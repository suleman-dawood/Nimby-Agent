"""Scraper index unit tests."""

from scraper.index import STAGE_URLS, _parse_index_page


def test_stage_urls_complete():
    expected = [
        "Pre-Gateway",
        "Under Assessment",
        "Under Exhibition",
        "Post-Exhibition",
        "Exhibition Closed",
        "Finalised",
    ]
    for stage in expected:
        assert stage in STAGE_URLS, f"Missing stage: {stage}"


def test_stage_urls_valid():
    for stage, url in STAGE_URLS.items():
        assert url.startswith("https://www.planningportal.nsw.gov.au/ppr/")


def test_parse_empty_html():
    result = _parse_index_page("<html><body></body></html>", "Under Exhibition")
    assert result == []
