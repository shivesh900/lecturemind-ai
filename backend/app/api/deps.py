"""Shared FastAPI dependencies: current user, owned lecture lookup, rate limits."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from ..core.config import get_settings
from ..core.database import get_db
from ..core.rate_limit import limiter
from ..core.security import decode_access_token
from ..models.documents import oid


def _token_from_request(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(get_settings().cookie_name)


async def get_current_user(request: Request) -> dict:
    token = _token_from_request(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated.")
    data = decode_access_token(token)
    if not data:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid. Please sign in again.")
    uid = oid(data.get("sub"))
    user = await get_db().users.find_one({"_id": uid}) if uid else None
    if not user or user.get("token_version", 0) != data.get("tv", 0):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid. Please sign in again.")
    return user


async def get_owned_lecture(lecture_id: str, user: dict = Depends(get_current_user)) -> dict:
    """Ownership check used by EVERY lecture-scoped endpoint.

    A lecture that exists but belongs to someone else returns 404 (not 403) so the
    API does not reveal which ids exist.
    """
    lid = oid(lecture_id)
    if lid is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lecture not found.")
    lecture = await get_db().lectures.find_one({"_id": lid, "user_id": user["_id"]})
    if not lecture:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lecture not found.")
    return lecture


def ai_rate_limit(user: dict = Depends(get_current_user)) -> dict:
    limiter.check(f"ai:{user['_id']}", get_settings().ai_rate_limit_per_minute)
    return user


def auth_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    limiter.check(f"auth:{ip}", get_settings().auth_rate_limit_per_minute)
