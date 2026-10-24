"""The lecture processing pipeline.

Steps (each persisted with its own status in `lectures.steps` and the job doc):
  extract_audio -> transcribe -> process_transcript -> embeddings -> summary ->
  notes -> knowledge_map -> quiz -> flashcards

A lecture is marked `completed` only after every step finished (or was
legitimately skipped, e.g. embeddings in demo mode). Steps that already
completed are not repeated when a job is retried. Temporary audio is always
cleaned up.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from bson import ObjectId

from ..core.config import get_settings
from ..models.documents import PIPELINE_STEPS, STEP_LABELS, utcnow
from ..services import audio_extractor, content_safety_service, demo_extractor, embedding_service
from ..services.flashcard_generator import generate_flashcards
from ..services.knowledge_extractor import extract_knowledge
from ..services.llm_client import LLMError, LLMUnavailable
from ..services.notes_generator import add_section_timestamps, clean_notes, generate_notes, render_markdown
from ..services.quiz_generator import generate_quiz
from ..services.storage_service import get_storage
from ..services.summarization_service import summarize_lecture
from ..services.transcript_processor import build_chunks, clean_segments
from ..services.transcription_service import TranscriptionError, get_transcriber

log = logging.getLogger(__name__)

STEP_WEIGHTS = {"extract_audio": 5, "transcribe": 40, "process_transcript": 3, "content_safety": 2, "embeddings": 5, "summary": 20,
                "notes": 10, "knowledge_map": 6, "quiz": 6, "flashcards": 5}


class StepError(Exception):
    def __init__(self, step: str, message: str, retryable: bool = True):
        super().__init__(message)
        self.step = step
        self.message = message
        self.retryable = retryable


def overall_progress(steps: dict, current: str | None = None, frac: float = 0.0) -> int:
    total = sum(STEP_WEIGHTS.values())
    done = sum(STEP_WEIGHTS[s] for s, v in steps.items() if v.get("status") in ("completed", "skipped"))
    if current:
        done += STEP_WEIGHTS[current] * max(0.0, min(1.0, frac))
    return int(round(100 * done / total))


class Pipeline:
    def __init__(self, db, lecture_id: ObjectId, job_id: ObjectId | None = None):
        self.db = db
        self.lecture_id = lecture_id
        self.job_id = job_id
        self.storage = get_storage()
        self.settings = get_settings()
        self.lecture: dict = {}
        self._demo: dict | None = None
        self._step_frac = 0.0

    # ------------------------------------------------------------------ utils
    async def _reload(self):
        self.lecture = await self.db.lectures.find_one({"_id": self.lecture_id})
        if not self.lecture:
            raise StepError("load", "Lecture no longer exists.", retryable=False)

    async def _set(self, fields: dict):
        fields["updated_at"] = utcnow()
        await self.db.lectures.update_one({"_id": self.lecture_id}, {"$set": fields})
        if self.job_id is not None:
            jf = {k: v for k, v in fields.items() if k in ("progress", "current_step", "status", "error")}
            if jf:
                jf["updated_at"] = utcnow()
                await self.db.processing_jobs.update_one({"_id": self.job_id}, {"$set": jf})

    async def _step_status(self, step: str, status: str, error: str | None = None):
        now = utcnow()
        upd = {f"steps.{step}.status": status, f"steps.{step}.error": error}
        if status == "running":
            upd[f"steps.{step}.started_at"] = now
            upd[f"steps.{step}.finished_at"] = None
        else:
            upd[f"steps.{step}.finished_at"] = now
        self.lecture.setdefault("steps", {}).setdefault(step, {})["status"] = status
        upd["progress"] = overall_progress(self.lecture["steps"])
        await self._set(upd)
        if self.job_id is not None:
            await self.db.processing_jobs.update_one({"_id": self.job_id}, {"$set": {f"steps.{step}": status}})

    def _meta(self) -> dict:
        return {k: self.lecture.get(k) for k in ("title", "subject", "description")}

    def _ldir(self) -> Path:
        return self.storage.lecture_dir(str(self.lecture["user_id"]), str(self.lecture_id))

    async def _segments(self) -> list[dict]:
        return [s async for s in self.db.transcript_segments.find({"lecture_id": self.lecture_id}, {"_id": 0}).sort("idx", 1)]

    async def _chunks(self) -> list[dict]:
        return [c async for c in self.db.transcript_chunks.find({"lecture_id": self.lecture_id}, {"_id": 0, "embedding": 0}).sort("idx", 1)]

    async def _demo_outputs(self) -> dict:
        if self._demo is None:
            self._demo = demo_extractor.build_demo_outputs(self._meta(), await self._segments(), await self._chunks())
        return self._demo

    async def _digests(self) -> tuple[list[dict], list[dict]]:
        doc = await self.db.summaries.find_one({"lecture_id": self.lecture_id})
        if not doc or not doc.get("digests"):
            raise StepError("summary", "Summary digests are missing; re-run the summary step.")
        return doc["digests"], doc.get("reduced_digests") or doc["digests"]

    @property
    def ai(self) -> bool:
        return self.settings.ai_enabled

    # ------------------------------------------------------------------ run
    async def run(self) -> None:
        await self._reload()
        await self._set({"status": "processing", "error": None})
        try:
            for step in PIPELINE_STEPS:
                st = self.lecture.get("steps", {}).get(step, {}).get("status")
                if st in ("completed", "skipped"):
                    continue
                await self._set({"current_step": step, "current_step_label": STEP_LABELS[step]})
                await self._step_status(step, "running")
                self._step_frac = 0.0
                tick = asyncio.create_task(self._ticker(step))
                try:
                    result = await getattr(self, f"step_{step}")()
                except StepError:
                    raise
                except (LLMError, LLMUnavailable) as exc:
                    raise StepError(step, str(exc), retryable=isinstance(exc, LLMError)) from exc
                except audio_extractor.AudioExtractionError as exc:
                    raise StepError(step, str(exc), retryable=False) from exc
                except TranscriptionError as exc:
                    raise StepError(step, str(exc), retryable=False) from exc
                except Exception as exc:
                    log.exception("Step %s failed", step)
                    raise StepError(step, f"{type(exc).__name__}: {str(exc)[:300]}") from exc
                finally:
                    tick.cancel()
                await self._step_status(step, "skipped" if result == "skipped" else "completed")
            await self._set({"status": "completed", "progress": 100, "current_step": None,
                             "current_step_label": None, "processed_at": utcnow(),
                             "mode": "ai" if self.ai else "demo"})
            await self.db.activity.insert_one({"user_id": self.lecture["user_id"], "type": "lecture_completed",
                                               "lecture_id": self.lecture_id, "minutes": round((self.lecture.get("duration") or 0) / 60, 2),
                                               "created_at": utcnow()})
        except StepError as exc:
            await self._step_status(exc.step, "failed", exc.message) if exc.step in PIPELINE_STEPS else None
            await self._set({"status": "failed", "error": f"{STEP_LABELS.get(exc.step, exc.step)} failed: {exc.message}"})
            raise
        finally:
            self._cleanup_temp()

    async def _ticker(self, step: str):
        try:
            while True:
                await asyncio.sleep(2)
                await self._set({"progress": overall_progress(self.lecture["steps"], step, self._step_frac),
                                 "current_step_progress": round(self._step_frac, 3)})
        except asyncio.CancelledError:
            pass

    def _cleanup_temp(self):
        try:
            d = self._ldir()
            for name in ("work.wav",):
                self.storage.remove_quietly(d / name)
        except Exception:
            pass

    # ------------------------------------------------------------------ steps
    async def step_extract_audio(self):
        media = self.lecture.get("media", {})
        src = self.storage.resolve(media["original"]) if media.get("original") else None
        if not src or not src.exists():
            if media.get("playback") and self.storage.resolve(media["playback"]).exists():
                src = self.storage.resolve(media["playback"])
            else:
                raise StepError("extract_audio", "The uploaded file is missing from storage.", retryable=False)
        info = await audio_extractor.probe(src)
        if not info.has_audio:
            raise StepError("extract_audio", "This file has no audio track.", retryable=False)
        d = self._ldir()
        await audio_extractor.extract_audio(src, d / "work.wav")
        playback = d / "playback.m4a"
        if not playback.exists():
            await audio_extractor.make_playback_audio(src, playback)
        await self._set({"duration": round(info.duration, 2), "media.playback": self.storage.relpath(playback),
                         "media.has_video": info.has_video})
        self.lecture["duration"] = round(info.duration, 2)

    async def step_transcribe(self):
        d = self._ldir()
        wav = d / "work.wav"
        if not wav.exists():
            await self.step_extract_audio()
        transcriber = get_transcriber()

        def cb(x: float):
            self._step_frac = x

        try:
            lang = self.lecture.get("language_requested") or None
            result = await transcriber.transcribe(wav, language=lang, progress_cb=cb)
        finally:
            self.storage.remove_quietly(wav)
        if not result.segments:
            raise TranscriptionError("No speech was detected in this recording.")
        raw = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text, "speaker": s.speaker} for s in result.segments]
        segs = clean_segments(raw)
        await self.db.transcript_segments.delete_many({"lecture_id": self.lecture_id})
        uid = self.lecture["user_id"]
        await self.db.transcript_segments.insert_many([
            {"lecture_id": self.lecture_id, "user_id": uid, "idx": s["idx"], "start": s["start"], "end": s["end"],
             "text": s["text"], "speaker": s.get("speaker"), "edited": False} for s in segs
        ])
        await self._set({"language": result.language, "word_count": sum(len(s["text"].split()) for s in segs),
                         "segment_count": len(segs), "has_speakers": any(s.get("speaker") for s in segs),
                         "transcription": {"provider": result.provider, "model": result.model, **result.extra},
                         "duration": round(self.lecture.get("duration") or result.duration, 2)})

    async def step_process_transcript(self):
        segs = await self._segments()
        chunks = build_chunks(segs, self.settings.chunk_target_chars, self.settings.chunk_overlap_segments)
        await self.db.transcript_chunks.delete_many({"lecture_id": self.lecture_id})
        await self.db.transcript_chunks.insert_many([
            {"lecture_id": self.lecture_id, "user_id": self.lecture["user_id"], "idx": c.idx, "start": c.start,
             "end": c.end, "seg_start": c.seg_start, "seg_end": c.seg_end, "text": c.text} for c in chunks
        ])
        await self._set({"chunk_count": len(chunks)})
        self._demo = None

    async def step_content_safety(self):
        # Non-fatal by design: the lexicon always runs; AI moderation errors are recorded, not raised.
        try:
            await content_safety_service.scan_lecture(self.db, self.lecture)
        except Exception as exc:
            log.warning("Content safety scan failed (non-fatal): %s", exc)
            await self.db.content_safety.replace_one(
                {"lecture_id": self.lecture_id},
                {"lecture_id": self.lecture_id, "user_id": self.lecture["user_id"], "scanned_at": utcnow(), "flagged": [],
                 "summary": content_safety_service.summarize([]), "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                 "moderation": {"status": "failed", "error": "scan failed"}}, upsert=True)

    async def step_embeddings(self):
        if not self.ai:
            return "skipped"
        await embedding_service.embed_chunks(self.db, self.lecture_id, await self._chunks())

    async def step_summary(self):
        now = utcnow()
        base = {"lecture_id": self.lecture_id, "user_id": self.lecture["user_id"], "updated_at": now}
        if not self.ai:
            demo = await self._demo_outputs()
            doc = {**base, "mode": "demo", "summary": demo["summary"], "chapters": demo["chapters"], "digests": [],
                   "reduced_digests": []}
        else:
            chunks = await self._chunks()

            def cb(x):
                self._step_frac = x
            out = await summarize_lecture(chunks, self._meta(), progress_cb=cb)
            doc = {**base, "mode": "ai", "model": self.settings.openai_chat_model, **out}
        await self.db.summaries.update_one({"lecture_id": self.lecture_id},
                                           {"$set": doc, "$setOnInsert": {"created_at": now}}, upsert=True)

    async def step_notes(self):
        now = utcnow()
        chunks = await self._chunks()
        starts = {c["idx"]: c["start"] for c in chunks}
        if not self.ai:
            notes = (await self._demo_outputs())["notes"]
            mode = "demo"
        else:
            digests, _ = await self._digests()
            user = await self.db.users.find_one({"_id": self.lecture["user_id"]}) or {}
            style = (user.get("preferences") or {}).get("note_style", "exam")
            notes = clean_notes((await generate_notes(digests, self._meta(), style)).model_dump())
            mode = "ai"
        notes = add_section_timestamps(notes, chunks, await self._segments())
        md = render_markdown(notes, starts, demo=mode == "demo")
        await self.db.study_notes.update_one(
            {"lecture_id": self.lecture_id},
            {"$set": {"lecture_id": self.lecture_id, "user_id": self.lecture["user_id"], "structured": notes,
                      "markdown": md, "edited": False, "mode": mode, "updated_at": now},
             "$setOnInsert": {"created_at": now}}, upsert=True)

    async def step_knowledge_map(self):
        now = utcnow()
        if not self.ai:
            km, mode = (await self._demo_outputs())["knowledge"], "demo"
        else:
            _, reduced = await self._digests()
            km = await extract_knowledge(reduced, self._meta(), await self._chunks(), await self._segments())
            mode = "ai"
        await self.db.knowledge_maps.update_one(
            {"lecture_id": self.lecture_id},
            {"$set": {"lecture_id": self.lecture_id, "user_id": self.lecture["user_id"], **km, "mode": mode,
                      "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)

    async def step_quiz(self):
        now = utcnow()
        if not self.ai:
            quiz, mode = (await self._demo_outputs())["quiz"], "demo"
        else:
            _, reduced = await self._digests()
            quiz, mode = await generate_quiz(reduced, self._meta()), "ai"
        await self.db.quizzes.delete_many({"lecture_id": self.lecture_id, "source": "auto"})
        await self.db.quizzes.insert_one({"lecture_id": self.lecture_id, "user_id": self.lecture["user_id"],
                                          "title": quiz["title"], "questions": quiz["questions"], "difficulty": "mixed",
                                          "source": "auto", "mode": mode, "created_at": now, "updated_at": now})

    async def step_flashcards(self):
        now = utcnow()
        if not self.ai:
            cards, mode = (await self._demo_outputs())["flashcards"], "demo"
        else:
            _, reduced = await self._digests()
            cards, mode = await generate_flashcards(reduced, self._meta()), "ai"
        await self.db.flashcards.update_one(
            {"lecture_id": self.lecture_id},
            {"$set": {"lecture_id": self.lecture_id, "user_id": self.lecture["user_id"], "cards": cards, "mode": mode,
                      "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)
