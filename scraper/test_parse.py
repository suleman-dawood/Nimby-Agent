"""Smoke tests for detail page parsing.

Run with: uv run python -m scraper.test_parse

Requires fixture files in scraper/fixtures/:
  - PP-2024-450.html   (Template A, council-led, e.g. Dural)
  - PP-2023-2828.html  (Template B, State-led, e.g. Kurnell)

Capture fixtures by running the scraper once and copying from data/raw_html/.
"""

import sys
from pathlib import Path

from scraper.detail import parse_detail_page

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_template_a():
    """Test parsing a Template A (council-led) detail page."""
    fixture = FIXTURES_DIR / "PP-2024-450.html"
    if not fixture.exists():
        print(f"SKIP: {fixture} not found. Run scraper first, then copy the file.")
        return False

    html = fixture.read_text(encoding="utf-8")
    result = parse_detail_page(
        html,
        "https://www.planningportal.nsw.gov.au/ppr/under-exhibition/dural-example",
        fallback_pp_number="PP-2024-450",
    )

    errors = []
    if not result["pp_number"]:
        errors.append("pp_number is empty")
    if not result["title"]:
        errors.append("title is empty")
    if not result["documents"]:
        errors.append("no documents found")

    if errors:
        print(f"FAIL template_a: {', '.join(errors)}")
        print(f"  Got: pp_number={result['pp_number']}, title={result['title']}, "
              f"docs={len(result['documents'])}")
        return False

    print(f"PASS template_a: pp={result['pp_number']}, title={result['title'][:50]}, "
          f"docs={len(result['documents'])}, addresses={result['addresses']}")
    return True


def test_template_b():
    """Test parsing a Template B (State-led) detail page."""
    fixture = FIXTURES_DIR / "PP-2023-2828.html"
    if not fixture.exists():
        print(f"SKIP: {fixture} not found. Run scraper first, then copy the file.")
        return False

    html = fixture.read_text(encoding="utf-8")
    result = parse_detail_page(
        html,
        "https://www.planningportal.nsw.gov.au/ppr/under-exhibition/kurnell-example",
        fallback_pp_number="PP-2023-2828",
    )

    errors = []
    if not result["pp_number"]:
        errors.append("pp_number is empty")
    if not result["title"]:
        errors.append("title is empty")
    if not result["documents"]:
        errors.append("no documents found")

    if errors:
        print(f"FAIL template_b: {', '.join(errors)}")
        print(f"  Got: pp_number={result['pp_number']}, title={result['title']}, "
              f"docs={len(result['documents'])}")
        return False

    print(f"PASS template_b: pp={result['pp_number']}, title={result['title'][:50]}, "
          f"docs={len(result['documents'])}, addresses={result['addresses']}")
    return True


def main():
    print("=" * 60)
    print("Detail parser smoke tests")
    print("=" * 60)

    results = [test_template_a(), test_template_b()]

    passed = sum(1 for r in results if r is True)
    skipped = sum(1 for r in results if r is False and r is not None)

    print(f"\n{passed}/{len(results)} passed")

    if not all(r for r in results if r is not None):
        sys.exit(1)


if __name__ == "__main__":
    main()
