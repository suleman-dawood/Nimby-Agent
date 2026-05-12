"""Brief endpoints: load brief markdown + citation lookup."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from api.deps import get_session
from api.schemas.briefs import BriefResponse, CitationRequest, CitationResponse
from pipeline.llm_utils import find_chunk
from scraper.models import PP, Brief, Document

router = APIRouter(prefix="/api/briefs", tags=["briefs"])

BRIEFS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "briefs")


@router.get("/{pp_number}", response_model=BriefResponse)
def get_brief(pp_number: str, session: Session = Depends(get_session)):
    logger.info("get_brief pp=%s", pp_number)
    pp = session.get(PP, pp_number)
    if not pp:
        logger.warning("brief 404 pp=%s", pp_number)
        raise HTTPException(status_code=404, detail=f"PP {pp_number} not found")

    # Try DB first, fall back to file, then generate a metadata-only brief
    brief = session.query(Brief).filter_by(pp_number=pp_number).first()
    if brief:
        markdown = brief.markdown
    else:
        brief_path = os.path.join(BRIEFS_DIR, f"{pp_number}.md")
        if os.path.exists(brief_path):
            with open(brief_path) as f:
                markdown = f.read()
        else:
            # No brief available — generate a metadata summary
            from scraper.models import Chunk, SiteContext
            chunk_count = session.query(Chunk).filter_by(pp_number=pp_number).count()
            site_ctx = session.query(SiteContext).filter_by(pp_number=pp_number).first()

            parts = [f"# {pp.title or pp_number}\n"]
            if pp.description:
                parts.append(f"{pp.description[:500]}\n")
            parts.append(f"**Stage:** {pp.stage or 'Unknown'}")
            parts.append(f"**Council:** {pp.council or 'Unknown'}")
            if pp.exhibition_end:
                parts.append(f"**Exhibition closes:** {pp.exhibition_end}")
            if site_ctx:
                parts.append(f"\n## Site Context\n- **Zoning:** {site_ctx.zoning or 'N/A'}")
                if site_ctx.max_height_m:
                    parts.append(f"- **Max Height:** {site_ctx.max_height_m}m")
                if site_ctx.bushfire_prone:
                    parts.append("- **Bushfire Prone**")
                if site_ctx.flood_planning:
                    parts.append("- **Flood Planning Area**")
            if chunk_count == 0:
                parts.append("\n*No public documents are available for this proposal yet. "
                             "Use the chat to ask questions based on the metadata and site context available.*")
            markdown = "\n".join(parts)

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
    logger.info("citation pp=%s doc=%s p=%d", pp_number, req.document_title[:40], req.page)
    chunk = find_chunk(session, pp_number, req.document_title, req.page)
    if not chunk:
        logger.warning("citation 404 pp=%s doc=%s p=%d", pp_number, req.document_title[:40], req.page)
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
