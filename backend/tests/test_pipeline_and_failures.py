"""End-to-end processing (real ffmpeg + real local Whisper tiny) and failure handling."""
import pytest

from app.services.llm_client import LLMError
from app.workers.queue import create_job, run_job

from .conftest import FakeLLM


async def _upload(client, headers, path, name, ctype):
    r = await client.post("/api/lectures/upload", files={"file": (name, path.read_bytes(), ctype)},
                          data={"title": "Speech basics", "subject": "ASR", "language": "en"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["lecture"]["id"]


@pytest.mark.slow
async def test_demo_mode_full_pipeline_with_real_transcription(client, alice, speech_wav, db):
    """No OpenAI key: real local transcription + clearly labelled non-LLM extraction."""
    lid = await _upload(client, alice, speech_wav, "lecture.wav", "audio/wav")
    st = (await client.get(f"/api/lectures/{lid}/status", headers=alice)).json()
    assert st["status"] == "completed", st
    assert st["steps"]["embeddings"]["status"] == "skipped"
    tr = (await client.get(f"/api/lectures/{lid}/transcript", headers=alice)).json()
    assert "speech" in tr["text"].lower()
    summary = (await client.get(f"/api/lectures/{lid}/summary", headers=alice)).json()
    assert summary["mode"] == "demo"
    notes = (await client.get(f"/api/lectures/{lid}/notes", headers=alice)).json()
    assert notes["mode"] == "demo" and "Demo mode" in notes["markdown"]
    chat = (await client.post(f"/api/lectures/{lid}/chat", json={"message": "what does the acoustic model do"}, headers=alice)).json()
    assert chat["message"]["mode"] == "demo" and chat["message"]["content"].startswith("Demo mode")
    # temp work file cleaned up, playback audio kept
    from app.services.storage_service import get_storage
    lec = await db.lectures.find_one({})
    d = get_storage().lecture_dir(str(lec["user_id"]), lid)
    assert not (d / "work.wav").exists() and (d / "playback.m4a").exists()
    media = await client.get(f"/api/lectures/{lid}/media", headers=alice)
    assert media.status_code == 200 and len(media.content) > 1000


@pytest.mark.slow
async def test_video_upload_ai_mode_with_mocked_llm(client, alice, speech_mp4, fake_llm, db):
    lid = await _upload(client, alice, speech_mp4, "lecture.mp4", "video/mp4")
    lec = (await client.get(f"/api/lectures/{lid}", headers=alice)).json()["lecture"]
    assert lec["status"] == "completed" and lec["kind"] == "video" and lec["mode"] == "ai"
    assert all(lec["steps"][s]["status"] == "completed" for s in lec["steps_order"])
    chunk = await db.transcript_chunks.find_one({})
    assert chunk.get("embedding") is not None
    chat = (await client.post(f"/api/lectures/{lid}/chat", json={"message": "What converts speech?"}, headers=alice)).json()
    assert chat["message"]["supported"] is True and chat["message"]["citations"]
    quiz = (await client.get(f"/api/lectures/{lid}/quizzes", headers=alice)).json()["quizzes"][0]
    mcq = next(q for q in quiz["questions"] if q["type"] == "mcq")
    att = (await client.post(f"/api/quizzes/{quiz['id']}/attempts", json={"answers": {mcq["id"]: mcq["correct_answer"]}}, headers=alice)).json()
    assert att["correct"] >= 1 and att["score"] > 0
    stats = (await client.get("/api/dashboard/stats", headers=alice)).json()
    assert stats["completed_lectures"] == 1 and stats["quizzes_completed"] == 1 and stats["notes_count"] == 1


async def test_chat_refuses_when_not_supported(client, alice, db, fake_llm):
    from .helpers import seed_lecture, user_id
    lid, _ = await seed_lecture(db, await user_id(client, alice))
    fake_llm.responses["ChatAnswer"] = lambda u: {"answer": "The lecture does not cover that.", "supported": False, "cited_excerpts": []}
    r = (await client.post(f"/api/lectures/{lid}/chat", json={"message": "Who won the world cup?"}, headers=alice)).json()
    assert r["message"]["supported"] is False and r["message"]["citations"] == []


async def test_missing_file_fails_permanently_without_retry(db, client, alice):
    from .helpers import seed_lecture, user_id
    lid, _ = await seed_lecture(db, await user_id(client, alice))
    lec = await db.lectures.find_one({"_id": lid})
    job = await create_job(db, lec, reset_steps=["extract_audio", "transcribe", "process_transcript"])
    assert await run_job(job, db) == "failed"
    lec = await db.lectures.find_one({"_id": lid})
    assert lec["status"] == "failed" and "missing" in lec["error"]
    assert lec["steps"]["extract_audio"]["status"] == "failed"
    j = await db.processing_jobs.find_one({"_id": job})
    assert j["attempts"] == 1  # permanent errors are not retried


async def test_ai_failure_retries_then_fails_and_never_marks_completed(db, client, alice, monkeypatch):
    from app.core import config
    from app.services import llm_client
    from .helpers import seed_lecture, user_id
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    config.get_settings.cache_clear()
    failing = FakeLLM(fail_with=LLMError("AI generation failed: RateLimitError"))
    llm_client.set_llm_client(failing)
    lid, _ = await seed_lecture(db, await user_id(client, alice))
    lec = await db.lectures.find_one({"_id": lid})
    job = await create_job(db, lec, reset_steps=["summary", "notes", "knowledge_map", "quiz", "flashcards"])
    assert await run_job(job, db) == "failed"
    j = await db.processing_jobs.find_one({"_id": job})
    assert j["attempts"] == config.get_settings().job_max_attempts
    lec = await db.lectures.find_one({"_id": lid})
    assert lec["status"] == "failed" and "RateLimitError" in lec["error"]
    assert lec["steps"]["summary"]["status"] == "failed" and lec["steps"]["notes"]["status"] == "pending"
    assert lec["steps"]["transcribe"]["status"] == "completed"  # earlier steps kept

    # once the AI recovers, a retry resumes from the failed step only
    ok = FakeLLM()
    llm_client.set_llm_client(ok)
    job2 = await create_job(db, lec, reset_steps=["summary", "notes", "knowledge_map", "quiz", "flashcards"])
    assert await run_job(job2, db) == "completed"
    assert {n for n, _ in ok.calls} >= {"ChunkDigest", "LectureSummary", "StudyNotesOut", "QuizOut"}
    assert (await db.lectures.find_one({"_id": lid}))["status"] == "completed"


async def test_reprocess_endpoint_and_busy_guard(client, db, alice):
    from .helpers import seed_lecture, user_id
    lid, _ = await seed_lecture(db, await user_id(client, alice))
    await db.lectures.update_one({"_id": lid}, {"$set": {"status": "processing"}})
    r = await client.post(f"/api/lectures/{lid}/reprocess", headers=alice)
    assert r.status_code == 409


async def test_rate_limit_on_ai_endpoints(client, db, alice, monkeypatch):
    from app.core import config
    from .helpers import seed_lecture, user_id
    monkeypatch.setenv("AI_RATE_LIMIT_PER_MINUTE", "2")
    config.get_settings.cache_clear()
    lid, _ = await seed_lecture(db, await user_id(client, alice))
    codes = [(await client.post(f"/api/lectures/{lid}/chat", json={"message": "Nyquist?"}, headers=alice)).status_code for _ in range(3)]
    assert codes[:2] == [200, 200] and codes[2] == 429
