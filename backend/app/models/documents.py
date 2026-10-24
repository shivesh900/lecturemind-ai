"""MongoDB document shapes and helpers.

Collections:
  users, lectures, transcript_segments, transcript_chunks (chunk text + embedding),
  summaries, study_notes, quizzes, quiz_attempts, flashcards, knowledge_maps,
  chat_messages, processing_jobs, activity
"""
from __future__ import annotations

import datetime as dt
from typing import Any

from bson import ObjectId

PIPELINE_STEPS = [
    "extract_audio",
    "transcribe",
    "process_transcript",
    "content_safety",
    "embeddings",
    "summary",
    "notes",
    "knowledge_map",
    "quiz",
    "flashcards",
]

STEP_LABELS = {
    "extract_audio": "Extracting audio",
    "transcribe": "Transcribing speech",
    "process_transcript": "Segmenting & chunking",
    "content_safety": "Scanning for harsh language",
    "embeddings": "Building search index",
    "summary": "Writing summaries",
    "notes": "Generating study notes",
    "knowledge_map": "Extracting concepts",
    "quiz": "Generating quiz",
    "flashcards": "Creating flashcards",
}


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def oid(value: str | ObjectId | None) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    if not value or not ObjectId.is_valid(str(value)):
        return None
    return ObjectId(str(value))


def iso(value: Any) -> Any:
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.isoformat().replace("+00:00", "Z")
    return value


def serialize(doc: dict | None, drop: tuple[str, ...] = ()) -> dict | None:
    """Convert a Mongo document into JSON-safe dict with `id` instead of `_id`."""
    if doc is None:
        return None
    out: dict[str, Any] = {}
    for k, v in doc.items():
        if k in drop:
            continue
        if k == "_id":
            out["id"] = str(v)
        elif isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, dt.datetime):
            out[k] = iso(v)
        elif isinstance(v, dict):
            out[k] = serialize(v)
        elif isinstance(v, list):
            out[k] = [serialize(x) if isinstance(x, dict) else (str(x) if isinstance(x, ObjectId) else iso(x)) for x in v]
        else:
            out[k] = v
    return out


def new_steps() -> dict[str, dict]:
    return {s: {"status": "pending", "error": None, "started_at": None, "finished_at": None} for s in PIPELINE_STEPS}
