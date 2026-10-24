"""Schemas for every structured AI output.

The LLM is asked to return JSON matching these models; responses are validated
with pydantic and retried once with the validation error if they do not match.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Definition(BaseModel):
    term: str
    definition: str


class Formula(BaseModel):
    expression: str
    meaning: str = ""


class ChunkDigest(BaseModel):
    """Map step: one per transcript chunk."""
    title: str = Field(description="Short topic title for this part of the lecture")
    summary: str = Field(description="3-5 sentence summary of only this part")
    key_points: list[str] = Field(default_factory=list)
    definitions: list[Definition] = Field(default_factory=list)
    formulas: list[Formula] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list, description="Key concepts/terms mentioned")
    entities: list[str] = Field(default_factory=list, description="People, organisations, dates, events named")


class SummarySection(BaseModel):
    heading: str
    content: str


class Topic(BaseModel):
    title: str
    description: str = ""
    chunk_index: int | None = None


class LectureSummary(BaseModel):
    """Reduce step: combines all chunk digests."""
    executive_summary: str
    quick_summary: list[str] = Field(description="Exactly five short lines")
    detailed_summary: list[SummarySection]
    main_topics: list[Topic] = Field(default_factory=list)
    arguments: list[str] = Field(default_factory=list, description="Important arguments and explanations")
    key_takeaways: list[str] = Field(default_factory=list)
    definitions: list[Definition] = Field(default_factory=list)
    formulas: list[Formula] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)

    @field_validator("quick_summary")
    @classmethod
    def _five(cls, v: list[str]) -> list[str]:
        return [x for x in v if x.strip()][:5]


class NoteSubsection(BaseModel):
    heading: str
    bullets: list[str] = Field(default_factory=list)


class NoteSection(BaseModel):
    heading: str
    chunk_index: int | None = None
    overview: str = ""
    bullets: list[str] = Field(default_factory=list)
    subsections: list[NoteSubsection] = Field(default_factory=list)
    definitions: list[Definition] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list, description="Step-by-step explanation, if any")
    formulas: list[Formula] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    advantages: list[str] = Field(default_factory=list)
    disadvantages: list[str] = Field(default_factory=list)


class StudyNotesOut(BaseModel):
    title: str
    subject: str = ""
    sections: list[NoteSection]
    terminology: list[Definition] = Field(default_factory=list)
    names_and_dates: list[str] = Field(default_factory=list)
    revision_summary: list[str] = Field(default_factory=list)


NodeType = Literal["topic", "subtopic", "concept", "definition", "entity", "date", "formula", "keyword"]


class KnowledgeNode(BaseModel):
    id: str
    label: str
    type: NodeType = "concept"
    description: str = ""
    chunk_index: int | None = None


class KnowledgeEdge(BaseModel):
    source: str
    target: str
    relation: str = "related to"


class KnowledgeMapOut(BaseModel):
    nodes: list[KnowledgeNode]
    edges: list[KnowledgeEdge] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


QuestionType = Literal["mcq", "true_false", "short", "long"]
Difficulty = Literal["easy", "medium", "hard"]


class QuizQuestion(BaseModel):
    type: QuestionType
    question: str
    options: list[str] = Field(default_factory=list, description="4 options for mcq, ['True','False'] for true_false, empty otherwise")
    correct_answer: str = Field(description="For mcq: the exact text of the correct option. For true_false: 'True' or 'False'. Otherwise a model answer.")
    explanation: str = ""
    difficulty: Difficulty = "medium"
    important: bool = Field(default=False, description="Likely exam question")
    chunk_index: int | None = None


class QuizOut(BaseModel):
    title: str = "Lecture quiz"
    questions: list[QuizQuestion]


class Flashcard(BaseModel):
    front: str
    back: str
    difficulty: Difficulty = "medium"
    chunk_index: int | None = None


class FlashcardsOut(BaseModel):
    cards: list[Flashcard]


class ChatAnswer(BaseModel):
    answer: str
    supported: bool = Field(description="False if the provided lecture excerpts do not contain enough information")
    cited_excerpts: list[int] = Field(default_factory=list, description="Numbers of the excerpts used, e.g. [1, 3]")
