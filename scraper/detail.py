"""Parse a PP detail page to extract metadata and document list.

Handles two known templates:
- Template A (council-led): "Documents (N)" section with individual entries
- Template B (State-led rezonings): grouped sections like "Exhibition Documents"
"""

from __future__ import annotations

import logging
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag
from dateutil import parser as dateparser

import httpx

from scraper.fetch import fetch

logger = logging.getLogger(__name__)

BASE_URL = "https://www.planningportal.nsw.gov.au"
DOC_API_BASE = "https://apps.planningportal.nsw.gov.au"


def _parse_date(text: str) -> date | None:
    """Parse a date string, expecting DD/MM/YYYY but tolerant of variations."""
    if not text or not text.strip():
        return None
    try:
        return dateparser.parse(text.strip(), dayfirst=True).date()
    except (ValueError, TypeError):
        logger.warning("Could not parse date: %r", text)
        return None


def _clean_text(text: str | None) -> str | None:
    """Strip and normalize whitespace."""
    if not text:
        return None
    return re.sub(r"\s+", " ", text.strip()) or None


def _parse_activity_details(soup: BeautifulSoup) -> dict[str, str]:
    """Extract all label->value pairs from the Activity Details sidebar.

    Portal structure:
        div.project__details
          div.spacing--bottom-m
            div.row.row--small   (repeated)
              <b>Label</b>
              <div>Value</div>
    """
    fields: dict[str, str] = {}

    details = soup.find("div", class_="project__details")
    if not details:
        return fields

    for row in details.find_all("div", class_="row"):
        b_tag = row.find("b")
        if not b_tag:
            continue
        label = b_tag.get_text(strip=True)
        val_div = b_tag.find_next_sibling("div")
        if val_div:
            value = val_div.get_text(strip=True)
            if value:
                fields[label] = value

    return fields


def _extract_addresses(fields: dict[str, str], soup: BeautifulSoup) -> list[str]:
    """Extract address list from parsed activity detail fields.

    Some PPs have multi-line addresses separated by <br> tags.
    Use get_text(separator='|') on the raw div to split them.
    """
    addresses = []

    # First try to get the raw address div for <br>-separated addresses
    details = soup.find("div", class_="project__details")
    if details:
        for row in details.find_all("div", class_="row"):
            b_tag = row.find("b")
            if b_tag and b_tag.get_text(strip=True) in ("Address", "Addresses"):
                val_div = b_tag.find_next_sibling("div")
                if val_div:
                    # Use | as separator to split on <br> tags
                    raw = val_div.get_text(separator="|", strip=True)
                    for addr in raw.split("|"):
                        addr = addr.strip()
                        if addr:
                            addresses.append(addr)
                    return addresses

    # Fallback: use the text field
    addr_text = fields.get("Address") or fields.get("Addresses") or ""
    if addr_text:
        for addr in re.split(r"[;\n]", addr_text):
            addr = addr.strip()
            if addr:
                addresses.append(addr)

    return addresses


def _extract_documents_template_a(soup: BeautifulSoup) -> list[dict]:
    """Template A: "Documents (N)" section with individual doc entries.

    Portal structure:
        div.row.row--small
          div.row__fill
            div.row__results__category  -> category
            div                         -> document title
          div.row__fill
            a[href=...PublicDocuments...]  -> "View" link
    """
    docs = []

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "PublicDocuments" not in href and "DocMgmt" not in href:
            continue

        doc_url = urljoin(DOC_API_BASE, href) if href.startswith("/") else href

        # Walk up to the row container (div.row)
        row = link.find_parent("div", class_=re.compile(r"\brow\b"))

        title = "Untitled"
        category = None

        if row:
            # Category from div.row__results__category
            cat_el = row.find("div", class_=re.compile(r"category", re.I))
            if cat_el:
                category = _clean_text(cat_el.get_text())

            # Title from the sibling div inside the first row__fill
            first_fill = row.find("div", class_="row__fill")
            if first_fill:
                # Title is in a plain div (not the category div)
                for div in first_fill.find_all("div"):
                    cls = div.get("class") or []
                    if any("category" in c for c in cls):
                        continue
                    text = _clean_text(div.get_text())
                    if text:
                        title = text
                        break

        # Fallback: try parent text minus "View"
        if title == "Untitled":
            parent = link.parent
            if parent:
                parent_text = _clean_text(parent.get_text())
                if parent_text and parent_text.lower() != "view":
                    title = parent_text

        docs.append({
            "title": title,
            "category": category,
            "url": doc_url,
        })

    return docs


