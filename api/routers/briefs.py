"""Brief endpoints: load brief markdown + citation lookup."""

from __future__ import annotations

import io
import logging
import os
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from api.deps import get_session
from api.schemas.briefs import BriefResponse, CitationRequest, CitationResponse, TimelineEvent, TimelineResponse
from pipeline.llm_utils import find_chunk
from scraper.models import PP, Brief, Document, SiteContext

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

    # Non-document citations (spatial data, portal metadata) — return info text
    if req.document_title.startswith("NSW ") or req.document_title.startswith("LEP "):
        return CitationResponse(
            text=f"Source: {req.document_title}. This data comes from NSW government systems, not proposal documents.",
            document_title=req.document_title,
            page=0,
            pdf_url=None,
        )

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


@router.get("/{pp_number}/timeline", response_model=TimelineResponse)
def get_timeline(pp_number: str, session: Session = Depends(get_session)):
    """Chronological history of events for a planning proposal."""
    pp = session.get(PP, pp_number)
    if not pp:
        raise HTTPException(status_code=404, detail=f"PP {pp_number} not found")

    events: list[TimelineEvent] = []

    if pp.scraped_at:
        events.append(TimelineEvent(
            date=str(pp.scraped_at), event_type="scraped",
            title="Proposal indexed",
            detail=f"Stage: {pp.stage}" if pp.stage else None,
        ))
    if pp.exhibition_start:
        events.append(TimelineEvent(
            date=str(pp.exhibition_start), event_type="exhibition_start",
            title="Exhibition opened",
        ))
    if pp.exhibition_end:
        events.append(TimelineEvent(
            date=str(pp.exhibition_end), event_type="exhibition_end",
            title="Exhibition closes",
        ))

    docs = session.query(Document).filter_by(pp_number=pp_number).all()
    for doc in docs:
        if doc.scraped_at:
            events.append(TimelineEvent(
                date=str(doc.scraped_at), event_type="document_added",
                title=f"Document: {doc.title}",
                detail=doc.category,
            ))

    site_ctx = session.query(SiteContext).filter_by(pp_number=pp_number).first()
    if site_ctx and hasattr(site_ctx, "queried_at") and site_ctx.queried_at:
        events.append(TimelineEvent(
            date=str(site_ctx.queried_at), event_type="spatial_enriched",
            title="Spatial data collected",
            detail=f"Zoning: {site_ctx.zoning}" if site_ctx.zoning else None,
        ))

    brief = session.query(Brief).filter_by(pp_number=pp_number).first()
    if brief and brief.generated_at:
        events.append(TimelineEvent(
            date=str(brief.generated_at), event_type="brief_generated",
            title="Brief generated",
            detail=f"{brief.doc_count} documents, {brief.chunk_count} chunks" if brief.doc_count else None,
        ))

    events.sort(key=lambda e: e.date)
    return TimelineResponse(pp_number=pp_number, events=events)


@router.get("/{pp_number}/export-pdf")
def export_pdf(pp_number: str, session: Session = Depends(get_session)):
    """Generate a PDF report for a planning proposal."""
    from fpdf import FPDF

    pp = session.get(PP, pp_number)
    if not pp:
        raise HTTPException(status_code=404, detail=f"PP {pp_number} not found")

    brief = session.query(Brief).filter_by(pp_number=pp_number).first()
    site_ctx = session.query(SiteContext).filter_by(pp_number=pp_number).first()
    docs = session.query(Document).filter_by(pp_number=pp_number).all()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, pp_number, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    if pp.title:
        pdf.multi_cell(0, 6, pp.title)
    pdf.ln(4)

    # Metadata
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Proposal Details", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    meta_lines = [
        f"Council: {pp.council or 'N/A'}",
        f"Stage: {pp.stage or 'N/A'}",
        f"Addresses: {pp.addresses or 'N/A'}",
        f"Exhibition: {pp.exhibition_start or '?'} to {pp.exhibition_end or '?'}",
    ]
    for line in meta_lines:
        pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Site Context
    if site_ctx:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Planning Controls", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        controls = [
            f"Zoning: {site_ctx.zoning or 'N/A'}",
            f"Max Height: {site_ctx.max_height_m or 'N/A'}m",
            f"Max FSR: {site_ctx.max_fsr or 'N/A'}",
            f"Heritage: {'Yes' if site_ctx.heritage_item else 'No'}",
            f"Bushfire Prone: {'Yes' if site_ctx.bushfire_prone else 'No'}",
            f"Flood Planning: {'Yes' if site_ctx.flood_planning else 'No'}",
        ]
        for line in controls:
            pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # Brief
    if brief:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Brief", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        # Strip markdown formatting for PDF
        clean = re.sub(r'[#*_\[\]]', '', brief.markdown)
        clean = re.sub(r'\[doc:.*?\]', '', clean)
        for line in clean.split('\n'):
            line = line.strip()
            if line:
                pdf.multi_cell(0, 5, line)
                pdf.ln(1)
        pdf.ln(4)

    # Documents list
    if docs:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, f"Documents ({len(docs)})", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for doc in docs:
            pdf.cell(0, 5, f"- {doc.title}", new_x="LMARGIN", new_y="NEXT")

    # Output
    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={pp_number}-report.pdf"},
    )
