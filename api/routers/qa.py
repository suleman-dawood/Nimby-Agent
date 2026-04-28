"""Q&A endpoints: ask questions and get suggestions."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.deps import get_session
from api.schemas.qa import (
    AskRequest,
    AskResponse,
    Citation,
    ImpactRequest,
    SuggestionsResponse,
    VerificationStats,
)
from pipeline.qa import answer_question, generate_impact, get_suggested_questions

router = APIRouter(prefix="/api/qa", tags=["qa"])


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    result = answer_question(req.pp_number, req.question)
    return AskResponse(
        answer=result.answer,
        citations=[
            Citation(document_title=c["document_title"], page=c["page"])
            for c in result.citations
        ],
        verification_stats=VerificationStats(**result.verification_stats)
        if result.verification_stats
        else VerificationStats(),
    )


@router.post("/impact", response_model=AskResponse)
def impact(req: ImpactRequest):
    result = generate_impact(req.pp_number, req.address, req.distance_km)
    return AskResponse(
        answer=result.answer,
        citations=[
            Citation(document_title=c["document_title"], page=c["page"])
            for c in result.citations
        ],
        verification_stats=VerificationStats(**result.verification_stats)
        if result.verification_stats
        else VerificationStats(),
    )


@router.get("/{pp_number}/suggestions", response_model=SuggestionsResponse)
def suggestions(pp_number: str, session: Session = Depends(get_session)):
    questions = get_suggested_questions(pp_number, session)
    return SuggestionsResponse(questions=questions)