def _extract_documents_template_b(soup: BeautifulSoup) -> list[dict]:
    """Template B: State-led rezonings (e.g. Kurnell PP-2023-2828).

    Documents are embedded inside the description div as <details> accordions:
        div.field-field-project-description
          <details class="accordion">
            <summary><h4>Exhibition Documents</h4></summary>
            <ul><li><a href="...">Doc title</a></li>...</ul>
          </details>
          <details class="accordion">
            <summary><h4>Technical Studies</h4></summary>
            ...
          </details>

    Doc URLs point to S3 buckets or /sites/default/files/, NOT PublicDocuments API.
    """
    docs = []

    # Find the description div which contains the doc accordions
    desc_div = soup.find("div", class_=lambda c: c and "field-field-project-description" in c)
    if not desc_div:
        # Fallback: search the whole page
        desc_div = soup

    for details in desc_div.find_all("details"):
        # Category from the h4 inside summary
        h4 = details.find("h4")
        category = _clean_text(h4.get_text()) if h4 else None

        # Skip non-document accordions (contacts, etc.)
        if category and not re.search(
            r"(document|stud|report|exhibit|panel|assessment|plan|technical)",
            category, re.I,
        ):
            continue

        for link in details.find_all("a", href=True):
            href = link["href"]

            # Skip anchor links, mailto, javascript
            if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
                continue

            # Accept any document URL (S3, /sites/default/files/, PublicDocuments)
            if not re.search(
                r"(\.pdf|\.docx?|\.xlsx?|PublicDocuments|DocMgmt|s3\..*amazonaws|/sites/default/files/)",
                href, re.I,
            ):
                continue

            doc_url = href if href.startswith("http") else urljoin(BASE_URL, href)
            title = _clean_text(link.get_text()) or "Untitled"

            # Skip generic link text
            if title.lower() in ("view", "download", "open"):
                # Try parent li text
                parent = link.parent
                if parent and parent.name == "li":
                    parent_text = _clean_text(parent.get_text())
                    if parent_text and parent_text.lower() != title.lower():
                        title = parent_text

            docs.append({
                "title": title,
                "category": category,
                "url": doc_url,
            })

    return docs


def _detect_template(soup: BeautifulSoup) -> str:
    """Detect which template a detail page uses.

    Returns 'A', 'B', or 'unknown'.
    """
    # Template A: has a "Documents (N)" accordion outside the description div
    docs_section = soup.find(string=re.compile(r"Documents\s*\(\d+\)", re.I))
    if docs_section:
        return "A"

    # Template A fallback: PublicDocuments links exist
    has_pub_links = soup.find("a", href=re.compile(r"PublicDocuments|DocMgmt"))
    if has_pub_links:
        return "A"

    # Template B: doc accordions inside the description div with section headings
    # (e.g. "Exhibition Documents", "Technical Studies")
    desc_div = soup.find("div", class_=lambda c: c and "field-field-project-description" in c)
    if desc_div:
        for details in desc_div.find_all("details"):
            h4 = details.find("h4")
            if h4 and re.search(r"(document|stud|report|exhibit|panel)", h4.get_text(), re.I):
                return "B"

    # Also check for S3/drupal file links as Template B indicator
    has_file_links = soup.find("a", href=re.compile(r"s3\..*amazonaws|/sites/default/files/"))
    if has_file_links:
        return "B"

    return "unknown"


