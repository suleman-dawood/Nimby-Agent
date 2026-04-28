"""Submission generator: produce evidence-based resident submissions."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from scraper.models import PP, create_db_engine, create_session
from pipeline.llm_utils import (
    load_prompt, call_llm, normalize_citations, extract_citations,
    format_chunks, find_chunk, extract_claim_for_citation,
)
from pipeline.retrieve import retrieve
from pipeline.verify_facts import verify_claim_facts

logger = logging.getLogger(__name__)

CONCERN_QUERIES = {
    "Traffic and transport": "traffic impact vehicle movement intersection transport assessment",
    "Environmental impact": "ecology biodiversity trees vegetation endangered species environmental",
    "Density and scale": "building height density floor space ratio dwellings lots scale",
    "Heritage": "heritage impact assessment significance conservation archaeological",
    "Bushfire risk": "bushfire risk assessment strategic study fire evacuation",
    "Noise and acoustic": "noise acoustic impact assessment decibel sound",
    "Neighbourhood character": "character streetscape amenity bulk scale neighbourhood",
    "Infrastructure capacity": "infrastructure water sewer drainage capacity services",
    "Parking": "parking spaces car parking provision demand",
    "Construction impact": "construction noise dust traffic management demolition",
    "Aircraft noise": "aircraft noise ANEF contour airport flight path",
    "Contamination": "contamination soil remediation asbestos hazardous investigation",
}


@dataclass
class SubmissionResult:
    markdown: str
    concern_results: list[dict] = field(default_factory=list)
    dropped_concerns: list[dict] = field(default_factory=list)
    citation_stats: dict = field(default_factory=dict)


def draft_concern_paragraph(
    pp_number: str,
    concern: str,
    context: dict,
) -> dict:
    """Draft a paragraph for one concern. Returns {concern, text, citations, dropped}."""
    query = CONCERN_QUERIES.get(concern, concern)
    chunks = retrieve(pp_number, query, k=8, tier_filter=[1, 2])

    if not chunks:
        return {
            "concern": concern,
            "text": "",
            "citations": [],
            "dropped": True,
            "drop_reason": "No supporting evidence found in the proposal documents.",
        }

    chunk_text = format_chunks(chunks)
    system = load_prompt("submission_system")
    prompt = load_prompt("submission_concern").format(
        concern=concern,
        pp_number=pp_number,
        title=context.get("title", ""),
        addresses=context.get("addresses", "Not specified"),
        council=context.get("council", "Not specified"),
        chunks=chunk_text,
    )

    text = call_llm(prompt, system=system)
    text = normalize_citations(text)
    citations = extract_citations(text)

    # Verify citations
    session = context.get("_session")
    verified = 0
    for cit in citations:
        if session:
            chunk = find_chunk(session, pp_number, cit["document_title"], cit["page"])
            if chunk:
                result = verify_claim_facts(
                    claim_sentence=extract_claim_for_citation(text, cit["span"]),
                    chunk_text=chunk.text,
                    chunk_metadata={"document_title": cit["document_title"], "page_number": cit["page"]},
                )
                if result.status in ("verified", "no_facts"):
                    verified += 1

    return {
        "concern": concern,
        "text": text,
        "citations": citations,
        "verified": verified,
        "total_citations": len(citations),
        "dropped": False,
    }


def generate_submission(
    pp_number: str,
    concerns: list[str],
    free_text: str = "",
    user_name: str = "A Concerned Resident",
    user_address: str = "",
) -> SubmissionResult:
    """Generate a full submission letter."""
    # ADC credentials used automatically via get_client()
    engine = create_db_engine()
    session = create_session(engine)

    try:
        pp = session.get(PP, pp_number)
        if not pp:
            raise ValueError(f"PP {pp_number} not found")

        context = {
            "title": pp.title,
            "council": pp.council or "the relevant authority",
            "addresses": pp.addresses or "Not specified",
            "_session": session,
        }

        concern_results = []
        dropped = []

        for concern in concerns:
            logger.info("Drafting concern: %s", concern)
            result = draft_concern_paragraph(pp_number, concern, context)
            if result["dropped"]:
                dropped.append({"concern": concern, "reason": result["drop_reason"]})
            else:
                concern_results.append(result)

        # Compose the full letter
        concern_paragraphs = "\n\n".join(
            f"### {r['concern']}\n{r['text']}" for r in concern_results
        )

        free_text_section = ""
        if free_text.strip():
            # Retrieve evidence for free text too
            chunks = retrieve(pp_number, free_text, k=6, tier_filter=[1, 2])
            if chunks:
                chunk_text = format_chunks(chunks)
                ft_prompt = load_prompt("submission_concern").format(
                    concern=f"the following specific concern: {free_text}",
                    pp_number=pp_number,
                    title=context["title"],
                    addresses=context["addresses"],
                    council=context["council"],
                    chunks=chunk_text,
                )
                ft_response = call_llm(ft_prompt, system=load_prompt("submission_system"))
                ft_response = normalize_citations(ft_response)
                free_text_section = f"### Additional concerns\n{ft_response}"
            else:
                free_text_section = f"### Additional concerns\n{free_text}"

        system = load_prompt("submission_system")
        compose_prompt = load_prompt("submission_compose").format(
            council=context["council"],
            pp_number=pp_number,
            title=context["title"],
            user_name=user_name,
            user_address=user_address,
            concern_paragraphs=concern_paragraphs,
            free_text_section=free_text_section,
        )

        letter = call_llm(compose_prompt, system=system)
        letter = normalize_citations(letter)

        # Add dropped concerns note
        if dropped:
            letter += "\n\n---\n"
            letter += "*The following concerns were not included because the proposal documents "
            letter += "do not contain supporting analysis:*\n"
            for d in dropped:
                letter += f"- **{d['concern']}**: {d['reason']}\n"

        total_cit = sum(r["total_citations"] for r in concern_results)
        total_verified = sum(r["verified"] for r in concern_results)

        return SubmissionResult(
            markdown=letter,
            concern_results=concern_results,
            dropped_concerns=dropped,
            citation_stats={"total": total_cit, "verified": total_verified},
        )

    finally:
        session.close()
