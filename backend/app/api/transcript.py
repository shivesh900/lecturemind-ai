"""Transcript read / edit / search."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.database import get_db
from ..models.documents import utcnow
from ..schemas.lecture import TranscriptUpdate
from .deps import get_owned_lecture

router = APIRouter(prefix="/api/lectures", tags=["transcript"])


def _seg(s: dict) -> dict:
    return {"idx": s["idx"], "start": s["start"], "end": s["end"], "text": s["text"], "speaker": s.get("speaker"),
            "edited": s.get("edited", False)}


@router.get("/{lecture_id}/transcript")
async def get_transcript(lecture: dict = Depends(get_owned_lecture)):
    segs = [_seg(s) async for s in get_db().transcript_segments.find({"lecture_id": lecture["_id"]}).sort("idx", 1)]
    return {
        "lecture_id": str(lecture["_id"]),
        "language": lecture.get("language"),
        "duration": lecture.get("duration"),
        "has_speakers": any(s.get("speaker") for s in segs),
        "transcription": lecture.get("transcription"),
        "segments": segs,
        "text": " ".join(s["text"] for s in segs),
    }


@router.patch("/{lecture_id}/transcript")
async def edit_transcript(body: TranscriptUpdate, lecture: dict = Depends(get_owned_lecture)):
    db = get_db()
    changed = 0
    for e in body.segments:
        text = re.sub(r"\s+", " ", e.text).strip()
        if not text:
            raise HTTPException(422, f"Segment {e.idx} cannot be empty.")
        res = await db.transcript_segments.update_one(
            {"lecture_id": lecture["_id"], "idx": e.idx}, {"$set": {"text": text, "edited": True}})
        if res.matched_count == 0:
            raise HTTPException(404, f"Segment {e.idx} not found.")
        changed += res.modified_count
    if changed:
        # keep chunk text (used by chat/search) in sync with the edited transcript
        segs = {s["idx"]: s["text"] async for s in db.transcript_segments.find({"lecture_id": lecture["_id"]})}
        async for ch in db.transcript_chunks.find({"lecture_id": lecture["_id"]}, {"embedding": 0}):
            text = " ".join(segs[i] for i in range(ch["seg_start"], ch["seg_end"] + 1) if i in segs)
            if text != ch["text"]:
                await db.transcript_chunks.update_one({"_id": ch["_id"]}, {"$set": {"text": text, "stale_embedding": True}})
        await db.lectures.update_one({"_id": lecture["_id"]}, {"$set": {"transcript_edited_at": utcnow(), "updated_at": utcnow()}})
    return {"ok": True, "updated": changed}


@router.get("/{lecture_id}/transcript/search")
async def search_transcript(q: str = Query(min_length=1, max_length=200), lecture: dict = Depends(get_owned_lecture)):
    rx = re.compile(re.escape(q.strip()), re.I)
    hits = []
    async for s in get_db().transcript_segments.find({"lecture_id": lecture["_id"]}).sort("idx", 1):
        n = len(rx.findall(s["text"]))
        if n:
            hits.append({**_seg(s), "matches": n})
    return {"query": q, "total": sum(h["matches"] for h in hits), "segments": hits}
