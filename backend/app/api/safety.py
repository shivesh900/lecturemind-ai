"""Content safety: harsh / abusive / threatening language detection."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..core.database import get_db
from ..core.rate_limit import limiter
from ..services import content_safety_service as cs
from .deps import ai_rate_limit, get_current_user, get_owned_lecture

router = APIRouter(prefix="/api", tags=["safety"])


class SafetyCheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


def _busy(lecture: dict) -> bool:
    return lecture.get("status") in ("queued", "processing") and \
        (lecture.get("steps") or {}).get("content_safety", {}).get("status") not in ("completed", "skipped")


@router.get("/lectures/{lecture_id}/safety")
async def get_safety(lecture: dict = Depends(get_owned_lecture)):
    db = get_db()
    doc = await db.content_safety.find_one({"lecture_id": lecture["_id"]})
    if not doc:
        has_transcript = await db.transcript_segments.count_documents({"lecture_id": lecture["_id"]}, limit=1) > 0
        if not has_transcript or _busy(lecture):
            raise HTTPException(404, "No transcript has been scanned for this lecture yet.")
        # lectures processed before this feature existed: scan on first view
        doc = await cs.scan_lecture(db, lecture)
    return cs.public_report(doc)


@router.post("/lectures/{lecture_id}/safety/rescan")
async def rescan_safety(lecture: dict = Depends(get_owned_lecture), _=Depends(ai_rate_limit)):
    db = get_db()
    if await db.transcript_segments.count_documents({"lecture_id": lecture["_id"]}, limit=1) == 0:
        raise HTTPException(409, "This lecture has no transcript yet.")
    return cs.public_report(await cs.scan_lecture(db, lecture))


@router.post("/safety/check")
async def check_text(body: SafetyCheckRequest, user: dict = Depends(get_current_user)):
    limiter.check(f"safety:{user['_id']}", get_settings().safety_check_rate_limit_per_minute)
    text = body.text.strip()
    if not text:
        raise HTTPException(422, "Text cannot be empty.")
    per, info = await cs.analyze_texts([text])
    flags = per[0]
    matches = sorted((m for f in flags for m in f.get("matches", [])), key=lambda m: m["start"])
    return {"text": text, "flagged": bool(flags), **cs.combine(flags), "flags": flags, "matches": matches,
            "moderation": info}
