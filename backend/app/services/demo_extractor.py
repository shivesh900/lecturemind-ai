"""DEMO MODE (no OpenAI key): simple, transparent, non-LLM extraction.

Everything produced here is computed from the real transcript with classic
techniques - TF-IDF keywords, extractive sentence ranking, regex definition
patterns, keyword co-occurrence and cloze questions - and is labelled
`mode: "demo"` everywhere in the API and UI. It is not presented as AI output.
"""
from __future__ import annotations

import math
import random
import re
import uuid
from collections import Counter

from ..utils.text import STOPWORDS, content_words, format_ts, split_sentences

DEF_PATTERNS = [
    re.compile(r"^(?P<term>[A-Za-z][\w\- ]{2,40}?)\s+(?:is|are)\s+(?:defined as|called|known as)\s+(?P<def>.+)$", re.I),
    re.compile(r"^(?P<term>[A-Za-z][\w\- ]{2,40}?)\s+(?:refers to|means|stands for)\s+(?P<def>.+)$", re.I),
    re.compile(r"^(?P<term>(?:an?|the)\s+[A-Za-z][\w\- ]{2,40}?)\s+is\s+(?P<def>(?:an?|the)\s+.+)$", re.I),
    re.compile(r"^(?P<term>[A-Z][\w\-]{2,30}(?:\s[\w\-]{2,30}){0,3})\s+is\s+(?P<def>(?:an?|the)\s+.+)$"),
]


def keywords(chunks: list[dict], top: int = 25) -> list[tuple[str, float]]:
    docs = [content_words(c["text"]) for c in chunks]
    df = Counter()
    for d in docs:
        df.update(set(d))
    # bigrams of content words
    bigram_tf = Counter()
    trigram_tf = Counter()
    for c in chunks:
        words = [w for w in re.findall(r"[a-zA-Z][a-zA-Z\-]+", c["text"].lower())]
        for a, b in zip(words, words[1:]):
            if a not in STOPWORDS and b not in STOPWORDS and len(a) > 2 and len(b) > 2:
                bigram_tf[f"{a} {b}"] += 1
        for a, b, d in zip(words, words[1:], words[2:]):
            if a not in STOPWORDS and b not in STOPWORDS and d not in STOPWORDS and min(len(a), len(b), len(d)) > 2:
                trigram_tf[f"{a} {b} {d}"] += 1
    tf = Counter(w for d in docs for w in d)
    n = len(docs) or 1
    scores: dict[str, float] = {}
    for w, f in tf.items():
        if f < 2 and len(tf) > 40:
            continue
        idf = math.log(1 + n / df[w]) if n > 1 else 1.0
        scores[w] = f * idf * (1.2 if len(w) > 6 else 1.0)
    for bg, f in bigram_tf.items():
        if f >= 2:
            scores[bg] = f * 2.5
    for tg, f in trigram_tf.items():
        if f >= 2:
            scores[tg] = f * 3.5
            for part in (" ".join(tg.split()[:2]), " ".join(tg.split()[1:])):
                if bigram_tf.get(part, 0) <= f + 1:
                    scores.pop(part, None)
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    out: list[tuple[str, float]] = []
    for term, sc in ranked:
        if any(re.search(rf"\b{re.escape(term)}\b", o) and term != o for o, _ in out):
            continue
        out.append((term, sc))
        if len(out) >= top:
            break
    return out


def _sentences_with_time(segments: list[dict]) -> list[dict]:
    out = []
    for s in segments:
        for sent in split_sentences(s["text"]):
            if len(sent.split()) >= 5 and sent[0].isupper():
                out.append({"text": sent, "start": s["start"], "seg": s["idx"]})
    return out


def rank_sentences(sentences: list[dict], kw: dict[str, float]) -> list[dict]:
    for s in sentences:
        low = s["text"].lower()
        words = content_words(low)
        s["score"] = sum(v for k, v in kw.items() if k in low) / (1 + math.log(1 + len(words)))
    return sentences


