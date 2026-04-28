"""Unit tests for all pipeline modules. No API calls, no brief generation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import re
from datetime import date

# ===================================================================
# llm_utils tests
# ===================================================================

def test_normalize_citations_multi_page():
    from pipeline.llm_utils import normalize_citations
    text = "[doc: Report | p.6, p.11, p.20]"
    result = normalize_citations(text)
    assert result == "[doc: Report | p.6][doc: Report | p.11][doc: Report | p.20]"

def test_normalize_citations_comma_format():
    from pipeline.llm_utils import normalize_citations
    text = "[doc: Some Report, p.14]"
    result = normalize_citations(text)
    assert result == "[doc: Some Report | p.14]"

def test_normalize_citations_single_page_unchanged():
    from pipeline.llm_utils import normalize_citations
    text = "[doc: Report | p.5]"
    assert normalize_citations(text) == text

def test_extract_citations():
    from pipeline.llm_utils import extract_citations
    text = "Fact one [doc: Report A | p.5]. Fact two [doc: Report B | p.12]."
    cites = extract_citations(text)
    assert len(cites) == 2
    assert cites[0]["document_title"] == "Report A"
    assert cites[0]["page"] == 5
    assert cites[1]["document_title"] == "Report B"
    assert cites[1]["page"] == 12

def test_extract_citations_duplicates_kept():
    from pipeline.llm_utils import extract_citations
    text = "A [doc: R | p.5]. B [doc: R | p.5]."
    cites = extract_citations(text)
    assert len(cites) == 2  # Both occurrences kept

def test_extract_claim_for_citation():
    from pipeline.llm_utils import extract_claim_for_citation
    text = "First sentence. The building is 44 metres tall [doc: R | p.5]. Next sentence."
    span = (47, 63)  # approximate span of citation
    # Find actual span
    import re
    m = re.search(r'\[doc: R \| p\.5\]', text)
    claim = extract_claim_for_citation(text, m.span())
    assert "44 metres" in claim
    assert "[doc:" not in claim

def test_format_chunks():
    from pipeline.llm_utils import format_chunks
    chunks = [{"document_title": "Test Doc", "page_number": 1, "text": "Hello world"}]
    result = format_chunks(chunks)
    assert "[DOCUMENT: Test Doc]" in result
    assert "[PAGE: 1]" in result
    assert "Hello world" in result

def test_load_prompt():
    from pipeline.llm_utils import load_prompt
    system = load_prompt("system")
    assert "citation" in system.lower()
    assert len(system) > 50

# ===================================================================
# verify_facts Layer 1 tests
# ===================================================================

def test_l1_number_match():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify("The site is 140 hectares", "The site covers 140 hectares of land")
    assert result.status == "verified"

def test_l1_number_mismatch():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify("The site is 140 hectares", "The site covers 116 hectares of land")
    assert result.status == "unsupported"

def test_l1_zone_codes():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify("rezoned from RU6 to R2", "rezoning from RU6 Rural Transition to R2 Low Density")
    assert result.status == "verified"

def test_l1_no_facts():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify("the proposal aims to revitalise the corner", "some text about revitalisation")
    assert result.status == "no_facts"

def test_l1_ratio():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify("a maximum FSR of 2.5:1", "the maximum floor space ratio is 2.5:1")
    assert result.status == "verified"

def test_l1_lot_dp():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify("Lot 133 DP 1081488 at Stan McCabe Drive", "The land is Lot 133 DP1081488 at Stan McCabe Drive")
    assert result.status == "verified"

def test_l1_year_anchored():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify("the 2021 Employment Lands Study", "Hornsby Employment Lands Study (March 2021)")
    assert result.status == "verified"

def test_l1_year_suppressed():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify("this could happen by 2031 if things go well", "planning horizon extends to 2031")
    assert result.status == "no_facts"  # Year suppressed — no anchor noun

def test_l1_directional_escalates():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify(
        "building height reduced from 16 metres to 9 metres",
        "maximum building height is 16 metres currently and proposed to be 9 metres",
    )
    assert result.status == "ambiguous"  # Needs L2 for direction check

def test_l1_comma_number():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify("approximately 4,300 new homes", "approximately 4,300 new homes featuring affordable housing")
    assert result.status == "verified"

def test_l1_money():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify("costing $2.5 million", "the project budget is $2.5 million")
    assert result.status == "verified"

def test_l1_clause():
    from pipeline.verify_facts import layer_1_verify
    result = layer_1_verify("under Clause 5.4 of the LEP", "pursuant to Clause 5.4 of the Local Environmental Plan")
    assert result.status == "verified"

# ===================================================================
# verify_facts L2 parser tests
# ===================================================================

def test_l2_parser_clean_json():
    from pipeline.verify_facts import _parse_l2_response
    raw = '{"verdict": "supported", "issues_found": [], "reasoning": "All facts match."}'
    result = _parse_l2_response(raw)
    assert result["verdict"] == "supported"

def test_l2_parser_code_fence():
    from pipeline.verify_facts import _parse_l2_response
    raw = '```json\n{"verdict": "unsupported", "issues_found": [], "reasoning": "No match."}\n```'
    result = _parse_l2_response(raw)
    assert result["verdict"] == "unsupported"

def test_l2_parser_preamble():
    from pipeline.verify_facts import _parse_l2_response
    raw = 'Sure, here is the JSON:\n{"verdict": "partially_supported", "reasoning": "Close."}'
    result = _parse_l2_response(raw)
    assert result["verdict"] == "partially_supported"

def test_l2_parser_truncated():
    from pipeline.verify_facts import _parse_l2_response
    raw = '{"verdict": "supported", "issues_found": ['
    result = _parse_l2_response(raw)
    assert result.get("_parse_failed") is True

def test_l2_canonicalize():
    from pipeline.verify_facts import _canonicalize_l2_result
    result = _canonicalize_l2_result({"Verdict": "SUPPORTED", "Reasoning": "ok"})
    assert result["verdict"] == "supported"

    result2 = _canonicalize_l2_result({"verdict": "not_supported"})
    assert result2["verdict"] == "unsupported"

    result3 = _canonicalize_l2_result({"verdict": "partially supported"})
    assert result3["verdict"] == "partially_supported"

# ===================================================================
# geocode tests
# ===================================================================

def test_haversine():
    from pipeline.geocode import haversine
    # Sydney to Melbourne ~713 km
    dist = haversine(-33.87, 151.21, -37.81, 144.96)
    assert 700 < dist < 730

def test_haversine_same_point():
    from pipeline.geocode import haversine
    assert haversine(-33.87, 151.21, -33.87, 151.21) == 0.0

# ===================================================================
# classify tests
# ===================================================================

def test_classify_tier1_category():
    from pipeline.classify import classify_by_category
    tier, concern = classify_by_category("Proposal for Public Exhibition")
    assert tier == 1

def test_classify_tier2_category():
    from pipeline.classify import classify_by_category
    tier, concern = classify_by_category("Traffic report")
    assert tier == 2
    assert concern == "traffic"

def test_classify_tier3_category():
    from pipeline.classify import classify_by_category
    tier, concern = classify_by_category("Gateway determination")
    assert tier == 3

def test_classify_title_overrides_category():
    from pipeline.classify import classify_by_title
    # Title says heritage, should be tier 2 even if category said tier 1
    tier, concern = classify_by_title("Heritage Impact Assessment Report")
    assert tier == 2
    assert concern == "heritage"

def test_classify_council_minutes_before_planning_proposal():
    from pipeline.classify import classify_by_title
    tier, _ = classify_by_title("Council Minutes - Planning Proposal to insert Additional Local Provision")
    assert tier == 3  # Council minutes, not a planning proposal

# ===================================================================
# components tests
# ===================================================================

def test_days_badge_future():
    from ui.components import days_badge
    from datetime import timedelta
    future = date.today() + timedelta(days=20)
    badge = days_badge(future)
    assert "20 days" in badge
    assert "green" in badge

def test_days_badge_urgent():
    from ui.components import days_badge
    from datetime import timedelta
    soon = date.today() + timedelta(days=3)
    badge = days_badge(soon)
    assert "3 days" in badge
    assert "red" in badge

def test_days_badge_closed():
    from ui.components import days_badge
    from datetime import timedelta
    past = date.today() - timedelta(days=5)
    badge = days_badge(past)
    assert "Closed" in badge

def test_days_badge_none():
    from ui.components import days_badge
    assert "Unknown" in days_badge(None)

def test_distance_label():
    from ui.components import distance_label
    assert "km" in distance_label(5.3, "address")
    assert "LGA" in distance_label(0, "lga_policy")
    assert "At your" in distance_label(0.05, "address")

# ===================================================================
# DB model tests
# ===================================================================

def test_pp_model_has_geocode_columns():
    from scraper.models import PP
    assert hasattr(PP, "latitude")
    assert hasattr(PP, "longitude")
    assert hasattr(PP, "geo_source")

def test_document_model_has_tier():
    from scraper.models import Document
    assert hasattr(Document, "tier")
    assert hasattr(Document, "sub_tier")
    assert hasattr(Document, "concern_tag")

def test_chunk_model():
    from scraper.models import Chunk
    assert hasattr(Chunk, "document_id")
    assert hasattr(Chunk, "page_number")
    assert hasattr(Chunk, "text")
    assert hasattr(Chunk, "extraction_method")

# ===================================================================
# prompt files exist
# ===================================================================

def test_all_prompts_exist():
    from pathlib import Path
    prompts_dir = Path("pipeline/prompts")
    expected = [
        "system.md", "draft.md", "verify.md", "rewrite.md",
        "section_summary.md", "section_proposed.md", "section_changes.md", "section_concerns.md",
        "empty_concerns.md",
        "verify_facts_system.md", "verify_facts_user.md",
        "submission_system.md", "submission_concern.md", "submission_compose.md",
        "qa_system.md", "qa_user.md",
    ]
    for name in expected:
        assert (prompts_dir / name).exists(), f"Missing prompt: {name}"

# ===================================================================
# Runner
# ===================================================================

if __name__ == "__main__":
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
            print(f"  PASS {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"  FAIL {test.__name__}: {e}")
            traceback.print_exc()

    print(f"\n{passed}/{passed + failed} passed")
    if failed:
        exit(1)
