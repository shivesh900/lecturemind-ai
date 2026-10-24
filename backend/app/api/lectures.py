"""Lecture upload, listing, metadata, deletion, reprocessing, status and media."""
from __future__ import annotations

import os
import re
import shutil

import aiofiles
from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from ..core.config import get_settings
from ..core.database import get_db
from ..models.documents import PIPELINE_STEPS, STEP_LABELS, new_steps, serialize, utcnow
from ..schemas.lecture import LectureUpdate
from ..services import audio_extractor
from ..services.storage_service import get_storage
from ..utils.files import FileValidationError, media_kind, validate_upload_meta
from ..utils.text import safe_display_filename
from ..workers.queue import create_job, job_queue
from .deps import get_current_user, get_owned_lecture

router = APIRouter(prefix="/api/lectures", tags=["lectures"])

LECTURE_CHILD_COLLECTIONS = ["transcript_segments", "transcript_chunks", "summaries", "study_notes", "quizzes",
                             "quiz_attempts", "flashcards", "knowledge_maps", "chat_messages", "processing_jobs", "content_safety"]


def public_lecture(doc: dict) -> dict:
    out = serialize(doc, drop=("media", "language_requested"))
    media = doc.get("media") or {}
    out["has_video"] = bool(media.get("has_video"))
    out["has_audio"] = bool(media.get("playback") or media.get("original"))
    out["original_filename"] = media.get("original_filename")
    out["file_size"] = media.get("size")
    out["steps_order"] = PIPELINE_STEPS
    out["step_labels"] = STEP_LABELS
    return out


@router.post("/upload", status_code=201)
async def upload_lecture(
    file: UploadFile = File(...),
    title: str | None = Form(default=None, max_length=200),
    subject: str | None = Form(default=None, max_length=100),
    description: str | None = Form(default=None, max_length=2000),
    language: str | None = Form(default="auto", max_length=10),
    user: dict = Depends(get_current_user),
):
    s = get_settings()
    storage = get_storage()
    try:
        ext = validate_upload_meta(file.filename or "", file.content_type, getattr(file, "size", None), s.max_upload_bytes)
    except FileValidationError as exc:
        raise HTTPException(exc.status_code, str(exc))
    if language and not re.fullmatch(r"auto|[a-z]{2,3}", language):
        raise HTTPException(422, "language must be 'auto' or an ISO code like 'en'.")

    # stream to a temp file, enforcing the size limit while reading
    tmp = storage.new_tmp_path(ext)
    size = 0
    try:
        async with aiofiles.open(tmp, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > s.max_upload_bytes:
                    raise HTTPException(413, f"File is too large. Maximum size is {s.max_upload_mb} MB.")
                await out.write(chunk)
        if size == 0:
            raise HTTPException(400, "The file is empty.")
        # content sniffing: must parse as media and contain audio
        try:
            info = await audio_extractor.probe(tmp)
        except audio_extractor.AudioExtractionError as exc:
            raise HTTPException(415, str(exc))
        if not info.has_audio:
            raise HTTPException(415, "This file has no audio track to transcribe.")
    except Exception:
        storage.remove_quietly(tmp)
        raise

    lecture_id = ObjectId()
    ldir = storage.lecture_dir(str(user["_id"]), str(lecture_id))
    final = ldir / f"original{ext}"
    shutil.move(str(tmp), final)
    os.chmod(final, 0o600)

    display = safe_display_filename(file.filename or "lecture")
    now = utcnow()
    doc = {
        "_id": lecture_id,
        "user_id": user["_id"],
        "title": (title or "").strip() or os.path.splitext(display)[0].replace("_", " ")[:200],
        "subject": (subject or "").strip() or None,
        "description": (description or "").strip() or None,
        "tags": [],
        "status": "queued",
        "progress": 0,
        "current_step": None,
        "steps": new_steps(),
        "error": None,
        "duration": round(info.duration, 2),
        "language": None,
        "language_requested": None if language in (None, "", "auto") else language,
        "kind": media_kind(ext, info.has_video),
        "media": {"original": storage.relpath(final), "original_filename": display, "size": size,
                  "has_video": info.has_video, "format": info.format_name},
        "created_at": now,
        "updated_at": now,
    }
    await get_db().lectures.insert_one(doc)
    await get_db().activity.insert_one({"user_id": user["_id"], "type": "lecture_uploaded", "lecture_id": lecture_id,
                                        "created_at": now})
    job_id = await create_job(get_db(), doc)
    await job_queue.enqueue(job_id)
    fresh = await get_db().lectures.find_one({"_id": lecture_id})
    return {"lecture": public_lecture(fresh), "job_id": str(job_id)}


@router.get("")
async def list_lectures(
    q: str | None = Query(default=None, max_length=200),
    subject: str | None = Query(default=None, max_length=100),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(queued|processing|completed|failed)$"),
    date_from: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    sort: str = Query(default="newest", pattern="^(newest|oldest|title)$"),
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    import datetime as dt

    query: dict = {"user_id": user["_id"]}
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"title": rx}, {"subject": rx}, {"description": rx}]
    if subject:
        query["subject"] = subject
    if status_filter:
        query["status"] = status_filter
    if date_from or date_to:
        rng = {}
        if date_from:
            rng["$gte"] = dt.datetime.fromisoformat(date_from).replace(tzinfo=dt.timezone.utc)
        if date_to:
            rng["$lt"] = dt.datetime.fromisoformat(date_to).replace(tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
        query["created_at"] = rng
    order = {"newest": [("created_at", -1)], "oldest": [("created_at", 1)], "title": [("title", 1)]}[sort]
    db = get_db()
    items = [public_lecture(d) async for d in db.lectures.find(query).sort(order).limit(limit)]
    subjects = sorted({d.get("subject") async for d in db.lectures.find({"user_id": user["_id"]}, {"subject": 1}) if d.get("subject")})
    return {"items": items, "total": len(items), "subjects": subjects}


@router.get("/{lecture_id}")
async def get_lecture(lecture: dict = Depends(get_owned_lecture)):
    db = get_db()
    lid = lecture["_id"]
    out = public_lecture(lecture)
    out["available"] = {
        "transcript": await db.transcript_segments.count_documents({"lecture_id": lid}, limit=1) > 0,
        "summary": await db.summaries.count_documents({"lecture_id": lid}, limit=1) > 0,
        "notes": await db.study_notes.count_documents({"lecture_id": lid}, limit=1) > 0,
        "quiz": await db.quizzes.count_documents({"lecture_id": lid}, limit=1) > 0,
        "flashcards": await db.flashcards.count_documents({"lecture_id": lid}, limit=1) > 0,
        "knowledge_map": await db.knowledge_maps.count_documents({"lecture_id": lid}, limit=1) > 0,
        "safety": await db.content_safety.count_documents({"lecture_id": lid}, limit=1) > 0,
    }
    return {"lecture": out}


@router.patch("/{lecture_id}")
async def update_lecture(body: LectureUpdate, lecture: dict = Depends(get_owned_lecture)):
    upd = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump(exclude_unset=True).items()}
    if "title" in upd and not upd["title"]:
        raise HTTPException(422, "title cannot be empty.")
    if "tags" in upd and upd["tags"] is not None:
        upd["tags"] = [t.strip()[:30] for t in upd["tags"] if t.strip()]
    upd["updated_at"] = utcnow()
    await get_db().lectures.update_one({"_id": lecture["_id"]}, {"$set": upd})
    return {"lecture": public_lecture(await get_db().lectures.find_one({"_id": lecture["_id"]}))}