def find_definitions(sentences: list[dict]) -> list[dict]:
    defs, seen = [], set()
    for s in sentences:
        for pat in DEF_PATTERNS:
            m = pat.match(s["text"].strip().rstrip("."))
            if m:
                term = re.sub(r"^(an?|the)\s+", "", m.group("term").strip(), flags=re.I)
                if term.lower() in seen or len(term.split()) > 5:
                    continue
                seen.add(term.lower())
                defs.append({"term": term, "definition": m.group("def").strip().rstrip(".") + ".", "start": s["start"]})
                break
    return defs


def build_demo_outputs(meta: dict, segments: list[dict], chunks: list[dict]) -> dict:
    kw_list = keywords(chunks)
    kw = dict(kw_list)
    sentences = rank_sentences(_sentences_with_time(segments), kw)
    defs = find_definitions(sentences)
    top_sorted = sorted(sentences, key=lambda s: -s["score"])

    def in_order(items):
        return sorted(items, key=lambda s: s["start"])

    quick = [s["text"] for s in in_order(top_sorted[:5])]
    executive = " ".join(s["text"] for s in in_order(top_sorted[:3]))

    per_chunk = []
    for c in chunks:
        cs = [s for s in sentences if c["seg_start"] <= s["seg"] <= c["seg_end"]]
        best = in_order(sorted(cs, key=lambda s: -s["score"])[:4])
        ck = [k for k, _ in keywords([c], top=4)]
        title = ", ".join(k.title() for k in ck[:3]) or f"Part {c['idx'] + 1}"
        per_chunk.append({"chunk": c, "title": title, "sentences": best, "keywords": ck})

    summary = {
        "executive_summary": executive,
        "quick_summary": quick,
        "detailed_summary": [{"heading": f"{p['title']} ({format_ts(p['chunk']['start'])})",
                              "content": " ".join(s["text"] for s in p["sentences"])} for p in per_chunk],
        "main_topics": [{"title": k.title(), "description": "", "chunk_index": None} for k, _ in kw_list[:8]],
        "arguments": [],
        "key_takeaways": [s["text"] for s in top_sorted[5:10]],
        "definitions": [{"term": d["term"], "definition": d["definition"]} for d in defs],
        "formulas": [],
        "examples": [s["text"] for s in sentences if re.search(r"\b(for example|for instance|e\.g\.|such as)\b", s["text"], re.I)][:6],
    }
    chapters = [{"title": p["title"], "start": p["chunk"]["start"], "end": p["chunk"]["end"],
                 "summary": " ".join(s["text"] for s in p["sentences"][:2]), "chunk_index": p["chunk"]["idx"]} for p in per_chunk]

    notes = {
        "title": meta.get("title") or "Lecture notes",
        "subject": meta.get("subject") or "",
        "sections": [{"heading": p["title"], "chunk_index": p["chunk"]["idx"], "overview": "",
                      "bullets": [s["text"] for s in p["sentences"]], "subsections": [],
                      "definitions": [{"term": d["term"], "definition": d["definition"]} for d in defs
                                      if p["chunk"]["start"] <= d["start"] <= p["chunk"]["end"]],
                      "steps": [], "formulas": [], "examples": [], "advantages": [], "disadvantages": []} for p in per_chunk],
        "terminology": [{"term": d["term"], "definition": d["definition"]} for d in defs],
        "names_and_dates": [],
        "revision_summary": quick,
    }

    # knowledge map: keyword nodes + co-occurrence edges
    top_terms = [k for k, _ in kw_list[:18]]
    nodes, edges = [], []
    first_time = {}
    for t in top_terms:
        hit = next((s for s in sentences if t in s["text"].lower()), None)
        first_time[t] = hit["start"] if hit else None
    def_map = {d["term"].lower(): d["definition"] for d in defs}
    for i, t in enumerate(top_terms):
        desc = def_map.get(t) or next((s["text"] for s in top_sorted if t in s["text"].lower()), "")
        nodes.append({"id": f"k{i}", "label": t.title(), "type": "topic" if i < 3 else "keyword",
                      "description": desc[:300], "chunk_index": None, "timestamp": first_time[t]})
    co = Counter()
    for s in sentences:
        low = s["text"].lower()
        present = [i for i, t in enumerate(top_terms) if t in low]
        for a in present:
            for b in present:
                if a < b:
                    co[(a, b)] += 1
    for (a, b), cnt in co.most_common(40):
        edges.append({"source": f"k{a}", "target": f"k{b}", "relation": f"co-occur ×{cnt}"})
    connected = {e["source"] for e in edges} | {e["target"] for e in edges}
    for n in nodes[1:]:
        if n["id"] not in connected:
            edges.append({"source": "k0", "target": n["id"], "relation": "mentioned with"})
    knowledge = {"nodes": nodes, "edges": edges, "keywords": [k for k, _ in kw_list]}

    # flashcards: definitions + cloze sentences
    cards = [{"front": f"What is {d['term']}?", "back": d["definition"], "difficulty": "easy", "chunk_index": None}
             for d in defs]
    for s in top_sorted[:20]:
        term = next((t for t in top_terms if t in s["text"].lower()), None)
        if not term or len(cards) >= 15:
            continue
        cloze = re.sub(re.escape(term), "_____", s["text"], flags=re.I)
        cards.append({"front": f"Fill in the blank: {cloze}", "back": term, "difficulty": "medium", "chunk_index": None})
    for c in cards:
        c.update({"id": uuid.uuid4().hex[:10], "rating": None, "review_count": 0, "last_reviewed_at": None})

    quiz = build_cloze_quiz(top_sorted, top_terms, defs)
    return {"summary": summary, "chapters": chapters, "notes": notes, "knowledge": knowledge, "flashcards": cards,
            "quiz": quiz, "keywords": [k for k, _ in kw_list]}


