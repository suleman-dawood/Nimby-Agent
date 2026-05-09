"""Q&A endpoints: ask questions and get suggestions."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
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


def _stream_qa(pp_number: str, question: str):
    """Stream Q&A response as SSE events."""
    from scraper.models import PP, create_db_engine, create_session
    from pipeline.retrieve import retrieve
    from pipeline.llm_utils import (
        load_prompt, stream_llm, format_chunks, normalize_citations,
        extract_citations, find_chunk,
    )

    engine = create_db_engine()
    session = create_session(engine)

    try:
        pp = session.get(PP, pp_number)
        if not pp:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Proposal not found'})}\n\n"
            return

        chunks = retrieve(pp_number, question, k=8, tier_filter=[1, 2])
        if not chunks:
            yield f"data: {json.dumps({'type': 'error', 'content': 'No relevant documents found.'})}\n\n"
            return

        chunk_text = format_chunks(chunks)
        system = load_prompt("qa_system")
        prompt = load_prompt("qa_user").format(
            pp_number=pp_number,
            title=pp.title or "",
            question=question,
            chunks=chunk_text,
        )

        full_text = ""
        for token in stream_llm(prompt, system=system):
            full_text += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        # Post-stream: extract citations
        full_text = normalize_citations(full_text)
        citations = extract_citations(full_text)
        cit_list = [
            {"document_title": c["document_title"], "page": c["page"]}
            for c in citations
        ]
        # Dedupe
        seen = set()
        unique_cits = []
        for c in cit_list:
            key = f"{c['document_title']}|{c['page']}"
            if key not in seen:
                seen.add(key)
                unique_cits.append(c)

        yield f"data: {json.dumps({'type': 'citations', 'citations': unique_cits})}\n\n"
        yield "data: [DONE]\n\n"

    finally:
        session.close()


def _stream_impact(pp_number: str, address: str, distance_km: float):
    """Stream impact response as SSE events."""
    from scraper.models import PP, create_db_engine, create_session
    from pipeline.retrieve import retrieve
    from pipeline.llm_utils import (
        load_prompt, stream_llm, format_chunks, normalize_citations,
        extract_citations,
    )

    engine = create_db_engine()
    session = create_session(engine)

    try:
        pp = session.get(PP, pp_number)
        if not pp:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Proposal not found'})}\n\n"
            return

        chunks = retrieve(pp_number, "impact residents nearby traffic noise height building", k=10, tier_filter=[1, 2])
        if not chunks:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Not enough information to assess impact.'})}\n\n"
            return

        chunk_text = format_chunks(chunks)
        system = load_prompt("impact_system")
        prompt = load_prompt("impact_user").format(
            pp_number=pp_number,
            title=pp.title or "",
            address=address,
            distance_km=distance_km,
            council=pp.council or "the relevant authority",
            exhibition_end=pp.exhibition_end or "Not specified",
            chunks=chunk_text,
        )

        full_text = ""
        for token in stream_llm(prompt, system=system):
            full_text += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        full_text = normalize_citations(full_text)
        citations = extract_citations(full_text)
        cit_list = [
            {"document_title": c["document_title"], "page": c["page"]}
            for c in citations
        ]
        seen = set()
        unique_cits = []
        for c in cit_list:
            key = f"{c['document_title']}|{c['page']}"
            if key not in seen:
                seen.add(key)
                unique_cits.append(c)

        yield f"data: {json.dumps({'type': 'citations', 'citations': unique_cits})}\n\n"
        yield "data: [DONE]\n\n"

    finally:
        session.close()


@router.post("/ask/stream")
def ask_stream(req: AskRequest):
    return StreamingResponse(
        _stream_qa(req.pp_number, req.question),
        media_type="text/event-stream",
    )


def _stream_impact_fast(pp_number: str, address: str, distance_km: float):
    """Stream a fast impact response using the pre-generated brief (no RAG pipeline)."""
    import os
    from scraper.models import PP, create_db_engine, create_session
    from pipeline.llm_utils import (
        load_prompt, stream_llm, normalize_citations, extract_citations,
    )

    engine = create_db_engine()
    session = create_session(engine)

    try:
        pp = session.get(PP, pp_number)
        if not pp:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Proposal not found'})}\n\n"
            return

        briefs_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "briefs",
        )
        brief_path = os.path.join(briefs_dir, f"{pp_number}.md")
        if not os.path.exists(brief_path):
            yield f"data: {json.dumps({'type': 'error', 'content': 'Brief not available yet.'})}\n\n"
            return

        with open(brief_path) as f:
            brief_md = f.read()

        system = load_prompt("impact_fast_system")
        prompt = load_prompt("impact_fast_user").format(
            pp_number=pp_number,
            title=pp.title or "",
            address=address,
            distance_km=distance_km,
            council=pp.council or "the relevant authority",
            exhibition_end=pp.exhibition_end or "Not specified",
            brief=brief_md,
        )

        full_text = ""
        for token in stream_llm(prompt, system=system):
            full_text += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        # Extract any citations the LLM reused from the brief
        full_text = normalize_citations(full_text)
        citations = extract_citations(full_text)
        cit_list = [
            {"document_title": c["document_title"], "page": c["page"]}
            for c in citations
        ]
        seen = set()
        unique_cits = []
        for c in cit_list:
            key = f"{c['document_title']}|{c['page']}"
            if key not in seen:
                seen.add(key)
                unique_cits.append(c)

        yield f"data: {json.dumps({'type': 'citations', 'citations': unique_cits})}\n\n"
        yield "data: [DONE]\n\n"

    finally:
        session.close()


@router.post("/impact-fast/stream")
def impact_fast_stream(req: ImpactRequest):
    return StreamingResponse(
        _stream_impact_fast(req.pp_number, req.address, req.distance_km),
        media_type="text/event-stream",
    )


@router.post("/impact/stream")
def impact_stream(req: ImpactRequest):
    return StreamingResponse(
        _stream_impact(req.pp_number, req.address, req.distance_km),
        media_type="text/event-stream",
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


# --- Agent endpoint (ADK) ---

@router.post("/agent/stream")
async def agent_stream(req: AskRequest):
    """Stream agent response with tool-use indicators. Requires auth + tokens in future."""
    import asyncio
    from agents.streaming import stream_agent_response

    async def generate():
        async for chunk in stream_agent_response(req.pp_number, req.question, "anonymous"):
            yield chunk

    return StreamingResponse(generate(), media_type="text/event-stream")
