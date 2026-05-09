"""Parse the PPR index page to discover all Planning Proposal URLs."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import httpx

from scraper.fetch import fetch

logger = logging.getLogger(__name__)

BASE_URL = "https://www.planningportal.nsw.gov.au"

STAGE_URLS = {
    "Pre-Gateway": f"{BASE_URL}/ppr/pre-gateway",
    "Under Assessment": f"{BASE_URL}/ppr/under%20assessment",
    "Under Exhibition": f"{BASE_URL}/ppr/under%20exhibition",
    "Post-Exhibition": f"{BASE_URL}/ppr/post-exhibition",
    "Exhibition Closed": f"{BASE_URL}/ppr/exhibition-closed",
    "Finalised": f"{BASE_URL}/ppr/finalised",
}

# URL path slugs used in read links per stage
_STAGE_PATH_SLUGS = {
    "Pre-Gateway": "pre-gateway",
    "Under Assessment": "under-assessment",
    "Under Exhibition": "under-exhibition",
    "Post-Exhibition": "post-exhibition",
    "Exhibition Closed": "exhibition-closed",
    "Finalised": "finalised",
}

# Default: only scrape stages with actionable proposals
DEFAULT_STAGES = ["Under Exhibition"]


def _parse_index_page(html: str, stage: str = "Under Exhibition") -> list[dict]:
    """Extract PP tiles from a single index page.

    Tile structure:
        div.card__content
          div.tag           -> "Under Exhibition"
          div.row           -> PP number
          h3.card__title    -> full title (includes PP number)
          div               -> council/LGA
          div > a[href]     -> "Read" link to detail page
    """
    soup = BeautifulSoup(html, "lxml")
    results = []

    path_slug = _STAGE_PATH_SLUGS.get(stage, "under-exhibition")

    for card in soup.find_all("div", class_="card__content"):
        # Detail URL from the "Read" link — match any /ppr/{stage-slug}/ pattern
        read_link = card.find("a", href=lambda h: h and f"/ppr/{path_slug}/" in h)
        if not read_link:
            # Fallback: match any /ppr/ link
            read_link = card.find("a", href=lambda h: h and "/ppr/" in h and "/ppr/under" not in h or h and f"/ppr/{path_slug}/" in h)
            if not read_link:
                continue

        href = read_link["href"]
        detail_url = urljoin(BASE_URL, href)
        slug = href.rstrip("/").split("/")[-1]

        # PP number from div.row or h3 text
        pp_number = None
        row_div = card.find("div", class_="row")
        if row_div:
            pp_match = re.search(r"PP-\d{4}-\d+", row_div.get_text())
            if pp_match:
                pp_number = pp_match.group(0)

        # Title from h3.card__title
        title = None
        h3 = card.find("h3", class_="card__title")
        if h3:
            title = h3.get_text(strip=True)

        # Fallback: extract PP number from title or slug
        if not pp_number and title:
            pp_match = re.search(r"PP-\d{4}-\d+", title)
            if pp_match:
                pp_number = pp_match.group(0)

        results.append({
            "pp_number": pp_number,
            "title": title,
            "detail_url": detail_url,
            "slug": slug,
            "stage": stage,
        })

    # Deduplicate by detail_url
    seen = set()
    deduped = []
    for r in results:
        if r["detail_url"] not in seen:
            seen.add(r["detail_url"])
            deduped.append(r)

    return deduped


def _find_next_page_url(html: str, current_url: str) -> str | None:
    """Find the 'next page' URL from pagination.

    Portal uses:
        li.pager__next > a[href="?page=N"]
    """
    soup = BeautifulSoup(html, "lxml")

    # Primary: li.pager__next
    pager_next = soup.find("li", class_="pager__next")
    if pager_next:
        a = pager_next.find("a", href=True)
        if a:
            # href is relative like "?page=1", resolve against current URL
            return urljoin(current_url, a["href"])

    # Fallback: rel="next"
    next_link = soup.find("a", {"rel": "next"})
    if next_link and next_link.get("href"):
        return urljoin(current_url, next_link["href"])

    return None


def _fetch_stage(client: httpx.Client, data_dir: Path, stage: str) -> list[dict]:
    """Fetch all index pages for a single stage and return PP entries."""
    raw_html_dir = data_dir / "raw_html"
    raw_html_dir.mkdir(parents=True, exist_ok=True)

    stage_url = STAGE_URLS.get(stage)
    if not stage_url:
        logger.warning("Unknown stage: %s", stage)
        return []

    all_entries: list[dict] = []
    url: str | None = stage_url
    page_num = 0

    while url:
        logger.info("Fetching %s page %d: %s", stage, page_num, url)
        resp = fetch(client, url)
        html = resp.text

        safe_stage = stage.lower().replace(" ", "_")
        filename = f"_index_{safe_stage}.html" if page_num == 0 else f"_index_{safe_stage}_{page_num}.html"
        (raw_html_dir / filename).write_text(html, encoding="utf-8")

        entries = _parse_index_page(html, stage=stage)
        all_entries.extend(entries)
        logger.info("Found %d PP entries on %s page %d", len(entries), stage, page_num)

        url = _find_next_page_url(html, url)
        page_num += 1

    return all_entries


def fetch_index(client: httpx.Client, data_dir: Path) -> list[dict]:
    """Fetch Under Exhibition index pages. Backward-compatible entry point."""
    return fetch_all_stages(client, data_dir, stages=["Under Exhibition"])


def fetch_all_stages(
    client: httpx.Client, data_dir: Path, stages: list[str] | None = None,
) -> list[dict]:
    """Fetch index pages for multiple stages. Default: all stages."""
    if stages is None:
        stages = list(STAGE_URLS.keys())

    all_entries: list[dict] = []
    for stage in stages:
        entries = _fetch_stage(client, data_dir, stage)
        all_entries.extend(entries)

    # Final dedup across stages (same PP may appear in multiple)
    seen = set()
    deduped = []
    for e in all_entries:
        if e["detail_url"] not in seen:
            seen.add(e["detail_url"])
            deduped.append(e)

    logger.info("Total unique PP entries across %d stages: %d", len(stages), len(deduped))
    return deduped
