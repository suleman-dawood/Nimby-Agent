"""Q&A: answer questions about a specific PP with grounded citations."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from scraper.models import PP, Document, Chunk, create_db_engine, create_session
from pipeline.llm_utils import (
    load_prompt, call_llm, normalize_citations, extract_citations,
    format_chunks, find_chunk, extract_claim_for_citation,
)
from pipeline.retrieve import retrieve
from pipeline.verify_facts import verify_claim_facts

logger = logging.getLogger(__name__)


@dataclass
class QAResult:
    answer: str
    citations: list[dict] = field(default_factory=list)
    chunks_used: list[dict] = field(default_factory=list)
    verification_stats: dict = field(default_factory=dict)


def get_suggested_questions(pp_number: str, session: Session) -> list[str]:
    """Return 3-5 suggested questions based on the PP's available data."""
    pp = session.get(PP, pp_number)
    if not pp:
        return []

    docs = session.query(Document).filter_by(pp_number=pp_number, download_status="ok").all()
    concerns = {d.concern_tag for d in docs if d.concern_tag}
    rpa = (pp.relevant_planning_authority or "").upper()

    questions = [
        "What is being proposed?",
        "What are the proposed building heights?",
    ]

    if "traffic" in concerns:
        questions.append("What did the traffic study find?")
    if "bushfire" in concerns:
        questions.append("What are the bushfire risks?")
    if "heritage" in concerns:
        questions.append("Are there heritage impacts?")
    if "acoustic" in concerns:
        questions.append("What are the noise impacts?")
    if "contamination" in concerns:
        questions.append("Is there contamination on the site?")
    if "flood" in concerns:
        questions.append("Is the site flood-prone?")
    if "ecology" in concerns:
        questions.append("What are the ecological impacts?")
    if rpa in ("DPHI", "MINISTER"):
        questions.append("Why is the state handling this proposal?")

    return questions[:6]


def generate_impact(pp_number: str, address: str, distance_km: float) -> QAResult:
    """Generate a personalized impact summary for a resident at a specific address."""
    engine = create_db_engine()
    session = create_session(engine)

    try:
        pp = session.get(PP, pp_number)
        if not pp:
            return QAResult(answer=f"Planning proposal {pp_number} not found.")

        chunks = retrieve(pp_number, f"impact residents nearby traffic noise height building", k=10, tier_filter=[1, 2])

        if not chunks:
            return QAResult(answer="The proposal documents don't contain enough information to assess the impact on your address.")

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

        answer = call_llm(prompt, system=system)
        answer = normalize_citations(answer)
        citations = extract_citations(answer)

        verified = 0
        for cit in citations:
            chunk = find_chunk(session, pp_number, cit["document_title"], cit["page"])
            if chunk:
                claim = extract_claim_for_citation(answer, cit["span"])
                result = verify_claim_facts(
                    claim_sentence=claim,
                    chunk_text=chunk.text,
                    chunk_metadata={"document_title": cit["document_title"], "page_number": cit["page"]},
                )
                if result.status in ("verified", "no_facts"):
                    verified += 1

        return QAResult(
            answer=answer,
            citations=citations,
            chunks_used=[{"doc_title": c["document_title"], "page": c["page_number"]} for c in chunks],
            verification_stats={"verified": verified, "unsupported": 0, "total": len(citations)},
        )

    finally:
        session.close()


def answer_question(pp_number: str, question: str) -> QAResult:
    """Answer a question about a PP with grounded citations."""
    # ADC credentials used automatically via get_client()
    engine = create_db_engine()
    session = create_session(engine)

    try:
        pp = session.get(PP, pp_number)
        if not pp:
            return QAResult(answer=f"Planning proposal {pp_number} not found.")

        # Retrieve relevant chunks
        chunks = retrieve(pp_number, question, k=8, tier_filter=[1, 2])

        if not chunks:
            return QAResult(answer="The reviewed documents do not contain information relevant to this question.")

        chunk_text = format_chunks(chunks)

        system = load_prompt("qa_system")
        prompt = load_prompt("qa_user").format(
            pp_number=pp_number,
            title=pp.title or "",
            question=question,
            chunks=chunk_text,
        )

        answer = call_llm(prompt, system=system)
        answer = normalize_citations(answer)
        citations = extract_citations(answer)

        # Verify citations
        verified = 0
        unsupported = 0
        for cit in citations:
            chunk = find_chunk(session, pp_number, cit["document_title"], cit["page"])
            if chunk:
                claim = extract_claim_for_citation(answer, cit["span"])
                result = verify_claim_facts(
                    claim_sentence=claim,
                    chunk_text=chunk.text,
                    chunk_metadata={"document_title": cit["document_title"], "page_number": cit["page"]},
                )
                if result.status in ("verified", "no_facts"):
                    verified += 1
                elif result.status == "unsupported":
                    unsupported += 1

        # Strip sentences with unsupported facts
        if unsupported > 0:
            sentences = re.split(r'(?<=[.!?])\s+', answer)
            clean_sentences = []
            for sent in sentences:
                sent_cites = extract_citations(sent)
                keep = True
                for sc in sent_cites:
                    chunk = find_chunk(session, pp_number, sc["document_title"], sc["page"])
                    if chunk:
                        claim = re.sub(r'\[doc:[^\]]+\]', '', sent).strip()
                        result = verify_claim_facts(
                            claim_sentence=claim,
                            chunk_text=chunk.text,
                            chunk_metadata={"document_title": sc["document_title"], "page_number": sc["page"]},
                        )
                        if result.status == "unsupported":
                            keep = False
                            break
                if keep:
                    clean_sentences.append(sent)

            answer = " ".join(clean_sentences)

        return QAResult(
            answer=answer,
            citations=citations,
            chunks_used=[{"doc_title": c["document_title"], "page": c["page_number"]} for c in chunks],
            verification_stats={"verified": verified, "unsupported": unsupported, "total": len(citations)},
        )

    finally:
        session.close()
