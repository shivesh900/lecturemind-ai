"""Speech-to-text with timestamps.

Providers (TRANSCRIPTION_PROVIDER):
  * local  - faster-whisper running on the server (free, private; default when
             no OpenAI key is configured). Model size via WHISPER_MODEL.
  * openai - OpenAI Whisper API (`whisper-1`, verbose_json segments). Audio is
             sent to OpenAI. Long files are split into 10-minute pieces.
  * auto   - openai when OPENAI_API_KEY is set, else local.

Neither provider performs speaker diarization, so `speaker` is left empty and the
UI does not invent speaker labels.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from ..core.config import get_settings
from . import audio_extractor

log = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    pass


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str | None = None


@dataclass
class TranscriptionResult:
    segments: list[Segment]
    language: str | None
    duration: float
    provider: str
    model: str
    extra: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segments)


class LocalWhisperTranscriber:
    name = "local"
    _model = None
    _model_name: str | None = None
    _lock = threading.Lock()

    def __init__(self, model_size: str | None = None):
        s = get_settings()
        self.model_size = model_size or s.whisper_model
        self.device = s.whisper_device
        self.compute_type = s.whisper_compute_type

    def _load(self):
        with LocalWhisperTranscriber._lock:
            if LocalWhisperTranscriber._model is None or LocalWhisperTranscriber._model_name != self.model_size:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:  # pragma: no cover
                    raise TranscriptionError(f"Local Whisper is unavailable ({exc}). Run: pip install -r requirements.txt") from exc
                log.info("Loading local Whisper model '%s' on %s (%s)", self.model_size, self.device, self.compute_type)
                LocalWhisperTranscriber._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
                LocalWhisperTranscriber._model_name = self.model_size
            return LocalWhisperTranscriber._model

    def _transcribe_sync(self, wav_path: str, language: str | None, progress_cb=None) -> TranscriptionResult:
        model = self._load()
        segments_iter, info = model.transcribe(
            wav_path,
            language=None if not language or language == "auto" else language,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        segs: list[Segment] = []
        total = float(getattr(info, "duration", 0) or 0)
        for seg in segments_iter:
            text = (seg.text or "").strip()
            if text:
                segs.append(Segment(start=float(seg.start), end=float(seg.end), text=text))
            if progress_cb and total > 0:
                progress_cb(min(0.99, float(seg.end) / total))
        return TranscriptionResult(
            segments=segs,
            language=getattr(info, "language", None),
            duration=total,
            provider="local",
            model=f"faster-whisper-{self.model_size}",
            extra={"language_probability": round(float(getattr(info, "language_probability", 0) or 0), 3)},
        )

    async def transcribe(self, wav_path: str | Path, language: str | None = None, progress_cb=None) -> TranscriptionResult:
        return await asyncio.to_thread(self._transcribe_sync, str(wav_path), language, progress_cb)


class OpenAITranscriber:
    name = "openai"

    def __init__(self, client=None):
        self._client = client
        self.model = get_settings().openai_transcription_model

    def _get_client(self):
        if self._client is None:
            from .llm_client import get_llm_client
            self._client = get_llm_client().raw_client()
        return self._client

    async def transcribe(self, wav_path: str | Path, language: str | None = None, progress_cb=None) -> TranscriptionResult:
        client = self._get_client()
        wav_path = Path(wav_path)
        pieces = await audio_extractor.split_audio(wav_path, wav_path.parent / f"{wav_path.stem}_pieces")
        segs: list[Segment] = []
        detected = None
        try:
            for i, (piece, offset) in enumerate(pieces):
                with open(piece, "rb") as fh:
                    kwargs = dict(model=self.model, file=fh, response_format="verbose_json",
                                  timestamp_granularities=["segment"])
                    if language and language != "auto":
                        kwargs["language"] = language
                    resp = await client.audio.transcriptions.create(**kwargs)
                data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
                detected = detected or data.get("language")
                for s in data.get("segments") or []:
                    text = (s.get("text") or "").strip()
                    if text:
                        segs.append(Segment(start=float(s["start"]) + offset, end=float(s["end"]) + offset, text=text))
                if progress_cb:
                    progress_cb((i + 1) / len(pieces))
        finally:
            for piece, _ in pieces:
                piece.unlink(missing_ok=True)
            try:
                (wav_path.parent / f"{wav_path.stem}_pieces").rmdir()
            except OSError:
                pass
        duration = segs[-1].end if segs else 0.0
        return TranscriptionResult(segments=segs, language=detected, duration=duration, provider="openai", model=self.model)


def get_transcriber(provider: str | None = None):
    provider = provider or get_settings().effective_transcription_provider
    if provider == "openai":
        if not get_settings().ai_enabled:
            raise TranscriptionError("TRANSCRIPTION_PROVIDER=openai but OPENAI_API_KEY is not set.")
        return OpenAITranscriber()
    return LocalWhisperTranscriber()
