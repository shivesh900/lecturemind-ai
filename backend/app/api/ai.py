"""AI study materials: summary, notes, knowledge map, quizzes (+ attempts),
flashcards (+ reviews) and grounded chat. Every route is ownership-checked and
the generation routes are rate-limited per user."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..core.config import get_settings
from ..core.database import get_db
from ..models.documents import oid, serialize, utcnow
from ..schemas.lecture import ChatRequest, FlashcardReview, GenerateRequest, NotesUpdate, QuizAttemptRequest, QuizGenerateRequest
from ..services import demo_extractor, lecture_chat_service
from ..services.flashcard_generator import generate_flashcards
from ..services.llm_client import LLMError
from ..services.quiz_generator import generate_quiz
from ..workers.queue import create_job, job_queue
from .deps import ai_rate_limit, get_current_user, get_owned_lecture

router = APIRouter(prefix="/api", tags=["ai"])


def _require_transcript(lecture: dict):
    steps = lecture.get("steps") or {}
    if steps.get("process_transcript", {}).get("status") != "completed":
        raise HTTPException(409, "The transcript is not ready yet. Wait for transcription to finish.")


def _not_busy(lecture: dict):
    if lecture.get("status") in ("queued", "processing"):
        raise HTTPException(409, "This lecture is still processing. Try again when it finishes.")


async def _get_or_404(coll: str, lecture: dict, what: str):
    doc = await get_db()[coll].find_one({"lecture_id": lecture["_id"]})
    if not doc:
        raise HTTPException(404, f"No {what} yet for this lecture.")
    return doc


async def _rerun_steps(lecture: dict, steps: list[str]) -> dict:
    _require_transcript(lecture)
    _not_busy(lecture)
    job_id = await create_job(get_db(), lecture, reset_steps=steps)
    await job_queue.enqueue(job_id)
    return {"ok": True, "queued": True, "job_id": str(job_id), "steps": steps}


async def _digests(lecture: dict) -> list[dict]:
    doc = await get_db().summaries.find_one({"lecture_id": lecture["_id"]})
    if not doc or not (doc.get("reduced_digests") or doc.get("digests")):
        raise HTTPException(409, "Generate the summary first.")
    return doc.get("reduced_digests") or doc["digests"]


async def _demo(lecture: dict) -> dict:
    db = get_db()
    segs = [s async for s in db.transcript_segments.find({"lecture_id": lecture["_id"]}, {"_id": 0}).sort("idx", 1)]
    chunks = [c async for c in db.transcript_chunks.find({"lecture_id": lecture["_id"]}, {"_id": 0, "embedding": 0}).sort("idx", 1)]
    return demo_extractor.build_demo_outputs({"title": lecture.get("title"), "subject": lecture.get("subject")}, segs, chunks)


def _meta(lecture: dict) -> dict:
    return {k: lecture.get(k) for k in ("title", "subject", "description")}


# ------------------------------------------------------------------ summary
@router.get("/lectures/{lecture_id}/summary")
async def get_summary(lecture: dict = Depends(get_owned_lecture)):
    doc = await _get_or_404("summaries", lecture, "summary")
    return serialize(doc, drop=("digests", "reduced_digests"))


@router.post("/lectures/{lecture_id}/summary", status_code=202)
async def regenerate_summary(lecture: dict = Depends(get_owned_lecture), _=Depends(ai_rate_limit)):
    return await _rerun_steps(lecture, ["summary", "notes", "knowledge_map", "quiz", "flashcards"])


# ------------------------------------------------------------------ notes
@router.get("/lectures/{lecture_id}/notes")
async def get_notes(lecture: dict = Depends(get_owned_lecture)):
    return serialize(await _get_or_404("study_notes", lecture, "notes"))


@router.post("/lectures/{lecture_id}/notes", status_code=202)
async def regenerate_notes(body: GenerateRequest | None = None, lecture: dict = Depends(get_owned_lecture),
                           user=Depends(ai_rate_limit)):
    if body and body.style:
        await get_db().users.update_one({"_id": user["_id"]}, {"$set": {"preferences.note_style": body.style}})
    return await _rerun_steps(lecture, ["notes"])


@router.patch("/lectures/{lecture_id}/notes")
async def save_notes(body: NotesUpdate, lecture: dict = Depends(get_owned_lecture)):
    db = get_db()
    await _get_or_404("study_notes", lecture, "notes")
    await db.study_notes.update_one({"lecture_id": lecture["_id"]},
                                    {"$set": {"markdown": body.markdown, "edited": True, "updated_at": utcnow()}})
    await db.activity.insert_one({"user_id": lecture["user_id"], "type": "notes_edited", "lecture_id": lecture["_id"],
                                  "created_at": utcnow()})
    return serialize(await db.study_notes.find_one({"lecture_id": lecture["_id"]}))


# ------------------------------------------------------------------ knowledge map
@router.get("/lectures/{lecture_id}/knowledge-map")
async def get_knowledge_map(lecture: dict = Depends(get_owned_lecture)):
    return serialize(await _get_or_404("knowledge_maps", lecture, "knowledge map"))


@router.post("/lectures/{lecture_id}/knowledge-map", status_code=202)
async def regenerate_knowledge_map(lecture: dict = Depends(get_owned_lecture), _=Depends(ai_rate_limit)):
    return await _rerun_steps(lecture, ["knowledge_map"])


# ------------------------------------------------------------------ quizzes
def _quiz_public(q: dict) -> dict:
    return serialize(q)


@router.get("/lectures/{lecture_id}/quizzes")
async def list_quizzes(lecture: dict = Depends(get_owned_lecture)):
    db = get_db()
    quizzes = [_quiz_public(q) async for q in db.quizzes.find({"lecture_id": lecture["_id"]}).sort("created_at", -1)]
    attempts = [serialize(a, drop=("results",)) async for a in
                db.quiz_attempts.find({"lecture_id": lecture["_id"]}).sort("created_at", -1).limit(50)]
    return {"quizzes": quizzes, "attempts": attempts}


@router.post("/lectures/{lecture_id}/quiz", status_code=201)
async def create_quiz(body: QuizGenerateRequest, lecture: dict = Depends(get_owned_lecture), _=Depends(ai_rate_limit)):
    _require_transcript(lecture)
    if body.num_mcq + body.num_true_false + body.num_short + body.num_long == 0:
        raise HTTPException(422, "Ask for at least one question.")
    if get_settings().ai_enabled:
        try:
            quiz = await generate_quiz(await _digests(lecture), _meta(lecture), body.difficulty, body.num_mcq,
                                       body.num_true_false, body.num_short, body.num_long)
        except (LLMError, ValueError) as exc:
            raise HTTPException(502, f"Quiz generation failed: {exc}")
        mode = "ai"
    else:
        quiz = (await _demo(lecture))["quiz"]
        mode = "demo"
    now = utcnow()
    doc = {"lecture_id": lecture["_id"], "user_id": lecture["user_id"], "title": quiz["title"],
           "questions": quiz["questions"], "difficulty": body.difficulty, "source": "user", "mode": mode,
           "created_at": now, "updated_at": now}
    res = await get_db().quizzes.insert_one(doc)
    doc["_id"] = res.inserted_id
    return _quiz_public(doc)


async def _owned_quiz(quiz_id: str, user: dict) -> dict:
    qid = oid(quiz_id)
    quiz = await get_db().quizzes.find_one({"_id": qid, "user_id": user["_id"]}) if qid else None
    if not quiz:
        raise HTTPException(404, "Quiz not found.")
    return quiz


@router.get("/quizzes/{quiz_id}")
async def get_quiz(quiz_id: str, user: dict = Depends(get_current_user)):
    return _quiz_public(await _owned_quiz(quiz_id, user))


@router.delete("/quizzes/{quiz_id}")
async def delete_quiz(quiz_id: str, user: dict = Depends(get_current_user)):
    quiz = await _owned_quiz(quiz_id, user)
    await get_db().quizzes.delete_one({"_id": quiz["_id"]})
    await get_db().quiz_attempts.delete_many({"quiz_id": quiz["_id"]})
    return {"ok": True}


def grade(quiz: dict, body: QuizAttemptRequest) -> dict:
    results, correct, gradable = [], 0, 0
    for q in quiz["questions"]:
        given = (body.answers.get(q["id"]) or "").strip()
        if q["type"] in ("mcq", "true_false"):
            ok = bool(given) and given.lower() == q["correct_answer"].strip().lower()
            gradable += 1
            correct += ok
        else:
            mark = body.self_marks.get(q["id"])
            ok = bool(mark) if mark is not None else None
            if mark is not None:
                gradable += 1
                correct += bool(mark)
        results.append({"question_id": q["id"], "type": q["type"], "given": given, "correct": ok,
                        "correct_answer": q["correct_answer"], "explanation": q.get("explanation", "")})
    score = round(100 * correct / gradable, 1) if gradable else 0.0
    return {"results": results, "correct": correct, "gradable": gradable, "total": len(quiz["questions"]), "score": score}


@router.post("/quizzes/{quiz_id}/attempts", status_code=201)
async def submit_attempt(quiz_id: str, body: QuizAttemptRequest, user: dict = Depends(get_current_user)):
    quiz = await _owned_quiz(quiz_id, user)
    g = grade(quiz, body)
    now = utcnow()
    doc = {"quiz_id": quiz["_id"], "lecture_id": quiz["lecture_id"], "user_id": user["_id"], **g,
           "duration_seconds": body.duration_seconds, "created_at": now}
    res = await get_db().quiz_attempts.insert_one(doc)
    await get_db().activity.insert_one({"user_id": user["_id"], "type": "quiz_attempt", "lecture_id": quiz["lecture_id"],
                                        "score": g["score"], "created_at": now})
    doc["_id"] = res.inserted_id
    return serialize(doc)


@router.get("/quizzes/{quiz_id}/attempts")
async def list_attempts(quiz_id: str, user: dict = Depends(get_current_user)):
    quiz = await _owned_quiz(quiz_id, user)
    items = [serialize(a) async for a in get_db().quiz_attempts.find({"quiz_id": quiz["_id"]}).sort("created_at", -1)]
    return {"attempts": items}


@router.get("/attempts")
async def all_attempts(user: dict = Depends(get_current_user)):
    db = get_db()
    titles = {d["_id"]: d["title"] async for d in db.lectures.find({"user_id": user["_id"]}, {"title": 1})}
    items = []
    async for a in db.quiz_attempts.find({"user_id": user["_id"]}, {"results": 0}).sort("created_at", -1).limit(200):
        x = serialize(a)
        x["lecture_title"] = titles.get(a["lecture_id"], "Deleted lecture")
        items.append(x)
    return {"attempts": items}


# ------------------------------------------------------------------ flashcards
@router.get("/lectures/{lecture_id}/flashcards")
async def get_flashcards(lecture: dict = Depends(get_owned_lecture)):
    return serialize(await _get_or_404("flashcards", lecture, "flashcards"))


@router.post("/lectures/{lecture_id}/flashcards")
async def regenerate_flashcards(lecture: dict = Depends(get_owned_lecture), _=Depends(ai_rate_limit)):
    _require_transcript(lecture)
    if get_settings().ai_enabled:
        try:
            cards = await generate_flashcards(await _digests(lecture), _meta(lecture))
        except (LLMError, ValueError) as exc:
            raise HTTPException(502, f"Flashcard generation failed: {exc}")
        mode = "ai"
    else:
        cards, mode = (await _demo(lecture))["flashcards"], "demo"
    now = utcnow()
    await get_db().flashcards.update_one(
        {"lecture_id": lecture["_id"]},
        {"$set": {"lecture_id": lecture["_id"], "user_id": lecture["user_id"], "cards": cards, "mode": mode,
                  "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)
    return serialize(await get_db().flashcards.find_one({"lecture_id": lecture["_id"]}))


@router.post("/lectures/{lecture_id}/flashcards/{card_id}/review")
async def review_card(card_id: str, body: FlashcardReview, lecture: dict = Depends(get_owned_lecture)):
    db = get_db()
    doc = await _get_or_404("flashcards", lecture, "flashcards")
    if not any(c["id"] == card_id for c in doc["cards"]):
        raise HTTPException(404, "Card not found.")
    now = utcnow()
    cards = []
    for c in doc["cards"]:
        if c["id"] == card_id:
            c = {**c, "rating": body.rating, "review_count": c.get("review_count", 0) + 1, "last_reviewed_at": now}
        cards.append(c)
    await db.flashcards.update_one({"_id": doc["_id"]}, {"$set": {"cards": cards, "updated_at": now}})
    await db.activity.insert_one({"user_id": lecture["user_id"], "type": "flashcard_review", "lecture_id": lecture["_id"],
                                  "rating": body.rating, "created_at": now})
    return {"ok": True, "card": serialize(next(c for c in cards if c["id"] == card_id))}


# ------------------------------------------------------------------ chat
@router.get("/lectures/{lecture_id}/chat")
async def chat_history(lecture: dict = Depends(get_owned_lecture)):
    msgs = [serialize(m) async for m in get_db().chat_messages.find({"lecture_id": lecture["_id"]}).sort("created_at", 1).limit(200)]
    return {"messages": msgs}


@router.delete("/lectures/{lecture_id}/chat")
async def clear_chat(lecture: dict = Depends(get_owned_lecture)):
    await get_db().chat_messages.delete_many({"lecture_id": lecture["_id"]})
    return {"ok": True}


@router.post("/lectures/{lecture_id}/chat")
async def chat(body: ChatRequest, lecture: dict = Depends(get_owned_lecture), _=Depends(ai_rate_limit)):
    _require_transcript(lecture)
    db = get_db()
    history = [m async for m in db.chat_messages.find({"lecture_id": lecture["_id"]}).sort("created_at", -1).limit(6)][::-1]
    try:
        result = await lecture_chat_service.answer(db, lecture, body.message.strip(), history)
    except LLMError as exc:
        raise HTTPException(502, f"The AI service failed to answer: {exc}")
    now = utcnow()
    user_msg = {"lecture_id": lecture["_id"], "user_id": lecture["user_id"], "role": "user", "content": body.message.strip(),
                "created_at": now}
    await db.chat_messages.insert_one(user_msg)
    bot = {"lecture_id": lecture["_id"], "user_id": lecture["user_id"], "role": "assistant", "content": result["answer"],
           "supported": result["supported"], "citations": result["citations"], "mode": result["mode"],
           "retrieval": result["retrieval"], "created_at": utcnow()}
    await db.chat_messages.insert_one(bot)
    await db.activity.insert_one({"user_id": lecture["user_id"], "type": "chat_message", "lecture_id": lecture["_id"],
                                  "created_at": now})
    return {"user_message": serialize(user_msg), "message": serialize(bot)}
