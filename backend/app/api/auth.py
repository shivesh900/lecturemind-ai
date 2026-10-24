"""Authentication: register, login, logout, me.

Sessions are JWTs delivered as an httpOnly, SameSite cookie (not readable by
JavaScript). A Bearer header is also accepted for API clients and tests.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pymongo.errors import DuplicateKeyError

from ..core.config import get_settings
from ..core.database import get_db
from ..core.security import create_access_token, hash_password, verify_password
from ..models.documents import serialize, utcnow
from ..schemas.auth import LoginRequest, Preferences, RegisterRequest
from .deps import auth_rate_limit, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def public_user(user: dict) -> dict:
    u = serialize(user, drop=("password_hash", "token_version"))
    u["preferences"] = {**Preferences().model_dump(), **(user.get("preferences") or {})}
    return u


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(s.cookie_name, token, httponly=True, secure=s.cookie_secure, samesite=s.cookie_samesite,
                        max_age=s.access_token_minutes * 60, path="/")


@router.post("/register", status_code=201, dependencies=[Depends(auth_rate_limit)])
async def register(body: RegisterRequest, response: Response):
    db = get_db()
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    now = utcnow()
    doc = {"name": body.name, "email": email, "password_hash": hash_password(body.password), "token_version": 0,
           "preferences": Preferences().model_dump(), "created_at": now, "updated_at": now}
    try:
        res = await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists.")
    doc["_id"] = res.inserted_id
    token = create_access_token(str(res.inserted_id), 0)
    _set_cookie(response, token)
    return {"user": public_user(doc), "access_token": token, "token_type": "bearer"}


@router.post("/login", dependencies=[Depends(auth_rate_limit)])
async def login(body: LoginRequest, response: Response):
    user = await get_db().users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    token = create_access_token(str(user["_id"]), user.get("token_version", 0))
    _set_cookie(response, token)
    await get_db().users.update_one({"_id": user["_id"]}, {"$set": {"last_login_at": utcnow()}})
    return {"user": public_user(user), "access_token": token, "token_type": "bearer"}


@router.post("/logout")
async def logout(response: Response, all_devices: bool = False, user: dict = Depends(get_current_user)):
    if all_devices:
        await get_db().users.update_one({"_id": user["_id"]}, {"$inc": {"token_version": 1}})
    s = get_settings()
    response.delete_cookie(s.cookie_name, path="/", samesite=s.cookie_samesite, secure=s.cookie_secure)
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": public_user(user)}
