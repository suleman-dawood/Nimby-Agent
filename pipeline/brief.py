"""Brief generator: produce plain-language PP summaries with grounded citations.

Pipeline: orient → draft → verify → rewrite → compose

Uses Gemini 2.5 Flash for all steps.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import func

from scraper.models import PP, Document, Chunk, create_db_engine, create_session
from pipeline.retrieve import retrieve
from pipeline.verify_facts import verify_claim_facts, FactVerificationResult
from pipeline.llm_utils import (
    load_prompt, call_llm, normalize_citations, extract_citations,
    format_chunks, find_chunk, extract_claim_for_citation, CITE_PATTERN,
)

logger = logging.getLogger(__name__)


# --- Node 1: Orient ---

def orient(session: Session, pp_number: str) -> dict:
    pp = session.query(PP).get(pp_number)
    if not pp:
        raise ValueError(f"PP {pp_number} not found")

    docs = session.query(Document).filter_by(pp_number=pp_number, download_status="ok").all()
    tier1a = [d for d in docs if d.sub_tier == "1a"]
    tier1 = [d for d in docs if d.tier == 1]
    tier2 = [d for d in docs if d.tier == 2]

    rpa = pp.relevant_planning_authority or ""
    pp_type = "state-led" if rpa.upper() in ("DPHI", "MINISTER") else "council-led"
    concerns = sorted({d.concern_tag for d in tier2 if d.concern_tag})

    # Content density: determines brief shape
    total_t1_pages = (
        session.query(func.count(Chunk.id))
        .join(Document)
        .filter(Chunk.pp_number == pp_number, Document.tier == 1)
        .scalar() or 0
    )
    total_t2_pages = (
        session.query(func.count(Chunk.id))
        .join(Document)
        .filter(Chunk.pp_number == pp_number, Document.tier == 2)
        .scalar() or 0
    )

    context = {
        "pp_number": pp_number,
        "title": pp.title,
        "council": pp.council,
        "addresses": pp.addresses,
        "description": pp.description,
        "exhibition_start": str(pp.exhibition_start) if pp.exhibition_start else None,
        "exhibition_end": str(pp.exhibition_end) if pp.exhibition_end else None,
        "stage": pp.stage,
        "rpa": rpa,
        "pp_type": pp_type,
        "main_proposal_title": tier1a[0].title if tier1a else None,
        "concerns": concerns,
        "content_density": {
            "tier1_chunks": total_t1_pages,
            "tier2_chunks": total_t2_pages,
            "tier1_docs": len(tier1),
            "tier2_docs": len(tier2),
        },
    }

    logger.info("Orient: %s (%s) — %s, T1=%d chunks, T2=%d chunks, %d concerns",
                pp_number, pp_type, pp.title, total_t1_pages, total_t2_pages, len(concerns))
    return context


# --- Node 2: Draft ---

def _get_brief_shape(context: dict) -> dict:
    """Determine brief structure based on content density."""
    density = context["content_density"]
    t1 = density["tier1_chunks"]
    t2 = density["tier2_chunks"]
    t2_docs = density["tier2_docs"]

    if t1 < 30 and t2 == 0:
        # Tiny PP: single document, procedural. One combined section.
        return {
            "mode": "compact",
            "target_words": 200,
            "sections": ["summary"],
        }
    elif t2_docs <= 2:
        # Small PP: proposal + maybe 1-2 studies. Two sections.
        return {
            "mode": "standard",
            "target_words": 400,
            "sections": ["proposed", "changes"],
        }
    else:
        # Full PP: multiple technical studies. Three sections.
        return {
            "mode": "full",
            "target_words": 600,
            "sections": ["proposed", "changes", "concerns"],
        }


SYSTEM_PROMPT = load_prompt("system")


SECTION_PROMPTS = {
    key: load_prompt(f"section_{key}")
    for key in ("summary", "proposed", "changes", "concerns")
}


def draft_section(context: dict, section_key: str, query: str, tiers: list[int], target_words: int) -> dict:
    pp = context["pp_number"]
    chunks = retrieve(pp, query, k=10, tier_filter=tiers)

    if not chunks:
        return {"section": section_key, "text": "", "citations": [], "chunks_used": []}

    chunk_text = format_chunks(chunks)
    section_instruction = SECTION_PROMPTS[section_key].format(target_words=target_words)

    prompt = load_prompt("draft").format(
        pp_number=pp,
        title=context["title"],
        section_instruction=section_instruction,
        addresses=context.get("addresses", "Not specified"),
        council=context.get("council", "Not specified"),
        exhibition_start=context.get("exhibition_start", "?"),
        exhibition_end=context.get("exhibition_end", "?"),
        pp_type=context.get("pp_type", "council-led"),
        chunks=chunk_text,
    )

    text = call_llm(prompt, system=SYSTEM_PROMPT)
    text = normalize_citations(text)
    citations = extract_citations(text)

    return {
        "section": section_key,
        "text": text,
        "citations": citations,
        "chunks_used": [{"chunk_id": c["chunk_id"], "doc_title": c["document_title"], "page": c["page_number"]} for c in chunks],
    }


def draft(context: dict) -> list[dict]:
    shape = _get_brief_shape(context)
    context["_shape"] = shape
    words_per_section = shape["target_words"] // len(shape["sections"])

    section_configs = {
        "summary": {
            "query": "what is being proposed rezoning development planning proposal overview changes impacts",
            "tiers": [1, 2],
        },
        "proposed": {
            "query": "what is being proposed rezoning development planning proposal overview purpose objective",
            "tiers": [1],
        },
        "changes": {
            "query": "building height density lots dwellings zoning changes floor space ratio land use maximum minimum",
            "tiers": [1, 2],
        },
        "concerns": {
            "query": "traffic noise heritage flooding bushfire contamination impact assessment concerns risk issues",
            "tiers": [2],
        },
    }

    drafted = []
    for section_key in shape["sections"]:
        cfg = section_configs[section_key]
        logger.info("Drafting: %s (mode=%s, ~%d words)", section_key, shape["mode"], words_per_section)
        result = draft_section(context, section_key, cfg["query"], cfg["tiers"], words_per_section)
        drafted.append(result)
        logger.info("  → %d chars, %d citations", len(result["text"]), len(result["citations"]))

    return drafted


# --- Node 3: Verify ---

def verify_citation(claim: str, cited_doc: str, cited_page: int, pp_number: str, session: Session) -> dict:
    chunk = find_chunk(session, pp_number, cited_doc, cited_page)

    if not chunk:
        return {"status": "not_found", "reason": f"No chunk for '{cited_doc[:40]}' p.{cited_page}"}

    prompt = load_prompt("verify").format(
        claim=claim,
        cited_doc=cited_doc,
        cited_page=cited_page,
        source_text=chunk.text[:2500],
    )

    response = call_llm(prompt)
    if not response:
        return {"status": "llm_error", "reason": "Empty LLM response", "chunk_id": chunk.id}

    first_line = response.strip().split("\n")[0].upper()

    if "NOT_SUPPORTED" in first_line or "NOT SUPPORTED" in first_line:
        status = "not_supported"
    elif "PARTIAL" in first_line:
        status = "partially_supported"
    elif "SUPPORTED" in first_line:
        status = "supported"
    else:
        status = "not_supported"

    return {"status": status, "reason": response.strip(), "chunk_id": chunk.id}


def verify(drafted: list[dict], context: dict, session: Session) -> list[dict]:
    pp = context["pp_number"]

    for section in drafted:
        verified_citations = []
        for cit in section["citations"]:
            doc_title = cit["document_title"]
            page = cit["page"]
            span = cit.get("span", (0, 0))

            claim = extract_claim_for_citation(section["text"], span)

            if not claim or len(claim) < 10:
                verified_citations.append({**cit, "claim": claim, "status": "no_claim_extracted", "verified": False})
                continue

            result = verify_citation(claim, doc_title, page, pp, session)
            verified = result["status"] in ("supported", "partially_supported")
            verified_citations.append({
                **cit,
                "claim": claim,
                "status": result["status"],
                "reason": result.get("reason", ""),
                "verified": verified,
                "chunk_id": result.get("chunk_id"),
            })
            logger.info("  Verify [%s | p.%d]: %s", doc_title[:30], page, result["status"])

        section["citations"] = verified_citations

    return drafted


# --- Node 4: Rewrite ---

def rewrite(drafted: list[dict], context: dict, session: Session) -> list[dict]:
    pp = context["pp_number"]

    for section in drafted:
        unsupported = [c for c in section["citations"] if not c.get("verified", True)]

        if not unsupported:
            continue

        logger.info("Rewriting '%s' — %d unsupported citations", section["section"], len(unsupported))

        bad_claims = []
        for cit in unsupported:
            claim = cit.get("claim", "")
            if claim:
                bad_claims.append(f"- UNSUPPORTED: \"{claim}\" (was cited as {cit['document_title']} p.{cit['page']})")

        if not bad_claims:
            continue

        combined_query = " ".join(c.get("claim", "")[:100] for c in unsupported)
        new_chunks = retrieve(pp, combined_query, k=15)
        chunk_text = format_chunks(new_chunks)

        prompt = load_prompt("rewrite").format(
            section_text=section["text"],
            bad_claims="\n".join(bad_claims),
            evidence=chunk_text,
        )

        rewritten = call_llm(prompt, system=SYSTEM_PROMPT)
        rewritten = normalize_citations(rewritten)
        new_citations = extract_citations(rewritten)

        section["text"] = rewritten
        re_verified = []
        for cit in new_citations:
            claim = extract_claim_for_citation(rewritten, cit.get("span", (0, 0)))
            result = verify_citation(claim, cit["document_title"], cit["page"], pp, session)
            verified = result["status"] in ("supported", "partially_supported")
            re_verified.append({
                **cit,
                "claim": claim,
                "status": result["status"],
                "verified": verified,
                "chunk_id": result.get("chunk_id"),
            })
            logger.info("  Re-verify [%s | p.%d]: %s", cit["document_title"][:30], cit["page"], result["status"])

        section["citations"] = re_verified

    return drafted


# --- Node 5: Fact verification ---

def verify_facts_node(drafted: list[dict], context: dict, session: Session) -> tuple[list[dict], dict]:
    """Run Layer 1 + Layer 2 fact verification on all verified citations.

    Returns (drafted_sections, fact_stats).
    """
    pp = context["pp_number"]
    stats = {"total_facts": 0, "l1_verified": 0, "l2_verified": 0,
             "unsupported": 0, "inconsistent": 0, "no_facts": 0, "claims_checked": 0}

    for section in drafted:
        for cit in section.get("citations", []):
            if not cit.get("verified"):
                continue  # Already failed citation check — skip fact check

            claim = cit.get("claim", "")
            if not claim or len(claim) < 10:
                continue

            chunk_id = cit.get("chunk_id")
            if not chunk_id:
                continue

            chunk = session.get(Chunk, chunk_id)
            if not chunk:
                continue

            stats["claims_checked"] += 1

            result = verify_claim_facts(
                claim_sentence=claim,
                chunk_text=chunk.text,
                chunk_metadata={
                    "document_title": cit["document_title"],
                    "page_number": cit["page"],
                },
                session=session,
                pp_number=pp,
                cited_chunk_id=chunk_id,
            )

            # Store result on citation
            cit["fact_status"] = result.status
            cit["fact_layer"] = result.layer_used
            cit["fact_notes"] = result.notes
            if result.contradictions:
                cit["l3_contradictions"] = [
                    {
                        "fact": c.fact_in_claim,
                        "alternative_value": c.alternative_value,
                        "alternative_doc": c.alternative_doc_title,
                        "alternative_page": c.alternative_page,
                        "shared_topics": c.shared_topics,
                        "confidence": c.confidence,
                    }
                    for c in result.contradictions
                ]

            stats["total_facts"] += len(result.extracted_facts)

            if result.status == "verified":
                if "L1" in result.layer_used:
                    stats["l1_verified"] += 1
                else:
                    stats["l2_verified"] += 1
            elif result.status == "no_facts":
                stats["no_facts"] += 1
            elif result.status == "inconsistent":
                stats["inconsistent"] += 1
                cit["verified"] = False
                cit["fact_issues"] = result.notes
                logger.warning("  L3 INCONSISTENT: %s | %s", claim[:60], result.notes[:80])
            elif result.status == "unsupported":
                stats["unsupported"] += 1
                cit["verified"] = False
                cit["fact_issues"] = result.notes
                logger.warning("  Fact check FAILED: %s | %s", claim[:60], result.notes[:80])

    logger.info(
        "Fact verification: %d claims checked, L1=%d, L2=%d verified, %d unsupported, %d no_facts",
        stats["claims_checked"], stats["l1_verified"], stats["l2_verified"],
        stats["unsupported"], stats["no_facts"],
    )

    return drafted, stats


# --- Node 6: Strip unsupported facts ---

def strip_unsupported_facts(drafted: list[dict]) -> list[dict]:
    """Remove sentences containing fact-check-failed claims from brief text.

    When a citation passes topical verification but fails fact verification
    (wrong number, wrong date, etc.), the sentence containing that claim
    is removed from the section text to prevent incorrect info in the brief.
    """
    for section in drafted:
        bad_claims = [
            cit for cit in section.get("citations", [])
            if cit.get("fact_status") == "unsupported"
        ]

        if not bad_claims:
            continue

        text = section["text"]
        removed = 0

        for cit in bad_claims:
            claim = cit.get("claim", "")
            if not claim or len(claim) < 15:
                continue

            # Find and remove the sentence containing this claim
            # The claim text has citations stripped, so we need to find it in context
            # Look for a sentence that contains the key words from the claim
            claim_words = set(claim.lower().split())
            sentences = re.split(r'(?<=[.!?])\s+', text)
            new_sentences = []

            for sentence in sentences:
                sentence_words = set(sentence.lower().split())
                # If >60% of claim words appear in this sentence, it's the one
                overlap = len(claim_words & sentence_words) / max(len(claim_words), 1)
                if overlap > 0.6:
                    removed += 1
                    logger.info("  Stripped unsupported sentence: %s", sentence[:80])
                else:
                    new_sentences.append(sentence)

            text = " ".join(new_sentences)

        if removed:
            section["text"] = text.strip()
            # Clean up double spaces and orphaned citations
            section["text"] = re.sub(r'\s+', ' ', section["text"])
            logger.info("  Stripped %d unsupported sentences from '%s'", removed, section["section"])

    return drafted


# --- Node 7: Compose ---

SECTION_TITLES = {
    "summary": "Summary",
    "proposed": "What's being proposed",
    "changes": "What changes on the ground",
    "concerns": "Things to know",
}

EMPTY_CONCERNS_FALLBACK = load_prompt("empty_concerns")


def compose(drafted: list[dict], context: dict, fact_stats: dict | None = None) -> str:
    pp = context["pp_number"]
    title = context["title"]
    council = context.get("council") or "Not specified"
    addresses = context.get("addresses") or "Not specified"
    exh_start = context.get("exhibition_start") or "?"
    exh_end = context.get("exhibition_end") or "?"
    shape = context.get("_shape", {})

    lines = [
        f"# {title}",
        "",
        f"**PP Number:** {pp}  ",
        f"**Council:** {council}  ",
        f"**Address:** {addresses}  ",
        f"**Exhibition:** {exh_start} to {exh_end}  ",
        f"**Type:** {context.get('pp_type', 'council-led')}",
        "",
    ]

    total_citations = 0
    verified_citations = 0

    for section in drafted:
        section_key = section["section"]
        section_title = SECTION_TITLES.get(section_key, section_key)

        # Skip empty concerns section — use fallback instead
        if section_key == "concerns" and (not section["text"] or not section["citations"]):
            lines.append(f"## {section_title}")
            lines.append("")
            lines.append(EMPTY_CONCERNS_FALLBACK)
            lines.append("")
            continue

        lines.append(f"## {section_title}")
        lines.append("")
        lines.append(section["text"])
        lines.append("")

        for c in section.get("citations", []):
            total_citations += 1
            if c.get("verified"):
                verified_citations += 1

    # References — built from citation data, NOT from text parsing
    all_citations = []
    for section in drafted:
        all_citations.extend(section.get("citations", []))

    if all_citations:
        lines.append("## References")
        lines.append("")
        seen = set()
        for c in all_citations:
            key = (c["document_title"], c["page"])
            if key not in seen:
                status = "verified" if c.get("verified") else "unverified"
                lines.append(f"- {c['document_title']}, p.{c['page']} — {status}")
                seen.add(key)

    lines.append("")
    lines.append("---")
    lines.append(f"*Citations resolved: {verified_citations}/{total_citations}.*")

    if fact_stats:
        l1 = fact_stats.get("l1_verified", 0)
        l2 = fact_stats.get("l2_verified", 0)
        unsup = fact_stats.get("unsupported", 0)
        incon = fact_stats.get("inconsistent", 0)
        total_f = l1 + l2 + unsup + incon
        if total_f > 0:
            parts = [f"*Facts verified: {l1 + l2}/{total_f} (L1: {l1}, L2: {l2})."]
            if unsup:
                parts.append(f"{unsup} unsupported.")
            if incon:
                parts.append(f"{incon} inconsistencies flagged.")
            lines.append(" ".join(parts) + "*")

    return "\n".join(lines)


def _save_audit_log(pp_number: str, drafted: list[dict], fact_stats: dict) -> None:
    """Save per-PP verification audit log."""
    import json
    os.makedirs("reports", exist_ok=True)
    audit = {
        "pp_number": pp_number,
        "fact_stats": fact_stats,
        "sections": [],
    }
    for section in drafted:
        section_data = {
            "section": section["section"],
            "citations": [],
        }
        for cit in section.get("citations", []):
            section_data["citations"].append({
                "document_title": cit.get("document_title"),
                "page": cit.get("page"),
                "claim": cit.get("claim", ""),
                "citation_verified": cit.get("verified", False),
                "fact_status": cit.get("fact_status"),
                "fact_layer": cit.get("fact_layer"),
                "fact_notes": cit.get("fact_notes", ""),
            })
        audit["sections"].append(section_data)

    path = f"reports/{pp_number}_verification.json"
    with open(path, "w") as f:
        json.dump(audit, f, indent=2)
    logger.info("Audit log saved: %s", path)


# --- Main pipeline ---

def generate_brief(pp_number: str) -> str:
    # ADC credentials used automatically via get_client()
    engine = create_db_engine()
    session = create_session(engine)

    try:
        # 1. Orient
        context = orient(session, pp_number)

        # 2. Draft
        drafted = draft(context)

        # 3. Citation verify
        drafted = verify(drafted, context, session)
        total = sum(len(s["citations"]) for s in drafted)
        ok = sum(1 for s in drafted for c in s["citations"] if c.get("verified"))
        logger.info("Citation verification: %d/%d supported", ok, total)

        # 4. Rewrite unsupported citations
        drafted = rewrite(drafted, context, session)
        total = sum(len(s["citations"]) for s in drafted)
        ok = sum(1 for s in drafted for c in s["citations"] if c.get("verified"))
        logger.info("After rewrite: %d/%d supported", ok, total)

        # 5. Fact verification (Layer 1 + Layer 2)
        drafted, fact_stats = verify_facts_node(drafted, context, session)

        # 6. Strip unsupported factual claims from brief text
        drafted = strip_unsupported_facts(drafted)

        # 7. Save audit log
        _save_audit_log(pp_number, drafted, fact_stats)

        # 7. Compose
        return compose(drafted, context, fact_stats=fact_stats)

    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("pp_number", help="e.g. PP-2023-2828")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    args = parser.parse_args()

    os.environ.setdefault("GOOGLE_API_KEY", open(".env").read().split("=")[1].strip())

    brief = generate_brief(args.pp_number)

    if args.output:
        with open(args.output, "w") as f:
            f.write(brief)
        print(f"Brief written to {args.output}")
    else:
        print(brief)
