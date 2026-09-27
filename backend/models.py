from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RecommendRequest(BaseModel):
    sentence: str
    mode: Literal["Creative", "Academic", "Professional"]

    @field_validator("sentence")
    @classmethod
    def require_blank(cls, sentence: str) -> str:
        sentence = sentence.strip()
        if "____" not in sentence:
            raise ValueError("Your sentence must contain ____ where the word should go.")
        return sentence


class Candidate(BaseModel):
    # Reject unexpected fields, including any model-generated final fit_score.
    model_config = ConfigDict(extra="forbid")

    word: str = Field(min_length=1, max_length=60)
    context_score: int = Field(strict=True, ge=0, le=100)
    grammar_score: int = Field(strict=True, ge=0, le=100)
    style_score: int = Field(strict=True, ge=0, le=100)
    explanation: str = Field(min_length=1, max_length=240)

    @field_validator("word")
    @classmethod
    def require_single_word(cls, word: str) -> str:
        word = word.strip()
        if not word or any(character.isspace() for character in word):
            raise ValueError("Each candidate must be a single word.")
        return word

    @field_validator("explanation")
    @classmethod
    def require_explanation(cls, explanation: str) -> str:
        if not explanation.strip():
            raise ValueError("An explanation cannot be blank.")
        return explanation.strip()


class CandidateBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[Candidate] = Field(min_length=8, max_length=8)

    @field_validator("candidates")
    @classmethod
    def require_distinct_words(cls, candidates: list[Candidate]) -> list[Candidate]:
        words = [candidate.word.casefold() for candidate in candidates]
        if len(set(words)) != len(words):
            raise ValueError("The eight candidate words must be distinct.")
        return candidates


class Recommendation(BaseModel):
    word: str
    fit_score: int = Field(ge=0, le=100)
    explanation: str


class RecommendResponse(BaseModel):
    session_id: UUID
    recommendations: list[Recommendation] = Field(min_length=5, max_length=5)


class AcceptRequest(BaseModel):
    word: str = Field(min_length=1, max_length=60)


class AcceptResponse(BaseModel):
    session_id: UUID
    word: str
    accepted: bool
