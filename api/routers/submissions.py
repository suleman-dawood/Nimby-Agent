"""Submission endpoints: generate evidence-based submissions."""

from __future__ import annotations

from fastapi import APIRouter

from api.schemas.submissions import (
    ConcernsResponse,
    DroppedConcern,
    SubmissionCitation,
    SubmissionRequest,
    SubmissionResponse,
)
from pipeline.submission import CONCERN_QUERIES, generate_submission
from pipeline.llm_utils import extract_citations, normalize_citations

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

    # Extract unique citations from the final letter
    normalized = normalize_citations(result.markdown)
    all_citations = extract_citations(normalized)
    seen = set()
    unique_citations = []
    for c in all_citations:
        key = f"{c['document_title']}|{c['page']}"
        if key not in seen:
            seen.add(key)
            unique_citations.append(
                SubmissionCitation(document_title=c["document_title"], page=c["page"])
            )

    return SubmissionResponse(
        markdown=result.markdown,
        dropped_concerns=[
            DroppedConcern(**d) for d in result.dropped_concerns
        ],
        citations=unique_citations,
    )
