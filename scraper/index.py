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

INDEX_URL = "https://www.planningportal.nsw.gov.au/ppr/under%20exhibition"
BASE_URL = "https://www.planningportal.nsw.gov.au"


def _parse_index_page(html: str) -> list[dict]:
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

    for card in soup.find_all("div", class_="card__content"):
        # Detail URL from the "Read" link
        read_link = card.find("a", href=lambda h: h and "/ppr/under-exhibition/" in h)
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


def fetch_index(client: httpx.Client, data_dir: Path) -> list[dict]:
    """Fetch all index pages and return list of PP entries."""
    raw_html_dir = data_dir / "raw_html"
    raw_html_dir.mkdir(parents=True, exist_ok=True)

    all_entries: list[dict] = []
    url: str | None = INDEX_URL
    page_num = 0

    while url:
        logger.info("Fetching index page %d: %s", page_num, url)
        resp = fetch(client, url)
        html = resp.text

        # Save raw HTML
        if page_num == 0:
            (raw_html_dir / "_index.html").write_text(html, encoding="utf-8")
        else:
            (raw_html_dir / f"_index_{page_num}.html").write_text(html, encoding="utf-8")

        entries = _parse_index_page(html)
        all_entries.extend(entries)
        logger.info("Found %d PP entries on page %d", len(entries), page_num)

        url = _find_next_page_url(html, url)
        page_num += 1

    # Final dedup across pages
    seen = set()
    deduped = []
    for e in all_entries:
        if e["detail_url"] not in seen:
            seen.add(e["detail_url"])
            deduped.append(e)

    logger.info("Total unique PP entries: %d", len(deduped))
    return deduped
