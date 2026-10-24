"""Global search across the signed-in user's lectures, transcripts, notes and
concepts. Keyword search always; semantic search when embeddings exist."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query

from ..core.config import get_settings
from ..core.database import get_db
from ..services.retrieval_service import best_segment_time, highlight_excerpt, semantic_chunks
from .deps import get_current_user

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search")
async def search(q: str = Query(min_length=2, max_length=200),
                 mode: str = Query("hybrid", pattern="^(keyword|semantic|hybrid)$"),
                 user: dict = Depends(get_current_user)):
    db = get_db()
    uid = user["_id"]
    rx = re.compile(re.escape(q.strip()), re.I)
    mrx = {"$regex": re.escape(q.strip()), "$options": "i"}
    lectures = {d["_id"]: d async for d in db.lectures.find({"user_id": uid}, {"title": 1, "subject": 1, "created_at": 1, "description": 1})}
    groups: dict = {}

    def add(lid, match):
        if lid not in lectures:
            return
        g = groups.setdefault(lid, {"lecture_id": str(lid), "title": lectures[lid]["title"],
                                    "subject": lectures[lid].get("subject"), "matches": [], "score": 0.0})
        g["matches"].append(match)
        g["score"] += match.get("score", 1.0)

    if mode in ("keyword", "hybrid"):
        for lid, d in lectures.items():
            if rx.search(d.get("title") or "") or rx.search(d.get("subject") or "") or rx.search(d.get("description") or ""):
                add(lid, {"kind": "lecture", "text": d.get("description") or d.get("title"), "timestamp": None, "score": 3.0})
        async for s in db.transcript_segments.find({"user_id": uid, "text": mrx}).limit(200):
            add(s["lecture_id"], {"kind": "transcript", "text": highlight_excerpt(s["text"], q), "timestamp": s["start"],
                                  "score": 1.0})
        async for n in db.study_notes.find({"user_id": uid, "markdown": mrx}, {"markdown": 1, "lecture_id": 1}):
            lines = [ln for ln in n["markdown"].splitlines() if rx.search(ln)][:3]
            for ln in lines:
                add(n["lecture_id"], {"kind": "notes", "text": ln.strip("-# ").strip()[:240], "timestamp": None, "score": 1.5})
        async for km in db.knowledge_maps.find({"user_id": uid}, {"nodes": 1, "lecture_id": 1}):
            for node in km.get("nodes", []):
                if rx.search(node.get("label", "")) or rx.search(node.get("description", "")):
                    add(km["lecture_id"], {"kind": "concept", "text": f"{node['label']}: {node.get('description', '')}"[:240],
                                           "timestamp": node.get("timestamp"), "score": 2.0})

    semantic_used = False
    if mode in ("semantic", "hybrid") and get_settings().ai_enabled:
        try:
            hits = await semantic_chunks(db, uid, q, None, k=8)
            semantic_used = True
            seg_cache: dict = {}
            for h in hits:
                if h["score"] < 0.2:
                    continue
                lid = h["lecture_id"]
                if lid not in seg_cache:
                    seg_cache[lid] = [s async for s in db.transcript_segments.find({"lecture_id": lid}, {"_id": 0, "idx": 1, "start": 1, "text": 1})]
                ts = best_segment_time(h, seg_cache[lid], q)
                seg = next((s for s in seg_cache[lid] if s["start"] == ts), None)
                add(lid, {"kind": "semantic", "text": (seg["text"] if seg else h["text"][:240]), "timestamp": ts,
                          "score": round(2 * h["score"], 3), "similarity": h["score"]})
        except Exception:
            semantic_used = False

    results = sorted(groups.values(), key=lambda g: -g["score"])
    for g in results:
        seen, uniq = set(), []
        for m in sorted(g["matches"], key=lambda m: -m.get("score", 0)):
            key = (m["kind"], m["text"][:80])
            if key not in seen:
                seen.add(key)
                uniq.append(m)
        g["matches"] = uniq[:8]
        g["score"] = round(g["score"], 3)
    return {"query": q, "mode": mode, "semantic_available": get_settings().ai_enabled, "semantic_used": semantic_used,
            "results": results, "total": sum(len(g["matches"]) for g in results)}
