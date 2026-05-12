"""Shared LLM utilities used by brief, submission, and Q&A pipelines."""

from __future__ import annotations

import logging
import os
import re
import time

import json
import tempfile

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

GCP_PROJECT = os.environ.get("GCP_PROJECT", "gen-lang-client-0499400729")
GCP_LOCATION = os.environ.get("GCP_LOCATION", "us-central1")
MODEL = "gemini-2.5-flash"

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Get or create the shared Genai client using ADC or service account JSON."""
    global _client
    if _client is not None:
        return _client

    # If GOOGLE_SA_KEY env var is set (Railway), decode and write to temp file for ADC
    # Accepts base64-encoded service account JSON
    sa_b64 = os.environ.get("GOOGLE_SA_KEY")
    if sa_b64:
        import base64
        sa_json = base64.b64decode(sa_b64).decode("utf-8")
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(sa_json)
        tmp.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
    elif os.environ.get("GOOGLE_SA_JSON"):
        # Fallback: raw JSON string
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(os.environ["GOOGLE_SA_JSON"])
        tmp.close()
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name

    _client = genai.Client(
        vertexai=True,
        project=GCP_PROJECT,
        location=GCP_LOCATION,
    )
    return _client
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

# Canonical citation format: [doc: Title | p.N]
CITE_PATTERN = re.compile(r'\[doc:\s*(.+?)\s*\|\s*p\.?\s*(\d+)\]')
# Fallback: [doc: Title] without page number (agent sometimes omits page)
CITE_PATTERN_NO_PAGE = re.compile(r'\[doc:\s*(.+?)\s*\]')


def load_prompt(name: str) -> str:
    """Load a prompt template from pipeline/prompts/<name>.md"""
    path = os.path.join(PROMPTS_DIR, f"{name}.md")
    with open(path) as f:
        return f.read().strip()


def call_llm(prompt: str, system: str = "", retries: int = 3) -> str:
    """Call Gemini Flash with retry + backoff via ADC."""
    client = get_client()
    config = types.GenerateContentConfig(
        system_instruction=system if system else None,
    )
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=config,
            )
            if response.text:
                return response.text
            logger.warning("Empty LLM response (attempt %d)", attempt + 1)
        except Exception as e:
            logger.warning("LLM call failed (attempt %d): %s", attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return ""


def stream_llm(prompt: str, system: str = ""):
    """Stream Gemini Flash response via ADC. Yields text chunks."""
    client = get_client()
    config = types.GenerateContentConfig(
        system_instruction=system if system else None,
    )
    try:
        for chunk in client.models.generate_content_stream(
            model=MODEL,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                yield chunk.text
    except Exception as e:
        logger.warning("LLM stream failed: %s", e)
        yield ""


def normalize_citations(text: str) -> str:
    """Normalize LLM output to enforce single-page citation format.

    Converts multi-page citations like [doc: X | p.6, p.11, p.20]
    into multiple single-page citations [doc: X | p.6][doc: X | p.11][doc: X | p.20].
    """
    def split_multi_page(match):
        full = match.group(0)
        inner = full[1:-1]
        if "|" in inner:
            title_part, page_part = inner.split("|", 1)
            title = title_part.replace("doc:", "").strip()
        else:
            return full

        pages = re.findall(r'(\d+)', page_part)
        if len(pages) <= 1:
            return full

        return "".join(f"[doc: {title} | p.{p}]" for p in pages)

    text = re.sub(
        r'\[doc:\s*[^]]+\|\s*p\.?\s*\d+(?:\s*,\s*p\.?\s*\d+)+\s*\]',
        split_multi_page,
        text,
    )

    text = re.sub(
        r'\[doc:\s*([^|\]]+?),\s*p\.?\s*(\d+)\]',
        r'[doc: \1 | p.\2]',
        text,
    )

    return text


def extract_citations(text: str) -> list[dict]:
    """Extract all citations from normalized text. Every occurrence kept with its span."""
    results = []
    seen = set()
    # Primary: [doc: Title | p.N]
    for match in CITE_PATTERN.finditer(text):
        title = match.group(1).strip()
        page = int(match.group(2))
        key = f"{title}|{page}"
        if key not in seen:
            seen.add(key)
            results.append({"document_title": title, "page": page, "span": match.span()})
    # Fallback: [doc: Title] without page
    for match in CITE_PATTERN_NO_PAGE.finditer(text):
        title = match.group(1).strip()
        # Skip if already matched by primary pattern (which includes | p.N)
        if "|" in title:
            continue
        key = f"{title}|0"
        if key not in seen:
            seen.add(key)
            results.append({"document_title": title, "page": 0, "span": match.span()})
    return results


def format_chunks(chunks: list[dict]) -> str:
    """Format retrieved chunks for LLM prompts."""
    parts = []
    for c in chunks:
        parts.append(
            f"--- [DOCUMENT: {c['document_title']}] [PAGE: {c['page_number']}] ---\n"
            f"{c['text'][:2000]}\n"
        )
    return "\n".join(parts)


def extract_claim_for_citation(text: str, citation_span: tuple[int, int]) -> str:
    """Extract the sentence containing a citation."""
    start_pos, end_pos = citation_span

    search_start = max(0, start_pos - 500)
    before = text[search_start:start_pos]

    sentence_start = search_start
    for m in re.finditer(r'[.!?]\s+', before):
        sentence_start = search_start + m.end()

    after = text[end_pos:]
    sentence_end_match = re.search(r'[.!?](?:\s|$)', after)
    if sentence_end_match:
        sentence_end = end_pos + sentence_end_match.end()
    else:
        sentence_end = min(end_pos + 200, len(text))

    claim = text[sentence_start:sentence_end].strip()
    claim = re.sub(r'\[doc:[^\]]+\]', '', claim).strip()
    claim = re.sub(r'\s+', ' ', claim).strip(' ,;')

    return claim


def find_chunk(session, pp_number: str, cited_doc: str, cited_page: int):
    """Find a chunk by PP, document title substring, and page number."""
    from scraper.models import Chunk, Document

    # Skip non-document citations (spatial data, portal metadata, etc.)
    if cited_doc.startswith("NSW ") or cited_doc.startswith("LEP "):
        return None

    for length in [50, 30, 20, 15]:
        title_fragment = cited_doc[:length]

        # Exact page match
        if cited_page > 0:
            chunk = (
                session.query(Chunk)
                .join(Document)
                .filter(
                    Chunk.pp_number == pp_number,
                    Chunk.page_number == cited_page,
                    Document.title.like(f"%{title_fragment}%"),
                )
                .first()
            )
            if chunk:
                return chunk

        # Page 0 or exact match failed — return first chunk from that document
        chunk = (
            session.query(Chunk)
            .join(Document)
            .filter(
                Chunk.pp_number == pp_number,
                Document.title.like(f"%{title_fragment}%"),
            )
            .order_by(Chunk.page_number)
            .first()
        )
        if chunk:
            return chunk

    logger.warning("Chunk not found: pp=%s doc='%s' page=%d", pp_number, cited_doc[:40], cited_page)
    return None