def build_cloze_quiz(top_sorted: list[dict], terms: list[str], defs: list[dict], seed: int = 7) -> dict:
    rng = random.Random(seed)
    qs = []
    used = set()
    for s in top_sorted:
        term = next((t for t in terms if t in s["text"].lower() and t not in used), None)
        if not term:
            continue
        distract = [t for t in terms if t != term and t not in s["text"].lower()]
        if len(distract) < 3:
            continue
        used.add(term)
        opts = rng.sample(distract, 3) + [term]
        rng.shuffle(opts)
        qs.append({"id": uuid.uuid4().hex[:10], "type": "mcq",
                   "question": "Which term completes this statement from the lecture? \"" +
                               re.sub(re.escape(term), "_____", s["text"], flags=re.I) + "\"",
                   "options": [o.title() for o in opts], "correct_answer": term.title(),
                   "explanation": f"At {format_ts(s['start'])} the lecture says: \"{s['text']}\"",
                   "difficulty": "easy", "important": False, "chunk_index": None})
        if len(qs) >= 6:
            break
    for s in top_sorted[6:12]:
        term = next((t for t in terms if t in s["text"].lower()), None)
        other = next((t for t in terms if t != term and t not in s["text"].lower()), None)
        if not term or not other:
            continue
        flip = rng.random() < 0.5
        text = re.sub(re.escape(term), other, s["text"], flags=re.I) if flip else s["text"]
        qs.append({"id": uuid.uuid4().hex[:10], "type": "true_false", "question": f"True or false: \"{text}\"",
                   "options": ["True", "False"], "correct_answer": "False" if flip else "True",
                   "explanation": f"The lecture ({format_ts(s['start'])}) says: \"{s['text']}\"",
                   "difficulty": "medium", "important": False, "chunk_index": None})
        if len([q for q in qs if q["type"] == "true_false"]) >= 3:
            break
    for d in defs[:2]:
        qs.append({"id": uuid.uuid4().hex[:10], "type": "short", "question": f"Define {d['term']} as explained in the lecture.",
                   "options": [], "correct_answer": d["definition"], "explanation": "Taken from the lecture's own definition.",
                   "difficulty": "easy", "important": True, "chunk_index": None})
    return {"title": "Demo quiz (cloze-based, no AI)", "questions": qs}
