"""Downloads with clear filenames, built from the stored content."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..core.database import get_db
from ..models.documents import oid, serialize
from ..services import export_service as ex
from ..utils.text import slugify
from .deps import get_owned_lecture

router = APIRouter(prefix="/api/lectures", tags=["exports"])

MIME = {
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "srt": "application/x-subrip; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _file(content: bytes | str, name: str, fmt: str) -> Response:
    body = content.encode("utf-8") if isinstance(content, str) else content
    return Response(body, media_type=MIME[fmt], headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})


async def _segments(lecture):
    return [s async for s in get_db().transcript_segments.find({"lecture_id": lecture["_id"]}, {"_id": 0}).sort("idx", 1)]


@router.get("/{lecture_id}/export/transcript")
async def export_transcript(format: str = Query("txt", pattern="^(txt|docx|srt)$"), timestamps: bool = True,
                            lecture: dict = Depends(get_owned_lecture)):
    segs = await _segments(lecture)
    if not segs:
        raise HTTPException(404, "No transcript yet.")
    name = f"{slugify(lecture['title'])}-transcript"
    if format == "docx":
        return _file(ex.transcript_docx(lecture, segs), name, "docx")
    if format == "srt":
        return _file(ex.transcript_srt(segs), name, "srt")
    return _file(ex.transcript_txt(lecture, segs, timestamps), name, "txt")


@router.get("/{lecture_id}/export/summary")
async def export_summary(format: str = Query("pdf", pattern="^(pdf|md|docx|txt)$"), lecture: dict = Depends(get_owned_lecture)):
    doc = await get_db().summaries.find_one({"lecture_id": lecture["_id"]})
    if not doc:
        raise HTTPException(404, "No summary yet.")
    md = ex.summary_markdown(lecture, doc)
    name = f"{slugify(lecture['title'])}-summary"
    if format == "pdf":
        return _file(ex.markdown_to_pdf(md, lecture["title"]), name, "pdf")
    if format == "docx":
        return _file(ex.markdown_to_docx(md, lecture["title"]), name, "docx")
    return _file(md, name, format)


@router.get("/{lecture_id}/export/notes")
async def export_notes(format: str = Query("pdf", pattern="^(pdf|md|docx|txt)$"), lecture: dict = Depends(get_owned_lecture)):
    doc = await get_db().study_notes.find_one({"lecture_id": lecture["_id"]})
    if not doc:
        raise HTTPException(404, "No notes yet.")
    md = doc["markdown"]
    name = f"{slugify(lecture['title'])}-notes"
    if format == "pdf":
        return _file(ex.markdown_to_pdf(md, lecture["title"]), name, "pdf")
    if format == "docx":
        return _file(ex.markdown_to_docx(md, lecture["title"]), name, "docx")
    if format == "txt":
        plain = md.replace("**", "").replace("`", "").replace("### ", "").replace("## ", "").replace("# ", "")
        return _file(plain, name, "txt")
    return _file(md, name, "md")


@router.get("/{lecture_id}/export/quiz")
async def export_quiz(format: str = Query("pdf", pattern="^(pdf|md|json|docx)$"), quiz_id: str | None = None,
                      answers: bool = True, lecture: dict = Depends(get_owned_lecture)):
    q = {"lecture_id": lecture["_id"]}
    if quiz_id:
        q["_id"] = oid(quiz_id)
    quiz = await get_db().quizzes.find_one(q, sort=[("created_at", -1)])
    if not quiz:
        raise HTTPException(404, "No quiz yet.")
    name = f"{slugify(lecture['title'])}-quiz"
    if format == "json":
        return _file(ex.to_json_bytes(serialize(quiz)), name, "json")
    md = ex.quiz_markdown(lecture, quiz, with_answers=answers)
    if format == "pdf":
        return _file(ex.markdown_to_pdf(md, quiz.get("title")), name, "pdf")
    if format == "docx":
        return _file(ex.markdown_to_docx(md, quiz.get("title")), name, "docx")
    return _file(md, name, "md")


@router.get("/{lecture_id}/export/flashcards")
async def export_flashcards(lecture: dict = Depends(get_owned_lecture)):
    doc = await get_db().flashcards.find_one({"lecture_id": lecture["_id"]})
    if not doc:
        raise HTTPException(404, "No flashcards yet.")
    return _file(ex.flashcards_csv(doc["cards"]), f"{slugify(lecture['title'])}-flashcards", "csv")


@router.get("/{lecture_id}/export/json")
async def export_json(lecture: dict = Depends(get_owned_lecture)):
    db = get_db()
    lid = lecture["_id"]
    summary = await db.summaries.find_one({"lecture_id": lid}, {"digests": 0, "reduced_digests": 0})
    data = {
        "lecture": serialize(lecture, drop=("media", "user_id", "job_id")),
        "transcript": await _segments(lecture),
        "summary": serialize(summary, drop=("user_id",)),
        "notes": serialize(await db.study_notes.find_one({"lecture_id": lid}), drop=("user_id",)),
        "knowledge_map": serialize(await db.knowledge_maps.find_one({"lecture_id": lid}), drop=("user_id",)),
        "quizzes": [serialize(q, drop=("user_id",)) async for q in db.quizzes.find({"lecture_id": lid})],
        "flashcards": serialize(await db.flashcards.find_one({"lecture_id": lid}), drop=("user_id",)),
    }
    for s in data["transcript"]:
        s.pop("lecture_id", None)
        s.pop("user_id", None)
    return _file(ex.to_json_bytes(serialize(data) or data), f"{slugify(lecture['title'])}-lecture-data", "json")
