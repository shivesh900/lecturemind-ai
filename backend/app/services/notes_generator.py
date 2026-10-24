"""Exam-friendly structured study notes, generated from the chunk digests in
chronological groups (so long lectures keep their detail), rendered to Markdown
for viewing/editing/export."""
from __future__ import annotations

import re

from ..schemas.ai import StudyNotesOut
from ..utils.text import format_ts
from .llm_client import get_llm_client
from .summarization_service import GROUNDING, digests_context, meta_header
from .transcript_processor import locate_timestamp

STYLE_HINTS = {
    "concise": "Keep notes compact: short bullets, only the essentials.",
    "detailed": "Be thorough: full explanations under each heading, keep every detail from the material.",
    "exam": "Optimise for exam revision: crisp bullets, definitions, step-by-step explanations, formulas and examples.",
}

NOTES_SYSTEM = (
    "You write organised, exam-friendly college study notes from lecture digests. Create a SEPARATE section for each distinct "
    "topic in lecture order (usually 3-8 sections per Part; never put a whole Part into one section), each with "
    "bullet points and subheadings where useful. Fill definitions, steps, formulas, examples, advantages and "
    "disadvantages ONLY when the lecture covers them. For each section set chunk_index to the Part it comes from. "
    + GROUNDING
)


def _groups(digests: list[dict], budget: int = 14000) -> list[list[dict]]:
    groups, cur = [], []
    for d in digests:
        if cur and len(digests_context(cur + [d])) > budget:
            groups.append(cur)
            cur = []
        cur.append(d)
    if cur:
        groups.append(cur)
    return groups


async def generate_notes(digests: list[dict], meta: dict, style: str = "exam") -> StudyNotesOut:
    llm = get_llm_client()
    parts: list[StudyNotesOut] = []
    groups = _groups(digests)
    for gi, g in enumerate(groups):
        where = f"(lecture section {gi + 1} of {len(groups)})" if len(groups) > 1 else ""
        prompt = (
            f"{meta_header(meta)}\nStyle: {STYLE_HINTS.get(style, STYLE_HINTS['exam'])}\n"
            f"Digests {where}:\n\n{digests_context(g)}"
        )
        parts.append(await llm.chat_json(NOTES_SYSTEM, prompt, StudyNotesOut, max_tokens=5000))
    merged = StudyNotesOut(
        title=meta.get("title") or parts[0].title,
        subject=meta.get("subject") or parts[0].subject,
        sections=[s for p in parts for s in p.sections],
        terminology=_dedupe_defs([d for p in parts for d in p.terminology]),
        names_and_dates=list(dict.fromkeys(x for p in parts for x in p.names_and_dates)),
        revision_summary=[x for p in parts for x in p.revision_summary][:12],
    )
    return merged


_BULLET = re.compile(r"^\s*(?:[-*\u2022\u25cf\u25aa]|\d+[.)])\s+")


def clean_notes(notes: dict) -> dict:
    """Strip stray bullet characters the model sometimes puts inside list items."""
    def c(items):
        return [_BULLET.sub("", x).strip() for x in items if x and _BULLET.sub("", x).strip()]
    for sec in notes.get("sections", []):
        for key in ("bullets", "steps", "examples", "advantages", "disadvantages"):
            sec[key] = c(sec.get(key, []))
        for sub in sec.get("subsections", []):
            sub["bullets"] = c(sub.get("bullets", []))
    notes["revision_summary"] = c(notes.get("revision_summary", []))
    notes["names_and_dates"] = c(notes.get("names_and_dates", []))
    return notes


def add_section_timestamps(notes: dict, chunks: list[dict], segments: list[dict]) -> dict:
    by_idx = {c["idx"]: c for c in chunks}
    for sec in notes.get("sections", []):
        chunk = by_idx.get(sec.get("chunk_index"))
        probe = sec.get("heading", "") + " " + " ".join(sec.get("bullets", [])[:1])
        sec["timestamp"] = locate_timestamp(probe, segments, chunk)
    return notes


def _dedupe_defs(defs):
    seen, out = set(), []
    for d in defs:
        k = d.term.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(d)
    return out


def render_markdown(notes: dict, chunk_starts: dict[int, float] | None = None, demo: bool = False) -> str:
    chunk_starts = chunk_starts or {}
    md: list[str] = [f"# {notes.get('title') or 'Lecture notes'}"]
    if notes.get("subject"):
        md.append(f"**Subject:** {notes['subject']}")
    if demo:
        md.append("> Demo mode: these notes were assembled by keyword/extractive methods without an AI model.")
    for sec in notes.get("sections", []):
        ts = sec.get("timestamp")
        if ts is None and sec.get("chunk_index") is not None:
            ts = chunk_starts.get(sec.get("chunk_index"))
        md.append(f"\n## {sec['heading']}" + (f"  `[{format_ts(ts)}]`" if ts is not None else ""))
        if sec.get("overview"):
            md.append(sec["overview"])
        md += [f"- {b}" for b in sec.get("bullets", [])]
        for sub in sec.get("subsections", []):
            md.append(f"\n### {sub['heading']}")
            md += [f"- {b}" for b in sub.get("bullets", [])]
        if sec.get("definitions"):
            md.append("\n**Definitions**")
            md += [f"- **{d['term']}**: {d['definition']}" for d in sec["definitions"]]
        if sec.get("steps"):
            md.append("\n**Step by step**")
            md += [f"{i + 1}. {s}" for i, s in enumerate(sec["steps"])]
        if sec.get("formulas"):
            md.append("\n**Formulas**")
            md += [f"- `{f['expression']}`" + (f" — {f['meaning']}" if f.get("meaning") else "") for f in sec["formulas"]]
        if sec.get("examples"):
            md.append("\n**Examples**")
            md += [f"- {e}" for e in sec["examples"]]
        if sec.get("advantages"):
            md.append("\n**Advantages**")
            md += [f"- {e}" for e in sec["advantages"]]
        if sec.get("disadvantages"):
            md.append("\n**Disadvantages**")
            md += [f"- {e}" for e in sec["disadvantages"]]
    if notes.get("terminology"):
        md.append("\n## Key terminology")
        md += [f"- **{d['term']}**: {d['definition']}" for d in notes["terminology"]]
    if notes.get("names_and_dates"):
        md.append("\n## Important names & dates")
        md += [f"- {x}" for x in notes["names_and_dates"]]
    if notes.get("revision_summary"):
        md.append("\n## Final revision summary")
        md += [f"- {x}" for x in notes["revision_summary"]]
    return "\n".join(md).strip() + "\n"
