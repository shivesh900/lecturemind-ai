"""Content safety: detect harsh, abusive or threatening language in transcripts.

Two detectors, merged per transcript segment:

1. **Lexicon** (always on, local, free). A curated list of English, Hinglish and
   Tamil-English (transliterated) abusive words, matched on word boundaries with
   leetspeak / masking tolerance (``f*ck``, ``sh1t``, ``b!tch``), plus regular
   expressions for threat phrases ("I will kill you", "you're dead",
   "watch your back", "maar dunga" ...). Fast and predictable, but it cannot
   understand context or sarcasm.
2. **AI moderation** (only when ``OPENAI_API_KEY`` is set and
   ``MODERATION_ENABLED`` is true). Segments are sent in batches to the OpenAI
   moderation endpoint (``MODERATION_MODEL``, default ``omni-moderation-latest``).
   Its category scores are mapped onto the same four categories. If the call
   fails, the lexicon results are kept and the failure is recorded.

Categories: ``profanity``, ``insult`` (insults / harassment), ``threat``
(threats / violence) and ``hate``. Severity: ``low`` < ``medium`` < ``high``.
Every flag records its ``source``: ``lexicon`` or ``ai_moderation``.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from ..core.config import get_settings
from ..models.documents import utcnow

log = logging.getLogger(__name__)

LEXICON_VERSION = "2026.10-1"
CATEGORIES = ("threat", "hate", "insult", "profanity")
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
CATEGORY_LABELS = {"threat": "Threat / violence", "hate": "Hate", "insult": "Insult / harassment", "profanity": "Profanity"}

# --------------------------------------------------------------------------- lexicon
# (word stem, allowed suffixes, category, severity, language)
# Suffixes are matched literally after the stem; "" = the bare stem.
_LEXICON: list[tuple[str, tuple[str, ...], str, str, str]] = [
    # English profanity
    ("fuck", ("", "s", "ed", "er", "ers", "ing", "in", "off", "face", "wit", "head"), "profanity", "high", "en"),
    ("motherfuck", ("er", "ers", "ing", "a"), "profanity", "high", "en"),
    ("shit", ("", "s", "ty", "head", "hole", "e", "ting"), "profanity", "medium", "en"),
    ("bullshit", ("",), "profanity", "medium", "en"),
    ("bitch", ("", "es", "y", "ing"), "insult", "high", "en"),
    ("bastard", ("", "s"), "insult", "medium", "en"),
    ("asshole", ("", "s"), "insult", "high", "en"),
    ("arsehole", ("", "s"), "insult", "high", "en"),
    ("ass", ("",), "profanity", "low", "en"),
    ("dumbass", ("", "es"), "insult", "medium", "en"),
    ("jackass", ("", "es"), "insult", "medium", "en"),
    ("dick", ("", "head", "heads"), "profanity", "medium", "en"),
    ("cunt", ("", "s"), "profanity", "high", "en"),
    ("prick", ("", "s"), "insult", "medium", "en"),
    ("piss", ("", "ed", "ing"), "profanity", "low", "en"),
    ("damn", ("", "ed", "it"), "profanity", "low", "en"),
    ("goddamn", ("", "it"), "profanity", "low", "en"),
    ("crap", ("", "py"), "profanity", "low", "en"),
    ("wtf", ("",), "profanity", "low", "en"),
    ("stfu", ("",), "insult", "medium", "en"),
    ("wanker", ("", "s"), "insult", "medium", "en"),
    ("bollocks", ("",), "profanity", "low", "en"),
    ("slut", ("", "s"), "insult", "high", "en"),
    ("whore", ("", "s"), "insult", "high", "en"),
    # English insults
    ("idiot", ("", "s", "ic"), "insult", "medium", "en"),
    ("moron", ("", "s", "ic"), "insult", "medium", "en"),
    ("imbecile", ("", "s"), "insult", "medium", "en"),
    ("stupid", ("",), "insult", "low", "en"),
    ("dumb", ("",), "insult", "low", "en"),
    ("loser", ("", "s"), "insult", "low", "en"),
    ("pathetic", ("",), "insult", "low", "en"),
    ("worthless", ("",), "insult", "medium", "en"),
    ("scumbag", ("", "s"), "insult", "medium", "en"),
    # Slurs (hate)
    ("retard", ("", "s", "ed"), "hate", "high", "en"),
    ("nigger", ("", "s"), "hate", "high", "en"),
    ("nigga", ("", "s"), "hate", "high", "en"),
    ("faggot", ("", "s"), "hate", "high", "en"),
    ("fag", ("", "s"), "hate", "high", "en"),
    ("tranny", ("",), "hate", "high", "en"),
    ("kike", ("", "s"), "hate", "high", "en"),
    ("paki", ("", "s"), "hate", "high", "en"),
    # Hinglish (transliterated Hindi)
    ("chutiya", ("", "s", "pa"), "insult", "high", "hi"),
    ("chutia", ("", "s"), "insult", "high", "hi"),
    ("chootiya", ("",), "insult", "high", "hi"),
    ("madarchod", ("",), "profanity", "high", "hi"),
    ("maderchod", ("",), "profanity", "high", "hi"),
    ("behenchod", ("",), "profanity", "high", "hi"),
    ("bhenchod", ("",), "profanity", "high", "hi"),
    ("benchod", ("",), "profanity", "high", "hi"),
    ("bhosdike", ("",), "profanity", "high", "hi"),
    ("bhosdi", ("", "ke", "wala")), 
    ("bsdk", ("",), "profanity", "high", "hi"),
    ("gandu", ("",), "insult", "high", "hi"),
    ("gaand", ("", "u"), "profanity", "medium", "hi"),
    ("harami", ("",), "insult", "medium", "hi"),
    ("haramkhor", ("",), "insult", "medium", "hi"),
    ("kamina", ("",), "insult", "medium", "hi"),
    ("kamine", ("",), "insult", "medium", "hi"),
    ("kutta", ("",), "insult", "medium", "hi"),
    ("kutte", ("",), "insult", "medium", "hi"),
    ("kutiya", ("",), "insult", "high", "hi"),
    ("randi", ("", "ka", "ke")), 
    ("lauda", ("",), "profanity", "high", "hi"),
    ("lavda", ("",), "profanity", "high", "hi"),
    ("lodu", ("",), "insult", "high", "hi"),
    ("saala", ("",), "insult", "low", "hi"),
    ("saali", ("",), "insult", "low", "hi"),
    ("bewakoof", ("",), "insult", "low", "hi"),
    ("ullu", ("",), "insult", "low", "hi"),
    ("chakka", ("",), "hate", "high", "hi"),
    # Tamil-English (transliterated Tamil)
    ("punda", ("",), "profanity", "high", "ta"),
    ("pundai", ("",), "profanity", "high", "ta"),
    ("thevidiya", ("",), "insult", "high", "ta"),
    ("thevdiya", ("",), "insult", "high", "ta"),
    ("otha", ("",), "profanity", "high", "ta"),
    ("ommala", ("",), "profanity", "high", "ta"),
    ("oombu", ("",), "profanity", "high", "ta"),
    ("koothi", ("",), "profanity", "high", "ta"),
    ("baadu", ("",), "insult", "medium", "ta"),
    ("loosu", ("",), "insult", "low", "ta"),
    ("naaye", ("",), "insult", "medium", "ta"),
    ("porukki", ("",), "insult", "medium", "ta"),
]
# entries written without category/severity default to profanity/high (Hinglish)
_LEXICON = [e if len(e) == 5 else (e[0], e[1], "profanity", "high", "hi") for e in _LEXICON]

# leetspeak / masking classes per letter. "*" "#" "%" may stand in for any inner letter.
_LEET = {"a": "a4@", "b": "b8", "e": "e3", "g": "g9", "i": "i1!|l", "l": "l1|", "o": "o0", "s": "s5$", "t": "t7+", "u": "uv", "z": "z2"}
_MASK = "*#%"


def _char_class(ch: str, inner: bool) -> str:
    chars = _LEET.get(ch, ch)
    if inner:
        chars += _MASK
    return "[" + re.escape(chars) + "]"


def _term_pattern(stem: str, suffixes: tuple[str, ...]) -> str:
    # each letter may repeat (fuuuck); inner letters may be masked (f**k)
    parts = []
    for i, ch in enumerate(stem):
        inner = 0 < i < len(stem) - 1
        parts.append(_char_class(ch, inner) + "+")
    suf = "|".join(re.escape(s) for s in sorted(suffixes, key=len, reverse=True) if s)
    if not suf:
        return "".join(parts)
    return "".join(parts) + (f"(?:{suf})?" if "" in suffixes else f"(?:{suf})")


_BOUND_L = r"(?<![a-z0-9])"
_BOUND_R = r"(?![a-z0-9])"


@dataclass
class _Rule:
    regex: re.Pattern
    category: str
    severity: str
    label: str
    kind: str  # "word" | "phrase"
    lang: str = "en"


_WORD_RULES: list[_Rule] = [
    _Rule(re.compile(_BOUND_L + _term_pattern(stem, sufs) + _BOUND_R, re.I), cat, sev, stem, "word", lang)
    for stem, sufs, cat, sev, lang in _LEXICON
]

_BODY = r"(?:face|head|skull|ass|legs?|arms?|bones|teeth|neck|family|kids?|mom|mother|dad|father|sister|brother)"
_YOU = (r"(?:(?:you|u|ya|yall|y'all|him|her|them|tujhe|tumhe|usko|unko|tereko)(?![a-z0-9'])|(?:your|ur|his|their)\s+" + _BODY
        + r"(?![a-z])|that\s+(?:guy|girl|teacher|sir|kid|idiot))")
_WILL = r"(?:i\s*(?:'ll|will|wil|shall|am\s+going\s+to|'m\s+going\s+to|'m\s+gonna|am\s+gonna|gonna|'d|would)|we\s*(?:'ll|will|are\s+going\s+to|'re\s+gonna|are\s+gonna|gonna)|gonna)"

_PHRASES: list[tuple[str, str, str, str]] = [
    # (regex, category, severity, label)
    (_WILL + r"\s+(?:\w+\s+){0,2}?(?:kill|murder|stab|shoot|strangle|slit|behead|hang)\s+" + _YOU, "threat", "high", "threat to kill / seriously harm"),
    (_WILL + r"\s+(?:\w+\s+){0,2}?(?:beat|hurt|punch|slap|smash|bash|thrash|kick|hit|break)\s+" + _YOU, "threat", "medium", "threat of violence"),
    (_WILL + r"\s+(?:\w+\s+){0,2}?(?:burn|bomb|blow\s+up|shoot\s+up)\s+(?:your|the|this|that|his|her)\s+\w+", "threat", "high", "threat of attack"),
    (r"(?:you'?re|you\s+are|ur|u\s+r|you\s+r)\s+(?:so\s+)?(?:dead|a\s+dead\s+man|dead\s+meat|done\s+for|going\s+to\s+die|gonna\s+die|finished)" + _BOUND_R, "threat", "high", "\"you're dead\" threat"),
    (r"(?:you|u)\s*(?:'ll|will|are\s+going\s+to|r\s+gonna|are\s+gonna|gonna)\s+(?:die|regret\s+(?:this|it)|pay\s+for\s+(?:this|it|that))", "threat", "medium", "intimidation"),
    (r"(?:beat|kick|knock|slap)\s+the\s+(?:hell|shit|crap|life|living\s+daylights)\s+out\s+of\s+" + _YOU, "threat", "medium", "threat of violence"),
    (r"watch\s+(?:your|ur|yo)\s+back", "threat", "medium", "\"watch your back\""),
    (r"i\s+know\s+where\s+(?:you|u)\s+live", "threat", "high", "\"I know where you live\""),
    (r"(?:kill|hang|shoot)\s+(?:yourself|urself|ur\s+self|your\s+self)|" + _BOUND_L + r"kys" + _BOUND_R, "threat", "high", "incitement to self-harm"),
    (r"(?:go\s+)?die\s+in\s+a\s+(?:fire|hole|ditch)", "threat", "medium", "wishing death"),
    (r"(?:i'?ll|i\s+will|gonna)\s+(?:end|finish|destroy|ruin)\s+(?:you|u|your\s+life|ur\s+life)" + _BOUND_R, "threat", "medium", "threat to harm"),
    (r"(?:all|these|those)\s+(?:muslims|hindus|christians|jews|blacks|dalits|women|gays|immigrants|tamils|biharis)\s+(?:should|must|deserve\s+to)\s+(?:die|be\s+killed|burn)", "hate", "high", "hate: calls for violence against a group"),
    (r"(?:muslims|hindus|christians|jews|blacks|dalits|women|gays|immigrants)\s+are\s+(?:animals|dogs|pigs|vermin|cockroaches|subhuman)", "hate", "high", "hate: dehumanising a group"),
    (r"shut\s+(?:the\s+(?:f\w*|hell)\s+)?up", "insult", "low", "\"shut up\""),
    (r"go\s+to\s+hell", "insult", "low", "\"go to hell\""),
    (r"(?:you|u)\s+(?:suck|stink)" + _BOUND_R, "insult", "low", "\"you suck\""),
    # Hinglish threats
    (r"(?:maar|mar)\s*(?:dunga|dungi|daalunga|dalunga|daalenge|denge|dalenge)", "threat", "high", "Hinglish: \"I'll kill/beat you\""),
    (r"jaan\s+se\s+(?:maar|mar)", "threat", "high", "Hinglish: \"kill you\""),
    (r"(?:khatam|khallas)\s+kar\s*(?:dunga|denge|dungi)", "threat", "high", "Hinglish: \"I'll finish you\""),
    (r"(?:tujhe|tereko|tumhe)\s+dekh\s+(?:lunga|lungi|lenge)", "threat", "medium", "Hinglish: \"I'll see to you\""),
    (r"(?:haath|hath)\s+(?:pair\s+)?tod\s*(?:dunga|denge)", "threat", "medium", "Hinglish: \"I'll break your bones\""),
    # Tamil-English threats
    (r"(?:kolla|kola)\s*(?:poren|poraen|poven)|kolluven|konnuduven|konnuruven|kondruven", "threat", "high", "Tamil: \"I'll kill you\""),
    (r"adichiduven|adichuruven|adi\s*(?:pinniduven|vanguva)|pichiduven", "threat", "medium", "Tamil: \"I'll beat you\""),
]
_PHRASE_RULES: list[_Rule] = [
    _Rule(re.compile(_BOUND_L + "(?:" + p + ")", re.I), c, s, label, "phrase")
    for p, c, s, label in _PHRASES
]


def _normalize(text: str) -> str:
    """Lower-case and unify apostrophes. Keeps length so spans map back 1:1."""
    return (text or "").lower().replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")


def mask_term(term: str) -> str:
    t = term.strip()
    if len(t) <= 2:
        return t[0] + "*" * (len(t) - 1) if t else t
    if " " in t:
        return " ".join(mask_term(w) if len(w) > 3 else w for w in t.split(" "))
    return t[0] + "*" * (len(t) - 2) + t[-1]


@dataclass
class Match:
    term: str
    start: int
    end: int
    category: str
    severity: str
    label: str
    kind: str

    def as_dict(self) -> dict:
        return {"term": self.term, "masked": mask_term(self.term), "start": self.start, "end": self.end,
                "category": self.category, "severity": self.severity, "label": self.label, "kind": self.kind}


def scan_text(text: str) -> list[Match]:
    """Run the lexicon + threat-phrase detector on one sentence/segment."""
    norm = _normalize(text)
    out: list[Match] = []
    for rule in _PHRASE_RULES:
        for m in rule.regex.finditer(norm):
            out.append(Match(text[m.start():m.end()], m.start(), m.end(), rule.category, rule.severity, rule.label, "phrase"))
    for rule in _WORD_RULES:
        for m in rule.regex.finditer(norm):
            # a word already inside a matched phrase still counts (e.g. "fucking kill you")
            out.append(Match(text[m.start():m.end()], m.start(), m.end(), rule.category, rule.severity, rule.label, "word"))
    out.sort(key=lambda x: (x.start, -SEVERITY_RANK[x.severity]))
    # drop exact duplicate spans (two stems matching the same characters, e.g. bhosdi/bhosdike)
    seen: dict[tuple[int, int], Match] = {}
    for m in out:
        k = (m.start, m.end)
        if k not in seen or SEVERITY_RANK[m.severity] > SEVERITY_RANK[seen[k].severity]:
            seen[k] = m
    res = list(seen.values())
    # drop a word fully contained in a longer word match of the same category (motherfucker vs fuck)
    words = [m for m in res if m.kind == "word"]
    res = [m for m in res if not (m.kind == "word" and any(o is not m and o.kind == "word" and o.start <= m.start and o.end >= m.end
                                                             and (o.end - o.start) > (m.end - m.start) for o in words))]
    return sorted(res, key=lambda x: x.start)


def max_severity(items) -> str | None:
    best = None
    for it in items:
        sev = it["severity"] if isinstance(it, dict) else it.severity
        if best is None or SEVERITY_RANK[sev] > SEVERITY_RANK[best]:
            best = sev
    return best


def lexicon_flags(text: str) -> list[dict]:
    """Group lexicon matches into one flag per category."""
    by_cat: dict[str, list[Match]] = {}
    for m in scan_text(text):
        by_cat.setdefault(m.category, []).append(m)
    flags = []
    for cat, ms in by_cat.items():
        flags.append({"category": cat, "severity": max_severity(ms), "source": "lexicon",
                      "terms": sorted({m.term for m in ms}, key=str.lower), "matches": [m.as_dict() for m in ms]})
    return flags


# --------------------------------------------------------------------------- AI moderation
# OpenAI moderation category -> our category
_MOD_MAP = {
    "harassment": "insult",
    "harassment/threatening": "threat",
    "hate": "hate",
    "hate/threatening": "hate",
    "violence": "threat",
    "self-harm/instructions": "threat",
    "self_harm_instructions": "threat",
}


def _sev_from_score(score: float) -> str:
    return "high" if score >= 0.85 else "medium" if score >= 0.6 else "low"


def _to_dict(obj) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(by_alias=True)
    return dict(obj)


def moderation_flags(result, threshold: float) -> list[dict]:
    """Turn one moderation result (SDK object or dict) into our flags."""
    r = _to_dict(result)
    cats = _to_dict(r.get("categories"))
    scores = _to_dict(r.get("category_scores"))
    best: dict[str, tuple[float, list[str]]] = {}
    for name, ours in _MOD_MAP.items():
        score = float(scores.get(name) or 0.0)
        hit = bool(cats.get(name)) or score >= threshold
        if not hit:
            continue
        prev = best.get(ours)
        labels = (prev[1] if prev else []) + [name]
        best[ours] = (max(score, prev[0] if prev else 0.0), labels)
    return [{"category": cat, "severity": _sev_from_score(score), "source": "ai_moderation", "score": round(score, 3),
             "terms": [], "matches": [], "moderation_categories": labels} for cat, (score, labels) in best.items()]


async def moderate_texts(texts: list[str], client=None) -> list[list[dict]]:
    """Call the moderation endpoint in batches. Raises on failure (callers decide)."""
    s = get_settings()
    if client is None:
        from .llm_client import LLMClient
        client = LLMClient().raw_client()
    out: list[list[dict]] = []
    bs = max(1, s.moderation_batch_size)
    for i in range(0, len(texts), bs):
        batch = texts[i:i + bs]
        resp = await client.moderations.create(model=s.moderation_model, input=batch)
        results = list(getattr(resp, "results", None) or _to_dict(resp).get("results") or [])
        if len(results) != len(batch):
            raise RuntimeError(f"moderation returned {len(results)} results for {len(batch)} inputs")
        out.extend(moderation_flags(r, s.moderation_threshold) for r in results)
    return out


def moderation_available() -> bool:
    s = get_settings()
    return bool(s.ai_enabled and s.moderation_enabled)


# --------------------------------------------------------------------------- combine
def combine(flags: list[dict]) -> dict:
    cats = sorted({f["category"] for f in flags}, key=CATEGORIES.index)
    return {"categories": cats, "severity": max_severity(flags), "sources": sorted({f["source"] for f in flags}),
            "terms": sorted({t for f in flags for t in f.get("terms", [])}, key=str.lower)}


async def analyze_texts(texts: list[str], *, use_moderation: bool | None = None, client=None) -> tuple[list[list[dict]], dict]:
    """Lexicon for every text, plus AI moderation when available. Never raises for moderation errors."""
    lex = [lexicon_flags(t) for t in texts]
    want = moderation_available() if use_moderation is None else use_moderation
    info = {"status": "disabled", "model": None, "error": None}
    if want and texts:
        s = get_settings()
        info["model"] = s.moderation_model
        try:
            mod = await moderate_texts(texts, client=client)
            lex = [a + b for a, b in zip(lex, mod)]
            info["status"] = "used"
        except Exception as exc:  # non-fatal: keep lexicon results
            log.warning("AI moderation failed, keeping lexicon results: %s", type(exc).__name__)
            info["status"] = "failed"
            info["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
    elif not get_settings().ai_enabled:
        info["reason"] = "OPENAI_API_KEY not set"
    return lex, info


def summarize(flags: list[dict]) -> dict:
    by_cat = {c: 0 for c in CATEGORIES}
    by_sev = {s: 0 for s in SEVERITY_RANK}
    for f in flags:
        for c in f["categories"]:
            by_cat[c] += 1
        by_sev[f["severity"]] += 1
    return {"total_flagged": len(flags), "by_category": by_cat, "by_severity": by_sev}


async def scan_lecture(db, lecture: dict, *, client=None) -> dict:
    """Scan every transcript segment of a lecture and store the result in `content_safety`."""
    lid = lecture["_id"]
    segs = [s async for s in db.transcript_segments.find({"lecture_id": lid}, {"_id": 0, "idx": 1, "start": 1, "end": 1, "text": 1}).sort("idx", 1)]
    per_seg, info = await analyze_texts([s["text"] for s in segs], client=client)
    flagged = []
    for seg, flags in zip(segs, per_seg):
        if not flags:
            continue
        flagged.append({"segment_idx": seg["idx"], "start": seg["start"], "end": seg["end"], "text": seg["text"],
                        **combine(flags), "flags": flags})
    doc = {"lecture_id": lid, "user_id": lecture["user_id"], "scanned_at": utcnow(), "segments_scanned": len(segs),
           "lexicon_version": LEXICON_VERSION, "moderation": info, "flagged": flagged, "summary": summarize(flagged)}
    await db.content_safety.replace_one({"lecture_id": lid}, doc, upsert=True)
    return doc


def public_report(doc: dict) -> dict:
    return {
        "lecture_id": str(doc["lecture_id"]),
        "scanned_at": doc["scanned_at"].isoformat() if hasattr(doc.get("scanned_at"), "isoformat") else doc.get("scanned_at"),
        "segments_scanned": doc.get("segments_scanned", 0),
        "lexicon_version": doc.get("lexicon_version"),
        "moderation": doc.get("moderation"),
        "summary": doc.get("summary"),
        "flagged": doc.get("flagged", []),
    }
