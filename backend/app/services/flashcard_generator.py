"""Question/answer flashcards from the lecture's key concepts."""
from __future__ import annotations

import uuid

from ..schemas.ai import FlashcardsOut
from .llm_client import get_llm_client
from .summarization_service import GROUNDING, digests_context, meta_header

FLASH_SYSTEM = (
    "You create revision flashcards from a lecture. Front: a short question or term. Back: a concise, accurate answer "
    "(1-3 sentences) taken from the lecture. Cover definitions, key concepts, formulas and examples across all parts. "
    "Set difficulty and chunk_index (the Part the card comes from). " + GROUNDING
)


async def generate_flashcards(digests: list[dict], meta: dict, count: int = 15) -> list[dict]:
    llm = get_llm_client()
    prompt = f"{meta_header(meta)}\nCreate {count} flashcards.\n\nLECTURE DIGESTS:\n\n{digests_context(digests)}"
    out = await llm.chat_json(FLASH_SYSTEM, prompt, FlashcardsOut, max_tokens=4000, temperature=0.3)
    cards = []
    seen = set()
    for c in out.cards:
        key = c.front.strip().lower()
        if not c.front.strip() or not c.back.strip() or key in seen:
            continue
        seen.add(key)
        cards.append({"id": uuid.uuid4().hex[:10], **c.model_dump(), "rating": None, "review_count": 0,
                      "last_reviewed_at": None})
    if not cards:
        raise ValueError("The AI returned no valid flashcards.")
    return cards
