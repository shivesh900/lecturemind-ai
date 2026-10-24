"""Retrieval over transcript chunks: semantic (embeddings), keyword (BM25-style),
and hybrid. Always scoped by user_id (and optionally one lecture)."""
from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

from ..utils.text import content_words
from .embedding_service import embed_query, from_binary


async def _load_chunks(db, user_id, lecture_id=None, with_embeddings=False) -> list[dict]:
    q = {"user_id": user_id}
    if lecture_id is not None:
        q["lecture_id"] = lecture_id
    proj = {"text": 1, "idx": 1, "start": 1, "end": 1, "lecture_id": 1, "seg_start": 1, "seg_end": 1}
    if with_embeddings:
        proj["embedding"] = 1
    return [c async for c in db.transcript_chunks.find(q, proj)]


def bm25(query: str, docs: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    q_terms = content_words(query)
    if not q_terms or not docs:
        return [0.0] * len(docs)
    toks = [content_words(d) for d in docs]
    avgdl = (sum(len(t) for t in toks) / len(toks)) or 1.0
    df = Counter()
    for t in toks:
        df.update(set(t))
    n = len(docs)
    scores = []
    for t in toks:
        tf = Counter(t)
        dl = len(t) or 1
        s = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            s += idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * dl / avgdl))
        scores.append(s)
    return scores


async def keyword_chunks(db, user_id, query: str, lecture_id=None, k: int = 5) -> list[dict]:
    chunks = await _load_chunks(db, user_id, lecture_id)
    scores = bm25(query, [c["text"] for c in chunks])
    ranked = sorted(zip(scores, chunks), key=lambda x: -x[0])
    return [{**c, "score": round(float(s), 4)} for s, c in ranked[:k] if s > 0]


async def semantic_chunks(db, user_id, query: str, lecture_id=None, k: int = 5) -> list[dict]:
    chunks = [c for c in await _load_chunks(db, user_id, lecture_id, with_embeddings=True) if c.get("embedding")]
    if not chunks:
        return []
    qv = await embed_query(query)
    valid = [c for c in chunks if len(from_binary(c["embedding"])) == len(qv)]
    if not valid:
        return []
    mat = np.stack([from_binary(c["embedding"]) for c in valid])
    sims = mat @ qv
    order = np.argsort(-sims)[:k]
    out = []
    for i in order:
        c = {kk: vv for kk, vv in valid[int(i)].items() if kk != "embedding"}
        c["score"] = round(float(sims[int(i)]), 4)
        out.append(c)
    return out


def best_segment_time(chunk: dict, segments: list[dict], text: str) -> float:
    words = set(content_words(text))
    pool = [s for s in segments if chunk.get("seg_start", 0) <= s["idx"] <= chunk.get("seg_end", 10**9)]
    best, best_score = None, 0
    for s in pool:
        score = len(words & set(content_words(s["text"])))
        if score > best_score:
            best, best_score = s, score
    return float(best["start"]) if best else float(chunk.get("start", 0))


def highlight_excerpt(text: str, query: str, width: int = 220) -> str:
    words = content_words(query)
    low = text.lower()
    pos = min([low.find(w) for w in words if low.find(w) >= 0] or [0])
    start = max(0, pos - width // 3)
    snippet = text[start : start + width]
    return ("…" if start > 0 else "") + snippet.strip() + ("…" if start + width < len(text) else "")


def regex_for(query: str) -> re.Pattern:
    return re.compile(re.escape(query.strip()), re.I)
