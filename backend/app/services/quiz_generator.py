"""Quiz generation (MCQ / true-false / short / long) from lecture digests, with
post-validation (4 options per MCQ, correct answer must be one of them)."""
from __future__ import annotations

import random
import re
import uuid

from ..schemas.ai import QuizOut, QuizQuestion
from .llm_client import get_llm_client
from .summarization_service import GROUNDING, digests_context, meta_header

QUIZ_SYSTEM = (
    "You are a university examiner writing questions strictly from a lecture. Every question must be answerable from "
    "the lecture digests provided; never ask about anything not covered. MCQs have exactly 4 plausible options with one "
    "correct answer (correct_answer = exact option text). True/false options are ['True','False']. Short-answer model "
    "answers are 1-3 sentences; long-answer model answers are a structured paragraph. Every question needs an "
    "explanation that references the lecture. Mark likely exam questions with important=true. Set chunk_index to the "
    "Part the question comes from. " + GROUNDING
)


def _difficulty_hint(d: str) -> str:
    return {
        "easy": "All questions EASY (recall of definitions and facts).",
        "medium": "All questions MEDIUM (understanding and application).",
        "hard": "All questions HARD (analysis, comparison, multi-step reasoning) but still answerable from the lecture.",
    }.get(d, "Mix difficulties: about one third each of easy, medium and hard, with difficulty set on each question.")


def normalize_question(q: QuizQuestion) -> QuizQuestion | None:
    q.question = q.question.strip()
    if not q.question:
        return None
    if q.type == "mcq":
        opts = [re.sub(r"^\s*[A-Da-d][\).:]\s+", "", o).strip() for o in q.options if o and o.strip()]
        opts = list(dict.fromkeys(opts))
        ans = re.sub(r"^\s*[A-Da-d][\).:]\s+", "", q.correct_answer or "").strip()
        if len(ans) == 1 and ans.upper() in "ABCD" and len(opts) >= "ABCD".index(ans.upper()) + 1:
            ans = opts["ABCD".index(ans.upper())]
        match = next((o for o in opts if o.lower() == ans.lower()), None)
        if match is None or len(opts) < 4:
            return None
        others = [o for o in opts if o != match][:3]
        opts = others + [match]
        random.shuffle(opts)  # models tend to put the right answer first
        q.options, q.correct_answer = opts, match
    elif q.type == "true_false":
        a = (q.correct_answer or "").strip().lower()
        if a not in ("true", "false"):
            return None
        q.options, q.correct_answer = ["True", "False"], a.capitalize()
    else:
        q.options = []
    return q


def finalize_questions(questions: list[QuizQuestion]) -> list[dict]:
    out = []
    for q in questions:
        nq = normalize_question(q)
        if nq is not None:
            out.append({"id": uuid.uuid4().hex[:10], **nq.model_dump()})
    return out


async def generate_quiz(digests: list[dict], meta: dict, difficulty: str = "mixed", num_mcq: int = 6,
                        num_true_false: int = 3, num_short: int = 2, num_long: int = 1) -> dict:
    llm = get_llm_client()
    prompt = (
        f"{meta_header(meta)}\nWrite {num_mcq} mcq, {num_true_false} true_false, {num_short} short and {num_long} long "
        f"questions. {_difficulty_hint(difficulty)} Spread questions across all parts of the lecture.\n\n"
        f"LECTURE DIGESTS:\n\n{digests_context(digests)}"
    )
    quiz = await llm.chat_json(QUIZ_SYSTEM, prompt, QuizOut, max_tokens=6000, temperature=0.4)
    questions = finalize_questions(quiz.questions)
    if not questions:
        raise ValueError("The AI returned no valid questions.")
    return {"title": quiz.title or f"{meta.get('title', 'Lecture')} quiz", "questions": questions}
