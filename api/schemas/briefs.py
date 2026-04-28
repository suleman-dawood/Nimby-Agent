"""Request/response models for brief endpoints."""

from pydantic import BaseModel


class BriefResponse(BaseModel):
    pp_number: str
    title: str | None
    council: str | None
    exhibition_start: str | None
    exhibition_end: str | None
    description: str | None
    markdown: str
    addresses: str | None


class CitationRequest(BaseModel):
    document_title: str
    page: int


class CitationResponse(BaseModel):
    text: str
    document_title: str
    page: int
    pdf_url: str | None = None
