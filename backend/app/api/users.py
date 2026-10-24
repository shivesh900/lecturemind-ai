"""Profile, preferences, password and data-deletion controls."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..core.config import get_settings
from ..core.database import get_db
from ..core.security import hash_password, verify_password
from ..models.documents import utcnow
from ..schemas.auth import DeleteAccountRequest, PasswordChange, UserUpdate
from ..services.storage_service import get_storage
from .auth import public_user
from .deps import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])

USER_COLLECTIONS = ["lectures", "transcript_segments", "transcript_chunks", "summaries", "study_notes", "quizzes",
                    "quiz_attempts", "flashcards", "knowledge_maps", "chat_messages", "processing_jobs", "activity"]


@router.patch("/me")
async def update_me(body: UserUpdate, user: dict = Depends(get_current_user)):
    upd = {"updated_at": utcnow()}
    if body.name is not None:
        upd["name"] = body.name.strip()
    if body.preferences is not None:
        upd["preferences"] = body.preferences.model_dump()
    await get_db().users.update_one({"_id": user["_id"]}, {"$set": upd})
    return {"user": public_user(await get_db().users.find_one({"_id": user["_id"]}))}


@router.post("/me/password")
async def change_password(body: PasswordChange, response: Response, user: dict = Depends(get_current_user)):
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.")
    await get_db().users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": hash_password(body.new_password)},
                                                            "$inc": {"token_version": 1}})
    response.delete_cookie(get_settings().cookie_name, path="/")
    return {"ok": True, "message": "Password changed. Please sign in again."}


async def delete_user_content(user_id) -> dict:
    db = get_db()
    counts = {}
    for c in USER_COLLECTIONS:
        res = await db[c].delete_many({"user_id": user_id})
        counts[c] = res.deleted_count
    get_storage().delete_user(str(user_id))
    return counts


@router.delete("/me/data")
async def delete_my_data(user: dict = Depends(get_current_user)):
    counts = await delete_user_content(user["_id"])
    return {"ok": True, "deleted": counts}


@router.delete("/me")
async def delete_account(body: DeleteAccountRequest, response: Response, user: dict = Depends(get_current_user)):
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Password is incorrect.")
    await delete_user_content(user["_id"])
    await get_db().users.delete_one({"_id": user["_id"]})
    response.delete_cookie(get_settings().cookie_name, path="/")
    return {"ok": True}
