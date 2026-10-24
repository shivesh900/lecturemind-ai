from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required")
        return v

    @field_validator("password")
    @classmethod
    def _strength(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password is too long (max 72 bytes)")
        if v.isdigit() or v.isalpha():
            raise ValueError("Use a mix of letters and numbers")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class Preferences(BaseModel):
    theme: Literal["dark", "light", "system"] = "dark"
    default_language: str = Field(default="auto", max_length=10)
    note_style: Literal["concise", "detailed", "exam"] = "exam"


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    preferences: Preferences | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=72)


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)
