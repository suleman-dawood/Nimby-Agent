"""Two-layer fact verification + cross-document consistency for brief claims.

Layer 1: Deterministic regex extraction + chunk matching (no LLM).
Layer 2: LLM verification for ambiguous cases (Gemini Flash).
Layer 3: Cross-document consistency check (deterministic, no LLM).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Literal

from google.genai import types as genai_types
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from pipeline.llm_utils import load_prompt


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ExtractedFact:
    kind: str
    raw: str
    normalized: str
    unit: str = ""
    layer_1_status: str = "pending"
    layer_1_notes: str = ""


@dataclass
class Contradiction:
    fact_in_claim: str
    alternative_value: str
    alternative_chunk_id: int
    alternative_doc_title: str
    alternative_page: int
    shared_topics: list[str]
    confidence: float


@dataclass
class FactVerificationResult:
    status: str  # verified, unsupported, ambiguous, no_facts, inconsistent
    layer_used: str = "skipped"
    extracted_facts: list[ExtractedFact] = field(default_factory=list)
    notes: str = ""
    escalation_reasons: list[str] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    raw_l2_response: str = ""


# ---------------------------------------------------------------------------
# Layer 1: Fact extraction patterns
# ---------------------------------------------------------------------------

_NUM_UNIT = re.compile(
    r'\b(\d+(?:,\d{3})*(?:\.\d+)?)\s+'
    r'(?:\w+\s+)?'
    r'(m²|m2|square\s*metres?|sqm|hectares?|ha|%|storeys?|storey'
    r'|kilometres?|km|metres?|dwellings?|homes?|lots?)\b',
    re.I,
)

_RATIO = re.compile(r'\b(\d+(?:\.\d+)?:\d+(?:\.\d+)?)\b')

_YEAR = re.compile(r'\b((?:19|20)\d{2})\b')
_YEAR_ANCHORS = re.compile(
    r'\b(study|plan|report|amendment|version|edition|published|since|dated|prepared|LEP|SEPP|DCP)\b',
    re.I,
)

_DATE_NUMERIC = re.compile(r'\b(\d{1,2}/\d{1,2}/\d{4})\b')
_DATE_WRITTEN = re.compile(
    r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b',
    re.I,
)

_PP_NUMBER = re.compile(r'\b(PP-\d{4}-\d+)\b')
_LOT_DP = re.compile(r'\b(Lot\s+\d+\s+(?:in\s+)?DP\s*\d+)\b', re.I)

_ZONE_CODE = re.compile(
    r'\b(R[1-5]|RU[1-6]|RE[1-2]|E[1-4]|SP[1-3]|MU\d|C[1-4]|B[1-8])\b(?=[\s,.;:]|$)'
)

_CLAUSE = re.compile(r'\b((?:Clause|Section|Schedule)\s+\d+(?:\.\d+)*[A-Z]?)\b', re.I)
_MONEY = re.compile(r'(\$\d+(?:[.,]\d+)?)\s*(million|m|billion|b)?\b', re.I)

_DIRECTIONAL = re.compile(
    r'\b((?:increas|reduc|chang|remov|introduc|rais|lower|amend)\w*)\s+'
    r'(?:from\s+)?(\d+(?:[.,]\d+)?(?:\s*(?:m²|m2|%|metres?|hectares?|ha|storeys?))?)'
    r'\s+to\s+'
    r'(\d+(?:[.,]\d+)?(?:\s*(?:m²|m2|%|metres?|hectares?|ha|storeys?))?)',
    re.I,
)


# ---------------------------------------------------------------------------
# Suppression rules
# ---------------------------------------------------------------------------

def _suppress_number(raw: str, unit: str, context: str, pos: int) -> bool:
    surrounding = context[max(0, pos - 30):pos + len(raw) + 30].lower()
    if unit.lower() == "m" and any(w in surrounding for w in ["million", "metropolitan", "mu"]):
        return True
    if re.search(r'\b(?:stage|part|phase|step|option|scenario)\s+' + re.escape(raw), surrounding):
        return True
    return False


def _suppress_year(year: str, context: str, pos: int) -> bool:
    window = context[max(0, pos - 40):pos + len(year) + 40]
    return not _YEAR_ANCHORS.search(window)


def _suppress_zone(code: str, context: str, pos: int) -> bool:
    before = context[max(0, pos - 10):pos].lower()
    if before.strip().endswith("the") and len(code) <= 2:
        after = context[pos:pos + 30].lower()
        if not any(w in after for w in ["zone", "zoning", "residential", "rural", "commercial",
                                         "industrial", "mixed", "environmental", "recreation"]):
            return True
    return False


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_UNIT_ALIASES = {
    "square metres": "m²", "square metre": "m²", "sqm": "m²", "m2": "m²",
    "hectares": "ha", "hectare": "ha",
    "metres": "m", "metre": "m",
    "kilometres": "km", "kilometre": "km",
    "storeys": "storey",
    "dwellings": "dwelling", "homes": "home", "lots": "lot",
}


def _normalize_number(num: str, unit: str) -> str:
    num = num.replace(",", "")
    unit_lower = unit.lower().strip()
    unit_norm = _UNIT_ALIASES.get(unit_lower, unit_lower)
    return f"{num} {unit_norm}"


def _get_unit(unit: str) -> str:
    return _UNIT_ALIASES.get(unit.lower().strip(), unit.lower().strip())


def _normalize_lot_dp(raw: str) -> str:
    s = re.sub(r'\s+', ' ', raw).strip().lower()
    s = re.sub(r'dp\s*', 'dp', s)
    return s


def _normalize_money(raw: str) -> str:
    return raw.lower().replace(",", "").strip()


def _normalize_chunk_text(text: str) -> str:
    t = text.lower()
    t = re.sub(r'\s+', ' ', t)
    for alias, norm in _UNIT_ALIASES.items():
        t = t.replace(alias, norm)
    t = t.replace("m2", "m²")
    t = re.sub(r'dp\s*(\d)', r'dp\1', t)
    t = re.sub(r'(\d),(\d)', r'\1\2', t)
    return t


def _has_approx_qualifier(claim: str) -> bool:
    return bool(re.search(r'\b(approximately|around|about|roughly)\b', claim, re.I))


# ---------------------------------------------------------------------------
# Layer 1: Extract
# ---------------------------------------------------------------------------

def extract_facts(claim: str) -> list[ExtractedFact]:
    facts: list[ExtractedFact] = []
    seen_raw: set[str] = set()

    for m in _DIRECTIONAL.finditer(claim):
        verb, val_from, val_to = m.group(1), m.group(2), m.group(3)
        raw = m.group(0)
        if raw not in seen_raw:
            seen_raw.add(raw)
            facts.append(ExtractedFact(kind="directional", raw=raw, normalized=f"{val_from} -> {val_to}"))

    for m in _NUM_UNIT.finditer(claim):
        raw = m.group(0).strip()
        if raw in seen_raw:
            continue
        num, unit = m.group(1), m.group(2)
        if _suppress_number(num, unit, claim, m.start()):
            continue
        seen_raw.add(raw)
        facts.append(ExtractedFact(kind="number", raw=raw, normalized=_normalize_number(num, unit), unit=_get_unit(unit)))

    for m in _RATIO.finditer(claim):
        raw = m.group(1)
        if raw not in seen_raw:
            seen_raw.add(raw)
            facts.append(ExtractedFact(kind="ratio", raw=raw, normalized=raw, unit="ratio"))

    for m in _YEAR.finditer(claim):
        year = m.group(1)
        if year in seen_raw or _suppress_year(year, claim, m.start()):
            continue
        seen_raw.add(year)
        facts.append(ExtractedFact(kind="year", raw=year, normalized=year))

    for m in _DATE_NUMERIC.finditer(claim):
        raw = m.group(1)
        if raw not in seen_raw:
            seen_raw.add(raw)
            facts.append(ExtractedFact(kind="date", raw=raw, normalized=raw))

    for m in _DATE_WRITTEN.finditer(claim):
        raw = m.group(1)
        if raw not in seen_raw:
            seen_raw.add(raw)
            facts.append(ExtractedFact(kind="date", raw=raw, normalized=raw))

    for m in _PP_NUMBER.finditer(claim):
        raw = m.group(1)
        if raw not in seen_raw:
            seen_raw.add(raw)
            facts.append(ExtractedFact(kind="identifier", raw=raw, normalized=raw))

    for m in _LOT_DP.finditer(claim):
        raw = m.group(1)
        if raw not in seen_raw:
            seen_raw.add(raw)
            facts.append(ExtractedFact(kind="identifier", raw=raw, normalized=_normalize_lot_dp(raw)))

    for m in _ZONE_CODE.finditer(claim):
        code = m.group(1)
        if code in seen_raw or _suppress_zone(code, claim, m.start()):
            continue
        seen_raw.add(code)
        facts.append(ExtractedFact(kind="zone", raw=code, normalized=code))

    for m in _CLAUSE.finditer(claim):
        raw = m.group(1)
        if raw not in seen_raw:
            seen_raw.add(raw)
            facts.append(ExtractedFact(kind="clause", raw=raw, normalized=raw.lower()))

    for m in _MONEY.finditer(claim):
        raw = m.group(0).strip()
        if raw not in seen_raw:
            seen_raw.add(raw)
            facts.append(ExtractedFact(kind="money", raw=raw, normalized=_normalize_money(raw)))

    return facts


# ---------------------------------------------------------------------------
# Layer 1: Match
# ---------------------------------------------------------------------------

def match_facts(
    facts: list[ExtractedFact],
    chunk_text: str,
    claim: str,
) -> tuple[list[ExtractedFact], list[str]]:
    chunk_norm = _normalize_chunk_text(chunk_text)
    approx = _has_approx_qualifier(claim)
    escalation_reasons: list[str] = []

    for fact in facts:
        if fact.kind == "directional":
            parts = fact.normalized.split(" -> ")
            if len(parts) == 2:
                x_norm = _normalize_chunk_text(parts[0].strip())
                y_norm = _normalize_chunk_text(parts[1].strip())
                x_num = re.match(r'[\d,.]+', x_norm)
                y_num = re.match(r'[\d,.]+', y_norm)
                x_found = x_norm in chunk_norm or (x_num and x_num.group() in chunk_norm)
                y_found = y_norm in chunk_norm or (y_num and y_num.group() in chunk_norm)
                if x_found and y_found:
                    fact.layer_1_status = "escalate"
                    fact.layer_1_notes = "Both values found; direction needs L2 check"
                    escalation_reasons.append("direction")
                else:
                    fact.layer_1_status = "missing"
                    missing = []
                    if not x_found:
                        missing.append(f"from-value '{parts[0].strip()}'")
                    if not y_found:
                        missing.append(f"to-value '{parts[1].strip()}'")
                    fact.layer_1_notes = f"Missing: {', '.join(missing)}"
            continue

        normalized = fact.normalized.lower().replace(",", "")

        if fact.kind == "number":
            num_match = re.match(r'([\d.]+)\s+(.*)', normalized)
            if num_match:
                num_val = num_match.group(1)
                unit_val = num_match.group(2).strip()
                num_found = num_val in chunk_norm
                unit_found = unit_val in chunk_norm
                matched = num_found and unit_found
            else:
                matched = normalized in chunk_norm
        else:
            matched = normalized in chunk_norm

        if matched:
            if fact.kind == "number":
                num_match = re.match(r'([\d.]+)\s+(.*)', normalized)
                if num_match:
                    unit_val = num_match.group(2).strip()
                    if unit_val:
                        unit_matches = re.findall(r'\d+(?:[.,]\d+)?\s*' + re.escape(unit_val), chunk_norm)
                        if len(unit_matches) > 2:
                            fact.layer_1_status = "escalate"
                            fact.layer_1_notes = f"Found {len(unit_matches)} numbers with unit '{unit_val}'"
                            escalation_reasons.append("scope")
                            continue

            fact.layer_1_status = "matched"
            fact.layer_1_notes = "Exact match in chunk"
        else:
            if fact.kind == "number" and approx:
                num_match = re.match(r'([\d.]+)', normalized)
                if num_match:
                    claim_val = float(num_match.group(1))
                    unit_part = normalized[num_match.end():].strip()
                    if unit_part:
                        for m in re.finditer(r'([\d,.]+)\s*' + re.escape(unit_part), chunk_norm):
                            try:
                                chunk_val = float(m.group(1).replace(",", ""))
                                if abs(chunk_val - claim_val) / max(claim_val, 1) <= 0.05:
                                    fact.layer_1_status = "matched"
                                    fact.layer_1_notes = f"Approximate match: claim={claim_val}, source={chunk_val}"
                                    break
                            except ValueError:
                                continue

                        if fact.layer_1_status != "matched":
                            for m in re.finditer(r'([\d,.]+)\s*' + re.escape(unit_part), chunk_norm):
                                try:
                                    chunk_val = float(m.group(1).replace(",", ""))
                                    if abs(chunk_val - claim_val) / max(claim_val, 1) <= 0.20:
                                        fact.layer_1_status = "escalate"
                                        fact.layer_1_notes = f"Close but beyond 5%: claim={claim_val}, source={chunk_val}"
                                        escalation_reasons.append("rounding")
                                        break
                                except ValueError:
                                    continue

            if fact.layer_1_status == "pending":
                fact.layer_1_status = "missing"
                fact.layer_1_notes = "Not found in chunk"

    return facts, escalation_reasons


def layer_1_verify(claim: str, chunk_text: str) -> FactVerificationResult:
    facts = extract_facts(claim)
    if not facts:
        return FactVerificationResult(status="no_facts", layer_used="skipped", extracted_facts=[],
                                       notes="No verifiable facts extracted from claim")

    facts, escalation_reasons = match_facts(facts, chunk_text, claim)

    has_missing = any(f.layer_1_status == "missing" for f in facts)
    has_escalate = any(f.layer_1_status == "escalate" for f in facts)
    all_matched = all(f.layer_1_status == "matched" for f in facts)

    if all_matched:
        return FactVerificationResult(status="verified", layer_used="L1", extracted_facts=facts)
    elif has_missing and not has_escalate:
        missing_facts = [f for f in facts if f.layer_1_status == "missing"]
        return FactVerificationResult(
            status="unsupported", layer_used="L1", extracted_facts=facts,
            notes="; ".join(f"{f.kind} '{f.raw}': {f.layer_1_notes}" for f in missing_facts))
    else:
        return FactVerificationResult(
            status="ambiguous", layer_used="L1", extracted_facts=facts,
            escalation_reasons=list(set(escalation_reasons)), notes="Escalating to Layer 2")


# ---------------------------------------------------------------------------
# Layer 2: LLM verification (with robust parser)
# ---------------------------------------------------------------------------

def _parse_l2_response(raw: str) -> dict:
    """Robustly parse L2 JSON response from Gemini Flash."""
    text = raw.strip()
    # Strip code fences
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    # Strip preambles
    for preamble in ["Sure, here is the JSON:", "Here is the response:",
                      "Response:", "JSON:", "Here's the JSON:"]:
        if text.lower().startswith(preamble.lower()):
            text = text[len(preamble):].strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Substring extraction fallback
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1 and last > first:
        try:
            return json.loads(text[first:last + 1])
        except json.JSONDecodeError:
            pass
    return {"_parse_failed": True, "_raw": text[:200]}


def _canonicalize_l2_result(parsed: dict) -> dict:
    """Normalize L2 response keys and verdict values."""
    norm = {k.lower(): v for k, v in parsed.items()}
    verdict_aliases = {
        "support": "supported", "supported": "supported",
        "partial": "partially_supported",
        "partially_supported": "partially_supported",
        "partially supported": "partially_supported",
        "unsupport": "unsupported", "unsupported": "unsupported",
        "not_supported": "unsupported", "not supported": "unsupported",
    }
    verdict = str(norm.get("verdict", "")).lower().strip()
    norm["verdict"] = verdict_aliases.get(verdict, "unsupported")
    return norm


def layer_2_verify(
    claim: str,
    chunk_text: str,
    chunk_metadata: dict,
    escalation_reasons: list[str],
) -> FactVerificationResult:
    system = load_prompt("verify_facts_system")
    user = load_prompt("verify_facts_user").format(
        claim_sentence=claim,
        document_title=chunk_metadata.get("document_title", "Unknown"),
        page_number=chunk_metadata.get("page_number", "?"),
        chunk_text=chunk_text[:2500],
        flagged_aspects=", ".join(escalation_reasons),
    )

    from pipeline.llm_utils import get_client
    client = get_client()
    config = genai_types.GenerateContentConfig(
        system_instruction=system,
        temperature=0,
        max_output_tokens=800,
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user,
            config=config,
        )
        raw_text = response.text.strip()

        parsed = _parse_l2_response(raw_text)

        if parsed.get("_parse_failed"):
            return FactVerificationResult(
                status="unsupported", layer_used="L2",
                notes=f"parse_failure: {parsed.get('_raw', '')[:200]}",
                raw_l2_response=raw_text,
            )

        result = _canonicalize_l2_result(parsed)
        verdict = result["verdict"]
        issues = result.get("issues_found", [])
        reasoning = result.get("reasoning", "")

        status = "verified" if verdict == "supported" else "unsupported"

        notes_parts = [reasoning]
        for issue in (issues if isinstance(issues, list) else []):
            if isinstance(issue, dict):
                notes_parts.append(f"[{issue.get('aspect', '?')}] {issue.get('issue', '')}")

        return FactVerificationResult(
            status=status, layer_used="L2",
            notes="; ".join(p for p in notes_parts if p),
            raw_l2_response=raw_text,
        )

    except Exception as e:
        logger.error("Layer 2 verification failed: %s", e)
        return FactVerificationResult(status="unsupported", layer_used="L2", notes=f"L2 error: {e}")


# ---------------------------------------------------------------------------
# Layer 3: Cross-document consistency
# ---------------------------------------------------------------------------

PLANNING_TOPICS = {
    "green_space": ["green space", "open space", "park", "reserve", "public open space",
                     "recreation", "vegetation", "ecological"],
    "site_area": ["site area", "total area", "land area", "hectares of land"],
    "lot_size": ["minimum lot size", "subdivision lot size", "minimum subdivision"],
    "building_height": ["building height", "maximum height", "storeys", "metres tall", "floor levels"],
    "fsr": ["floor space ratio", "fsr", "floor area ratio"],
    "dwellings": ["dwelling", "homes", "houses", "apartments", "residential units"],
    "retail": ["retail", "shops", "supermarket", "commercial floorspace"],
    "tourism": ["tourist", "tourism", "hotel", "cabin"],
    "infrastructure": ["road", "bypass", "infrastructure", "water", "sewer", "drainage"],
    "heritage": ["heritage", "aboriginal", "indigenous"],
    "environmental": ["bushfire", "flood", "ecology", "biodiversity", "contamination"],
    "traffic": ["traffic", "transport", "vehicle", "intersection"],
    "money": ["dollars", "$", "million", "contribution", "cost"],
    "timeline": ["stage", "year", "completion", "target"],
}

# Specific topics = higher confidence when matched
_SPECIFIC_TOPICS = {"lot_size", "building_height", "fsr", "green_space", "site_area", "dwellings"}


@dataclass
class IndexedNumber:
    chunk_id: int
    doc_title: str
    page: int
    value: str
    normalized: str
    unit: str
    surrounding_text: str


def _derive_topics(text: str) -> set[str]:
    text_lower = text.lower()
    topics = set()
    for topic, keywords in PLANNING_TOPICS.items():
        if any(kw in text_lower for kw in keywords):
            topics.add(topic)
    return topics


def build_numeric_index(session: Session, pp_number: str) -> list[IndexedNumber]:
    """Extract all numbers from all T1+T2 chunks for a PP."""
    from scraper.models import Chunk, Document

    chunks = (
        session.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.pp_number == pp_number, Document.tier.in_([1, 2]),
                Chunk.extraction_method == "pdfplumber")
        .all()
    )

    index: list[IndexedNumber] = []

    for chunk, doc in chunks:
        for m in _NUM_UNIT.finditer(chunk.text):
            num, unit = m.group(1), m.group(2)
            start = max(0, m.start() - 100)
            end = min(len(chunk.text), m.end() + 100)
            surrounding = chunk.text[start:end]

            index.append(IndexedNumber(
                chunk_id=chunk.id,
                doc_title=doc.title or "",
                page=chunk.page_number,
                value=m.group(0).strip(),
                normalized=_normalize_number(num, unit),
                unit=_get_unit(unit),
                surrounding_text=surrounding,
            ))

        for m in _RATIO.finditer(chunk.text):
            start = max(0, m.start() - 100)
            end = min(len(chunk.text), m.end() + 100)
            surrounding = chunk.text[start:end]
            index.append(IndexedNumber(
                chunk_id=chunk.id,
                doc_title=doc.title or "",
                page=chunk.page_number,
                value=m.group(0),
                normalized=m.group(1),
                unit="ratio",
                surrounding_text=surrounding,
            ))

    return index


# Cache per PP to avoid rebuilding
_numeric_index_cache: dict[str, list[IndexedNumber]] = {}


def _get_numeric_index(session: Session, pp_number: str) -> list[IndexedNumber]:
    if pp_number not in _numeric_index_cache:
        _numeric_index_cache[pp_number] = build_numeric_index(session, pp_number)
        logger.info("Built numeric index for %s: %d entries", pp_number, len(_numeric_index_cache[pp_number]))
    return _numeric_index_cache[pp_number]


def layer_3_consistency(
    claim: str,
    facts: list[ExtractedFact],
    cited_chunk_id: int | None,
    session: Session,
    pp_number: str,
) -> list[Contradiction]:
    """Check verified facts against the full PP corpus for contradictions."""
    index = _get_numeric_index(session, pp_number)
    claim_topics = _derive_topics(claim)
    contradictions: list[Contradiction] = []

    for fact in facts:
        if fact.layer_1_status != "matched":
            continue
        if fact.kind not in ("number", "ratio"):
            continue

        # Skip ratio range endpoints — "from 0.2:1 to 2.5:1" contains both values
        # and the other endpoint isn't a contradiction
        if fact.kind == "ratio" and ("to" in claim.lower() or "range" in claim.lower()):
            continue

        fact_norm = fact.normalized.lower().replace(",", "")
        fact_unit = fact.unit.lower() if fact.unit else ""

        for entry in index:
            if entry.chunk_id == cited_chunk_id:
                continue
            if entry.unit.lower() != fact_unit:
                continue

            entry_norm = entry.normalized.lower().replace(",", "")
            if entry_norm == fact_norm:
                continue  # Same value — no contradiction

            # Check topic overlap
            entry_topics = _derive_topics(entry.surrounding_text)
            shared = claim_topics & entry_topics

            if not shared:
                continue

            # Confidence scoring — be conservative to avoid false positives
            # Planning docs legitimately have many different heights, areas, ratios
            # for different zones/uses. Only flag when context is very similar.
            has_specific = bool(shared & _SPECIFIC_TOPICS)

            # Check if the numbers are in a similar range (within 2x)
            # Wildly different numbers (4,300 vs 377,000) are usually different facts
            try:
                claim_num = float(re.match(r'[\d,.]+', fact_norm).group().replace(",", ""))
                entry_num = float(re.match(r'[\d,.]+', entry_norm).group().replace(",", ""))
                ratio = max(claim_num, entry_num) / max(min(claim_num, entry_num), 0.001)
                if ratio > 5:
                    continue  # Too different — probably different facts, not a contradiction
            except (ValueError, AttributeError):
                pass

            if len(shared) >= 3 and has_specific:
                confidence = 0.9
            elif len(shared) >= 2 and has_specific:
                confidence = 0.7
            elif has_specific:
                confidence = 0.5
            else:
                confidence = 0.3

            if confidence < 0.7:
                continue

            contradictions.append(Contradiction(
                fact_in_claim=fact.raw,
                alternative_value=entry.value,
                alternative_chunk_id=entry.chunk_id,
                alternative_doc_title=entry.doc_title,
                alternative_page=entry.page,
                shared_topics=sorted(shared),
                confidence=confidence,
            ))

    # Deduplicate: keep highest confidence per (fact, alternative_value)
    seen: dict[tuple[str, str], Contradiction] = {}
    for c in contradictions:
        key = (c.fact_in_claim, c.alternative_value)
        if key not in seen or c.confidence > seen[key].confidence:
            seen[key] = c

    return sorted(seen.values(), key=lambda c: -c.confidence)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def verify_claim_facts(
    claim_sentence: str,
    chunk_text: str,
    chunk_metadata: dict,
    session: Session | None = None,
    pp_number: str | None = None,
    cited_chunk_id: int | None = None,
) -> FactVerificationResult:
    """Run L1 → L2 (if ambiguous) → L3 (if verified). Returns final result."""
    result = layer_1_verify(claim_sentence, chunk_text)

    # L2 for ambiguous
    if result.status == "ambiguous":
        logger.info("  L1 → ambiguous (%s), escalating to L2", ", ".join(result.escalation_reasons))
        l2_result = layer_2_verify(
            claim_sentence, chunk_text, chunk_metadata, result.escalation_reasons,
        )
        l2_result.extracted_facts = result.extracted_facts
        result = l2_result

    # L3 disabled — too many false positives on planning docs where
    # multiple legitimate values exist for the same unit across zones/uses.
    # Keep the code for future use but don't run it.
    # if result.status == "verified" and session and pp_number:
    #     contradictions = layer_3_consistency(...)


    return result
