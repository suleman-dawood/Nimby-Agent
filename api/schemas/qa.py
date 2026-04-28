"""Request/response models for Q&A endpoints."""

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    pp_number: str
    question: str = Field(..., min_length=3)


class Citation(BaseModel):
    document_title: str
    page: int


class VerificationStats(BaseModel):
    verified: int = 0
    unsupported: int = 0
    total: int = 0


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    verification_stats: VerificationStats = VerificationStats()


class ImpactRequest(BaseModel):
    pp_number: str
    address: str
    distance_km: float = 0.0


class SuggestionsResponse(BaseModel):
    questions: list[str]