@router.delete("/{lecture_id}")
async def delete_lecture(lecture: dict = Depends(get_owned_lecture)):
    db = get_db()
    lid = lecture["_id"]
    for c in LECTURE_CHILD_COLLECTIONS:
        await db[c].delete_many({"lecture_id": lid})
    await db.activity.delete_many({"lecture_id": lid})
    await db.lectures.delete_one({"_id": lid})
    get_storage().delete_lecture(str(lecture["user_id"]), str(lid))
    return {"ok": True}


@router.post("/{lecture_id}/reprocess", status_code=202)
async def reprocess_lecture(full: bool = False, lecture: dict = Depends(get_owned_lecture)):
    if lecture.get("status") in ("queued", "processing"):
        raise HTTPException(409, "This lecture is already being processed.")
    steps = lecture.get("steps") or new_steps()
    if full:
        reset = PIPELINE_STEPS
    else:
        # resume from the first step that did not complete
        reset = [s for s in PIPELINE_STEPS if steps.get(s, {}).get("status") not in ("completed", "skipped")]
        if not reset:
            # regenerate study materials (and re-run the content-safety scan)
            reset = ["content_safety"] + PIPELINE_STEPS[PIPELINE_STEPS.index("summary"):]
    job_id = await create_job(get_db(), lecture, reset_steps=reset)
    await job_queue.enqueue(job_id)
    return {"ok": True, "job_id": str(job_id), "reset_steps": reset}


@router.get("/{lecture_id}/status")
async def lecture_status(lecture: dict = Depends(get_owned_lecture)):
    job = None
    if lecture.get("job_id"):
        job = serialize(await get_db().processing_jobs.find_one({"_id": lecture["job_id"]}))
    return {
        "id": str(lecture["_id"]),
        "status": lecture.get("status"),
        "progress": lecture.get("progress", 0),
        "current_step": lecture.get("current_step"),
        "current_step_label": lecture.get("current_step_label"),
        "current_step_progress": lecture.get("current_step_progress"),
        "steps": serialize(lecture.get("steps") or {}),
        "steps_order": PIPELINE_STEPS,
        "step_labels": STEP_LABELS,
        "error": lecture.get("error"),
        "job": job,
    }


@router.get("/{lecture_id}/media")
async def lecture_media(lecture: dict = Depends(get_owned_lecture)):
    media = lecture.get("media") or {}
    storage = get_storage()
    for key, mime in (("playback", "audio/mp4"), ("original", None)):
        rel = media.get(key)
        if rel:
            path = storage.resolve(rel)
            if path.exists():
                return FileResponse(path, media_type=mime, headers={"Cache-Control": "private, max-age=3600"})
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Audio is not available for this lecture yet.")