def parse_detail_page(html: str, detail_url: str, fallback_pp_number: str | None = None) -> dict:
    """Parse a PP detail page and return metadata + document list.

    Returns dict with keys matching the pps table schema plus a 'documents' list.
    """
    soup = BeautifulSoup(html, "lxml")
    slug = detail_url.rstrip("/").split("/")[-1]

    # Parse structured metadata from Activity Details sidebar
    fields = _parse_activity_details(soup)

    # PP number
    pp_number = fields.get("Number")
    if not pp_number:
        pp_match = re.search(r"PP-\d{4}-\d+", html)
        if pp_match:
            pp_number = pp_match.group(0)
        elif fallback_pp_number:
            pp_number = fallback_pp_number
        else:
            pp_number = slug

    # Title — h1
    h1 = soup.find("h1")
    title = _clean_text(h1.get_text()) if h1 else None

    # Council / LGA
    council = fields.get("Local government area") or fields.get("Council") or fields.get("LGA")

    # Description — from the Drupal field div
    description = None
    desc_div = soup.find("div", class_=lambda c: c and "field-field-project-description" in c)
    if desc_div:
        description = _clean_text(desc_div.get_text())

    # Addresses
    addresses = _extract_addresses(fields, soup)

    # Exhibition dates — portal combines as "Exhibition Start-End Date" -> "DD/MM/YYYY-DD/MM/YYYY"
    exhibition_start = None
    exhibition_end = None
    date_range = fields.get("Exhibition Start-End Date")
    if date_range and "-" in date_range:
        # Format: "DD/MM/YYYY-DD/MM/YYYY" — split on the dash between dates
        # Handle "DD/MM/YYYY-DD/MM/YYYY" carefully (dash also in date)
        parts = re.split(r"(\d{2}/\d{2}/\d{4})", date_range)
        dates = [p for p in parts if re.match(r"\d{2}/\d{2}/\d{4}$", p)]
        if len(dates) >= 2:
            exhibition_start = _parse_date(dates[0])
            exhibition_end = _parse_date(dates[1])
        elif len(dates) == 1:
            exhibition_start = _parse_date(dates[0])

    # Stage
    stage = fields.get("Stage")

    # Relevant Planning Authority
    rpa = fields.get("Relevant Planning Authority")

    # Documents
    template = _detect_template(soup)
    logger.info("PP %s uses template %s", pp_number, template)

    if template == "A":
        documents = _extract_documents_template_a(soup)
    elif template == "B":
        documents = _extract_documents_template_b(soup)
    else:
        logger.info("No documents section found for PP %s (%s)", pp_number, detail_url)
        documents = []

    # Deduplicate documents by URL
    seen_urls = set()
    deduped_docs = []
    for doc in documents:
        if doc["url"] not in seen_urls:
            seen_urls.add(doc["url"])
            deduped_docs.append(doc)

    return {
        "pp_number": pp_number,
        "slug": slug,
        "detail_url": detail_url,
        "title": title,
        "council": council,
        "addresses": addresses,
        "description": description,
        "exhibition_start": exhibition_start,
        "exhibition_end": exhibition_end,
        "stage": stage,
        "relevant_planning_authority": rpa,
        "documents": deduped_docs,
    }


def fetch_and_parse_detail(
    client: httpx.Client,
    detail_url: str,
    pp_number: str | None,
    data_dir: Path,
) -> dict:
    """Fetch a detail page, save HTML, parse and return metadata."""
    resp = fetch(client, detail_url)
    html = resp.text

    result = parse_detail_page(html, detail_url, fallback_pp_number=pp_number)

    # Save raw HTML
    raw_html_dir = data_dir / "raw_html"
    raw_html_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^\w\-.]", "_", result["pp_number"])
    html_path = raw_html_dir / f"{safe_name}.html"
    html_path.write_text(html, encoding="utf-8")
    result["raw_html_path"] = str(html_path)

    return result
