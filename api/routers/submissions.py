"""Submission endpoints: generate evidence-based submissions."""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas.submissions import (
    ConcernsResponse,
    CitationStats,
    DroppedConcern,
    SubmissionRequest,
    SubmissionResponse,
)
from pipeline.submission import CONCERN_QUERIES, generate_submission

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.get("/concerns", response_model=ConcernsResponse)
def list_concerns():
    return ConcernsResponse(concerns=list(CONCERN_QUERIES.keys()))


@router.post("/generate", response_model=SubmissionResponse)
def generate(req: SubmissionRequest):
    result = generate_submission(
        pp_number=req.pp_number,
        concerns=req.concerns,
        free_text=req.free_text,
        user_name=req.user_name,
        user_address=req.user_address,
    )
    return SubmissionResponse(
        markdown=result.markdown,
        dropped_concerns=[
            DroppedConcern(**d) for d in result.dropped_concerns
        ],
        citation_stats=CitationStats(**result.citation_stats),
    )
