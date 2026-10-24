from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LectureUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    subject: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    tags: list[str] | None = Field(default=None, max_length=20)


class SegmentEdit(BaseModel):
    idx: int = Field(ge=0)
    text: str = Field(max_length=5000)


class TranscriptUpdate(BaseModel):
    segments: list[SegmentEdit] = Field(min_length=1, max_length=5000)


class NotesUpdate(BaseModel):
    markdown: str = Field(max_length=500_000)


class GenerateRequest(BaseModel):
    style: Literal["concise", "detailed", "exam"] | None = None


class QuizGenerateRequest(BaseModel):
    difficulty: Literal["easy", "medium", "hard", "mixed"] = "mixed"
    num_mcq: int = Field(default=6, ge=0, le=20)
    num_true_false: int = Field(default=3, ge=0, le=10)
    num_short: int = Field(default=2, ge=0, le=10)
    num_long: int = Field(default=1, ge=0, le=5)


class QuizAttemptRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)
    self_marks: dict[str, bool] = Field(default_factory=dict)
    duration_seconds: int | None = Field(default=None, ge=0, le=60 * 60 * 10)


class FlashcardReview(BaseModel):
    rating: Literal["easy", "medium", "hard"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
