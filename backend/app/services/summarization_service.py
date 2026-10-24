"""Map-reduce summarisation.

1. MAP: each transcript chunk -> ChunkDigest (title, summary, key points,
   definitions, formulas, examples, concepts, entities). Chunks are processed in
   chronological order with limited concurrency.
2. COMPRESS: if the digests together are still too large for one request, they
   are merged hierarchically in groups (still chronological) until they fit.
3. REDUCE: the (compressed) digests -> LectureSummary.

No single request ever contains the whole transcript of a long lecture.
"""
from __future__ import annotations

import asyncio
import logging

from ..schemas.ai import ChunkDigest, LectureSummary
from ..utils.text import format_ts
from .llm_client import get_llm_client

log = logging.getLogger(__name__)

GROUNDING = (
    "Use ONLY information stated in the lecture material provided. Never add facts, topics, names or formulas that "
    "are not in it. If something is not present, leave that list empty. Write in clear, student-friendly English."
)

MAP_SYSTEM = (
    "You are an expert teaching assistant who turns lecture transcripts into study material. "
    "You are given ONE part of a longer lecture transcript (speech-to-text output, may contain recognition errors; "
    "fix obvious mis-hearings only when the intended term is clear from context). " + GROUNDING
)

COMPRESS_SYSTEM = (
    "You merge consecutive study digests of a lecture into ONE digest that keeps every distinct key point, definition, "
    "formula, example, concept and named entity (deduplicate, do not drop details). " + GROUNDING
)

REDUCE_SYSTEM = (
    "You are an expert teaching assistant. You receive chronological digests of every part of a lecture and write the "
    "final lecture summary. " + GROUNDING + " quick_summary must be exactly five short lines. detailed_summary should "
    "have one section per major part of the lecture, in order. For main_topics set chunk_index to the Part number where "
    "the topic is mainly discussed."
)

DIGEST_BUDGET_CHARS = 18000


def digest_brief(d: dict) -> str:
    parts = [f"## Part {d['chunk_index']} [{format_ts(d.get('start'))}–{format_ts(d.get('end'))}] {d.get('title', '')}"]
    if d.get("summary"):
        parts.append(f"Summary: {d['summary']}")
    if d.get("key_points"):
        parts.append("Key points:\n" + "\n".join(f"- {x}" for x in d["key_points"]))
    if d.get("definitions"):
        parts.append("Definitions:\n" + "\n".join(f"- {x['term']}: {x['definition']}" for x in d["definitions"]))
    if d.get("formulas"):
        parts.append("Formulas:\n" + "\n".join(f"- {x['expression']} ({x.get('meaning', '')})" for x in d["formulas"]))
    if d.get("examples"):
        parts.append("Examples:\n" + "\n".join(f"- {x}" for x in d["examples"]))
    if d.get("concepts"):
        parts.append("Concepts: " + ", ".join(d["concepts"]))
    if d.get("entities"):
        parts.append("Named entities: " + ", ".join(d["entities"]))
    return "\n".join(parts)


def digests_context(digests: list[dict]) -> str:
    return "\n\n".join(digest_brief(d) for d in digests)


def meta_header(meta: dict) -> str:
    bits = [f"Lecture title: {meta.get('title') or 'Untitled'}"]
    if meta.get("subject"):
        bits.append(f"Subject: {meta['subject']}")
    if meta.get("description"):
        bits.append(f"Description from the student: {meta['description'][:500]}")
    return "\n".join(bits)


async def digest_chunks(chunks: list[dict], meta: dict, progress_cb=None, concurrency: int = 3) -> list[dict]:
    llm = get_llm_client()
    sem = asyncio.Semaphore(concurrency)
    done = 0
    results: list[dict | None] = [None] * len(chunks)

    async def one(i: int, ch: dict):
        nonlocal done
        async with sem:
            prompt = (
                f"{meta_header(meta)}\nThis is part {ch['idx']} of {len(chunks) - 1 if len(chunks) > 1 else 0} "
                f"(time {format_ts(ch['start'])}–{format_ts(ch['end'])}).\n\nTRANSCRIPT PART:\n{ch['text']}"
            )
            dg = await llm.chat_json(MAP_SYSTEM, prompt, ChunkDigest, max_tokens=1800)
            results[i] = {**dg.model_dump(), "chunk_index": ch["idx"], "start": ch["start"], "end": ch["end"]}
            done += 1
            if progress_cb:
                progress_cb(done / len(chunks))

    await asyncio.gather(*(one(i, c) for i, c in enumerate(chunks)))
    return [r for r in results if r is not None]


async def compress_digests(digests: list[dict], meta: dict, budget: int = DIGEST_BUDGET_CHARS) -> list[dict]:
    """Hierarchically merge consecutive digests until their brief fits the budget."""
    level = list(digests)
    llm = get_llm_client()
    rounds = 0
    while len(digests_context(level)) > budget and len(level) > 1 and rounds < 6:
        rounds += 1
        groups: list[list[dict]] = []
        cur: list[dict] = []
        for d in level:
            if cur and len(digests_context(cur + [d])) > budget // 2:
                groups.append(cur)
                cur = []
            cur.append(d)
        if cur:
            groups.append(cur)
        if len(groups) == len(level):  # cannot shrink by grouping; pair them up
            groups = [level[i : i + 2] for i in range(0, len(level), 2)]
        merged: list[dict] = []
        for g in groups:
            if len(g) == 1:
                merged.append(g[0])
                continue
            dg = await llm.chat_json(COMPRESS_SYSTEM, f"{meta_header(meta)}\n\n{digests_context(g)}", ChunkDigest, max_tokens=2500)
            merged.append({**dg.model_dump(), "chunk_index": g[0]["chunk_index"], "start": g[0]["start"],
                           "end": g[-1]["end"], "covers": [x["chunk_index"] for x in g]})
        level = merged
    return level


async def reduce_summary(digests: list[dict], meta: dict) -> LectureSummary:
    llm = get_llm_client()
    prompt = f"{meta_header(meta)}\n\nCHRONOLOGICAL DIGESTS OF THE LECTURE:\n\n{digests_context(digests)}"
    return await llm.chat_json(REDUCE_SYSTEM, prompt, LectureSummary, max_tokens=4000)


def build_chapters(digests: list[dict], max_chapters: int = 12) -> list[dict]:
    """Chapter list with timestamps from the per-chunk digests (no extra AI call)."""
    if not digests:
        return []
    group = max(1, -(-len(digests) // max_chapters))
    chapters = []
    for i in range(0, len(digests), group):
        g = digests[i : i + group]
        chapters.append({
            "title": g[0].get("title") or f"Part {i + 1}",
            "start": g[0]["start"],
            "end": g[-1]["end"],
            "summary": " ".join(x.get("summary", "") for x in g)[:800],
            "chunk_index": g[0]["chunk_index"],
        })
    return chapters


async def summarize_lecture(chunks: list[dict], meta: dict, progress_cb=None) -> dict:
    digests = await digest_chunks(chunks, meta, progress_cb=progress_cb)
    reduced = await compress_digests(digests, meta)
    summary = await reduce_summary(reduced, meta)
    return {
        "summary": summary.model_dump(),
        "chapters": build_chapters(digests),
        "digests": digests,
        "reduced_digests": reduced,
    }
