"""Brief endpoints: load brief markdown + citation lookup."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import get_session
from api.schemas.briefs import BriefResponse, CitationRequest, CitationResponse
from pipeline.llm_utils import find_chunk
from scraper.models import PP, Document

router = APIRouter(prefix="/api/briefs", tags=["briefs"])

BRIEFS_DIR = "/data/briefs" if os.path.isdir("/data") else os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "briefs")


@router.get("/{pp_number}", response_model=BriefResponse)
def get_brief(pp_number: str, session: Session = Depends(get_session)):
    pp = session.get(PP, pp_number)
    if not pp:
        raise HTTPException(status_code=404, detail=f"PP {pp_number} not found")

    brief_path = os.path.join(BRIEFS_DIR, f"{pp_number}.md")
    if not os.path.exists(brief_path):
        raise HTTPException(status_code=404, detail=f"Brief for {pp_number} not generated yet")

    with open(brief_path) as f:
        markdown = f.read()

    return BriefResponse(
        pp_number=pp_number,
        title=pp.title,
        council=pp.council,
        exhibition_start=str(pp.exhibition_start) if pp.exhibition_start else None,
        exhibition_end=str(pp.exhibition_end) if pp.exhibition_end else None,
        description=pp.description,
        markdown=markdown,
        addresses=pp.addresses,
        portal_url=pp.detail_url,
    )


@router.post("/{pp_number}/citation", response_model=CitationResponse)
def get_citation(
    pp_number: str,
    req: CitationRequest,
    session: Session = Depends(get_session),
):
    chunk = find_chunk(session, pp_number, req.document_title, req.page)
    if not chunk:
        raise HTTPException(status_code=404, detail="Citation source not found")

    doc = (
        session.query(Document)
        .filter(
            Document.pp_number == pp_number,
            Document.title.like(f"%{req.document_title[:30]}%"),
        )
        .first()
    )

    return CitationResponse(
        text=chunk.text[:1500],
        document_title=req.document_title,
        page=req.page,
        pdf_url=doc.url if doc else None,
    )
