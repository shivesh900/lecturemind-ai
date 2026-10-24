"""MongoDB connection (motor) and index initialisation."""
from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from .config import get_settings

log = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def set_database(db) -> None:
    """Used by tests to inject a mongomock-motor database."""
    global _db
    _db = db


def get_db() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is None:
        s = get_settings()
        _client = AsyncIOMotorClient(s.mongodb_uri, serverSelectionTimeoutMS=8000, uuidRepresentation="standard")
        _db = _client[s.mongodb_db]
    return _db


async def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


INDEXES: dict[str, list[tuple[list[tuple[str, int]], dict]]] = {
    "users": [([("email", ASCENDING)], {"unique": True})],
    "lectures": [
        ([("user_id", ASCENDING), ("created_at", DESCENDING)], {}),
        ([("user_id", ASCENDING), ("status", ASCENDING)], {}),
        ([("user_id", ASCENDING), ("subject", ASCENDING)], {}),
    ],
    "transcript_segments": [([("lecture_id", ASCENDING), ("idx", ASCENDING)], {"unique": True}), ([("user_id", ASCENDING)], {})],
    "transcript_chunks": [([("lecture_id", ASCENDING), ("idx", ASCENDING)], {"unique": True}), ([("user_id", ASCENDING)], {})],
    "summaries": [([("lecture_id", ASCENDING)], {"unique": True})],
    "study_notes": [([("lecture_id", ASCENDING)], {"unique": True}), ([("user_id", ASCENDING)], {})],
    "quizzes": [([("lecture_id", ASCENDING), ("created_at", DESCENDING)], {}), ([("user_id", ASCENDING)], {})],
    "quiz_attempts": [([("user_id", ASCENDING), ("created_at", DESCENDING)], {}), ([("quiz_id", ASCENDING)], {})],
    "flashcards": [([("lecture_id", ASCENDING)], {"unique": True}), ([("user_id", ASCENDING)], {})],
    "knowledge_maps": [([("lecture_id", ASCENDING)], {"unique": True})],
    "chat_messages": [([("lecture_id", ASCENDING), ("created_at", ASCENDING)], {})],
    "processing_jobs": [([("lecture_id", ASCENDING)], {}), ([("status", ASCENDING), ("created_at", ASCENDING)], {})],
    "activity": [([("user_id", ASCENDING), ("created_at", DESCENDING)], {})],
}


async def init_indexes(db: AsyncIOMotorDatabase | None = None) -> None:
    db = db if db is not None else get_db()
    for coll, specs in INDEXES.items():
        for keys, opts in specs:
            try:
                await db[coll].create_index(keys, **opts)
            except Exception as exc:  # pragma: no cover - mongomock limitations
                log.warning("index on %s failed: %s", coll, exc)
