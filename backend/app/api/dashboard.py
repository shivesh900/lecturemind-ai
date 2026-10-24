"""Dashboard statistics and weekly activity, computed from the database."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query

from ..core.database import get_db
from ..models.documents import serialize, utcnow
from .deps import get_current_user
from .lectures import public_lecture

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats")
async def stats(user: dict = Depends(get_current_user)):
    db = get_db()
    uid = user["_id"]
    lectures = [d async for d in db.lectures.find({"user_id": uid}, {"media": 0}).sort("created_at", -1)]
    completed = [d for d in lectures if d.get("status") == "completed"]
    seconds = sum(float(d.get("duration") or 0) for d in completed)
    attempts = [a async for a in db.quiz_attempts.find({"user_id": uid}, {"score": 1})]
    reviews = await db.activity.count_documents({"user_id": uid, "type": "flashcard_review"})
    titles = {d["_id"]: d["title"] for d in lectures}

    materials = []
    for coll, kind in (("study_notes", "notes"), ("quizzes", "quiz"), ("flashcards", "flashcards"), ("summaries", "summary")):
        async for m in db[coll].find({"user_id": uid}, {"_id": 1, "lecture_id": 1, "updated_at": 1, "created_at": 1, "mode": 1}).sort("updated_at", -1).limit(5):
            materials.append({"kind": kind, "lecture_id": str(m["lecture_id"]), "lecture_title": titles.get(m["lecture_id"], ""),
                              "updated_at": serialize({"t": m.get("updated_at") or m.get("created_at")})["t"], "mode": m.get("mode")})
    materials.sort(key=lambda x: x["updated_at"] or "", reverse=True)

    return {
        "total_lectures": len(lectures),
        "completed_lectures": len(completed),
        "learning_hours": round(seconds / 3600, 2),
        "learning_minutes": round(seconds / 60, 1),
        "notes_count": await db.study_notes.count_documents({"user_id": uid}),
        "quizzes_completed": len(attempts),
        "average_quiz_score": round(sum(a.get("score", 0) for a in attempts) / len(attempts), 1) if attempts else None,
        "flashcards_reviewed": reviews,
        "recent_lectures": [public_lecture(d) for d in lectures[:5]],
        "recent_materials": materials[:8],
        "jobs": [public_lecture(d) for d in lectures if d.get("status") in ("queued", "processing", "failed")][:10],
    }


@router.get("/activity")
async def activity(days: int = Query(7, ge=1, le=90), tz_offset_minutes: int = Query(0, ge=-840, le=840),
                   user: dict = Depends(get_current_user)):
    """Per-day counts. tz_offset_minutes = minutes EAST of UTC (IST = 330)."""
    db = get_db()
    offset = dt.timedelta(minutes=tz_offset_minutes)
    today_local = (utcnow() + offset).date()
    start_local = today_local - dt.timedelta(days=days - 1)
    start_utc = dt.datetime.combine(start_local, dt.time.min, tzinfo=dt.timezone.utc) - offset
    buckets = {}
    for i in range(days):
        d = start_local + dt.timedelta(days=i)
        buckets[d.isoformat()] = {"date": d.isoformat(), "label": d.strftime("%a"), "lectures": 0, "minutes": 0.0,
                                  "quiz_attempts": 0, "flashcard_reviews": 0, "chat_messages": 0, "study_actions": 0}
    async for ev in db.activity.find({"user_id": user["_id"], "created_at": {"$gte": start_utc}}):
        t = ev["created_at"]
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        key = (t + offset).date().isoformat()
        b = buckets.get(key)
        if not b:
            continue
        typ = ev.get("type")
        if typ == "lecture_uploaded":
            b["lectures"] += 1
        elif typ == "lecture_completed":
            b["minutes"] = round(b["minutes"] + float(ev.get("minutes") or 0), 1)
        elif typ == "quiz_attempt":
            b["quiz_attempts"] += 1
        elif typ == "flashcard_review":
            b["flashcard_reviews"] += 1
        elif typ == "chat_message":
            b["chat_messages"] += 1
        if typ in ("quiz_attempt", "flashcard_review", "chat_message", "notes_edited"):
            b["study_actions"] += 1
    return {"days": list(buckets.values())}
