"""Request/response models for submission endpoints."""

from pydantic import BaseModel, Field


class SubmissionRequest(BaseModel):
    pp_number: str
    concerns: list[str] = Field(..., min_length=1)
    free_text: str = ""
    user_name: str = "A Concerned Resident"
    user_address: str = ""


class DroppedConcern(BaseModel):
    concern: str
    reason: str


class CitationStats(BaseModel):
    total: int = 0
    verified: int = 0


class SubmissionResponse(BaseModel):
    markdown: str
    dropped_concerns: list[DroppedConcern] = []
    citation_stats: CitationStats = CitationStats()


class ConcernsResponse(BaseModel):
    concerns: list[str]
