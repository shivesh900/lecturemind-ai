"""Knowledge map: topics, subtopics, concepts, definitions, entities, dates,
formulas, keywords and the relationships between them. Nodes are linked back to
transcript timestamps via their chunk + a keyword match inside it."""
from __future__ import annotations

import re

from ..schemas.ai import KnowledgeMapOut
from .llm_client import get_llm_client
from .summarization_service import GROUNDING, digests_context, meta_header
from .transcript_processor import locate_timestamp

KM_SYSTEM = (
    "You build a knowledge graph of a lecture. Nodes: main topics (type topic), subtopics, key concepts, definitions, "
    "people/named entities (entity), dates/events (date), formulas and important keywords. Each node gets a short "
    "explanation from the lecture in description and chunk_index = the Part where it appears. Edges connect related "
    "nodes with a short relation label (e.g. 'is a', 'part of', 'uses', 'defined as', 'contrasts with'). Every node "
    "must be connected to at least one other node. Use short unique ids like n1, n2. 12-40 nodes. " + GROUNDING
)


def _clean_id(x: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "", x)[:40] or "n"


def sanitize_map(km: KnowledgeMapOut, chunks: list[dict], segments: list[dict]) -> dict:
    by_idx = {c["idx"]: c for c in chunks}
    nodes, ids = [], set()
    for n in km.nodes:
        nid = _clean_id(n.id)
        while nid in ids:
            nid += "x"
        ids.add(nid)
        n.id = nid
        chunk = by_idx.get(n.chunk_index) if n.chunk_index is not None else None
        ts = locate_timestamp(n.label, segments, chunk)
        nodes.append({**n.model_dump(), "timestamp": ts})
    label_to_id = {n["label"].lower(): n["id"] for n in nodes}
    edges, seen = [], set()
    for e in km.edges:
        s = _clean_id(e.source) if _clean_id(e.source) in ids else label_to_id.get(e.source.lower())
        t = _clean_id(e.target) if _clean_id(e.target) in ids else label_to_id.get(e.target.lower())
        if not s or not t or s == t or (s, t) in seen:
            continue
        seen.add((s, t))
        edges.append({"source": s, "target": t, "relation": e.relation})
    return {"nodes": nodes, "edges": edges, "keywords": km.keywords[:30]}


async def extract_knowledge(digests: list[dict], meta: dict, chunks: list[dict], segments: list[dict]) -> dict:
    llm = get_llm_client()
    prompt = f"{meta_header(meta)}\n\nLECTURE DIGESTS:\n\n{digests_context(digests)}"
    km = await llm.chat_json(KM_SYSTEM, prompt, KnowledgeMapOut, max_tokens=5000)
    result = sanitize_map(km, chunks, segments)
    if not result["nodes"]:
        raise ValueError("The AI returned an empty knowledge map.")
    return result
