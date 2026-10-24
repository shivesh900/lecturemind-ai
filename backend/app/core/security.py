"""Password hashing (bcrypt) and JWT session tokens."""
from __future__ import annotations

import datetime as dt

import bcrypt
import jwt

from .config import get_settings


def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes; we reject longer passwords at the schema level.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, token_version: int = 0) -> str:
    s = get_settings()
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": user_id,
        "tv": token_version,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(minutes=s.access_token_minutes)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_access_token(token: str) -> dict | None:
    s = get_settings()
    try:
        data = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    if data.get("typ") != "access":
        return None
    return data
