"""Clean transcript segments and split them into ordered, timestamped chunks.

Chunks are the unit for the map step of summarisation, for embeddings and for
retrieval. Each chunk keeps [start, end] and the range of segment indices it
covers, so anything generated from it can point back to a timestamp.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..utils.text import content_words, format_ts, split_sentences


@dataclass
class Chunk:
    idx: int
    start: float
    end: float
    seg_start: int
    seg_end: int  # inclusive
    text: str

    def as_prompt(self) -> str:
        return f"[Part {self.idx} | {format_ts(self.start)}–{format_ts(self.end)}]\n{self.text}"


def clean_segments(segments: list[dict], max_seg_chars: int = 600) -> list[dict]:
    """Normalise whitespace, drop empties, and split very long segments on sentence
    boundaries (interpolating timestamps by character position)."""
    out: list[dict] = []
    for s in segments:
        text = re.sub(r"\s+", " ", (s.get("text") or "")).strip()
        if not text:
            continue
        start, end = float(s.get("start", 0)), float(s.get("end", 0))
        if end < start:
            end = start
        if len(text) <= max_seg_chars:
            out.append({"start": start, "end": end, "text": text, "speaker": s.get("speaker")})
            continue
        sentences = split_sentences(text) or [text]
        total = sum(len(x) for x in sentences) or 1
        pos = 0
        buf: list[str] = []
        buf_start = start
        for sent in sentences:
            buf.append(sent)
            pos += len(sent)
            if sum(len(x) for x in buf) >= max_seg_chars // 2 or sent is sentences[-1]:
                t_end = start + (end - start) * (pos / total)
                out.append({"start": round(buf_start, 2), "end": round(t_end, 2), "text": " ".join(buf), "speaker": s.get("speaker")})
                buf, buf_start = [], t_end
    for i, s in enumerate(out):
        s["idx"] = i
    return out


def build_chunks(segments: list[dict], target_chars: int = 3500, overlap_segments: int = 1) -> list[Chunk]:
    """Greedy chronological chunking on segment boundaries with a small overlap so
    ideas spanning a boundary are not lost."""
    chunks: list[Chunk] = []
    i = 0
    n = len(segments)
    while i < n:
        j = i
        size = 0
        while j < n and (size == 0 or size + len(segments[j]["text"]) <= target_chars):
            size += len(segments[j]["text"]) + 1
            j += 1
        group = segments[i:j]
        chunks.append(Chunk(
            idx=len(chunks),
            start=float(group[0]["start"]),
            end=float(group[-1]["end"]),
            seg_start=int(group[0]["idx"]),
            seg_end=int(group[-1]["idx"]),
            text=" ".join(s["text"] for s in group),
        ))
        if j >= n:
            break
        i = max(j - overlap_segments, i + 1)
    return chunks


def locate_timestamp(label: str, segments: list[dict], chunk: dict | None = None) -> float | None:
    """Best-effort: first segment (inside the chunk if given) that mentions the label's words."""
    words = [w for w in content_words(label)][:4]
    if not words:
        return float(chunk["start"]) if chunk else None
    pool = segments
    if chunk:
        pool = [s for s in segments if chunk["seg_start"] <= s["idx"] <= chunk["seg_end"]] or segments
    best, best_score = None, 0
    for s in pool:
        low = s["text"].lower()
        score = sum(1 for w in words if w in low)
        if score > best_score:
            best, best_score = s, score
            if score == len(words):
                break
    if best is not None:
        return float(best["start"])
    return float(chunk["start"]) if chunk else None
