"""Grounded lecture chat: retrieve the most relevant transcript chunks, then ask
the model to answer ONLY from those excerpts and cite them. If the excerpts do not
support an answer, the reply says so instead of guessing."""
from __future__ import annotations

from ..core.config import get_settings
from ..schemas.ai import ChatAnswer
from ..utils.text import format_ts
from .llm_client import get_llm_client
from .retrieval_service import best_segment_time, keyword_chunks, semantic_chunks

NOT_IN_LECTURE = "The lecture doesn't contain enough information to answer that."

CHAT_SYSTEM = (
    "You are LectureMind, a study assistant answering questions about ONE lecture. You are given numbered excerpts "
    "from its transcript (with timestamps). Answer ONLY using these excerpts. You may explain concepts in simpler "
    "language, compare concepts, summarise a section, or explain formulas/examples, as long as everything you state is "
    "supported by the excerpts. If the excerpts do not contain the information, set supported=false and say briefly "
    "that the lecture does not cover it - do not use outside knowledge to fill gaps. List the excerpt numbers you used "
    "in cited_excerpts. Use short paragraphs or bullets; plain text with simple markdown."
)


async def retrieve(db, user_id, lecture_id, question: str, k: int = 5) -> tuple[list[dict], str]:
    hits: list[dict] = []
    method = "keyword"
    if get_settings().ai_enabled:
        try:
            hits = await semantic_chunks(db, user_id, question, lecture_id, k)
            method = "semantic"
        except Exception:
            hits = []
    if not hits:
        hits = await keyword_chunks(db, user_id, question, lecture_id, k)
        method = "keyword"
    return sorted(hits, key=lambda h: h["idx"]), method


async def answer(db, lecture: dict, question: str, history: list[dict]) -> dict:
    user_id = lecture["user_id"]
    hits, method = await retrieve(db, user_id, lecture["_id"], question)
    segments = [s async for s in db.transcript_segments.find({"lecture_id": lecture["_id"]}).sort("idx", 1)]

    if not get_settings().ai_enabled:
        if not hits:
            return {"answer": "Demo mode (no AI model configured): no passage in this lecture matches your question.",
                    "supported": False, "citations": [], "mode": "demo", "retrieval": method}
        cites = [_citation(h, segments, question) for h in hits[:3]]
        text = ("Demo mode (no AI model configured) - I can't compose an answer, but these are the most relevant "
                "passages from the lecture:\n\n" + "\n\n".join(f"[{format_ts(c['timestamp'])}] {c['excerpt']}" for c in cites))
        return {"answer": text, "supported": True, "citations": cites, "mode": "demo", "retrieval": method}

    if not hits:
        return {"answer": NOT_IN_LECTURE, "supported": False, "citations": [], "mode": "ai", "retrieval": method}

    excerpts = "\n\n".join(
        f"[{i + 1}] ({format_ts(h['start'])}–{format_ts(h['end'])})\n{h['text']}" for i, h in enumerate(hits)
    )
    convo = "\n".join(f"{m['role'].upper()}: {m['content'][:600]}" for m in history[-6:])
    prompt = (f"Lecture: {lecture.get('title')}\n\nEXCERPTS:\n{excerpts}\n\n"
              + (f"RECENT CONVERSATION:\n{convo}\n\n" if convo else "") + f"QUESTION: {question}")
    out = await get_llm_client().chat_json(CHAT_SYSTEM, prompt, ChatAnswer, max_tokens=1500)
    if not out.supported:
        return {"answer": out.answer.strip() or NOT_IN_LECTURE, "supported": False, "citations": [], "mode": "ai",
                "retrieval": method}
    used = [i for i in out.cited_excerpts if 1 <= i <= len(hits)] or list(range(1, min(2, len(hits)) + 1))
    cites = [_citation(hits[i - 1], segments, question + " " + out.answer) for i in used]
    return {"answer": out.answer.strip(), "supported": True, "citations": cites, "mode": "ai", "retrieval": method}


def _citation(hit: dict, segments: list[dict], text: str) -> dict:
    ts = best_segment_time(hit, segments, text)
    seg = next((s for s in segments if s["start"] == ts), None)
    excerpt = seg["text"] if seg else hit["text"][:240]
    return {"chunk_index": hit["idx"], "timestamp": ts, "start": hit["start"], "end": hit["end"],
            "excerpt": excerpt[:300], "score": hit.get("score")}
