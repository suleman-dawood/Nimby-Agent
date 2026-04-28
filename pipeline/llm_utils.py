"""Shared LLM utilities used by brief, submission, and Q&A pipelines."""

from __future__ import annotations

import logging
import os
import re
import time

import google.generativeai as genai

logger = logging.getLogger(__name__)

MODEL = "models/gemini-2.5-flash"
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

# Canonical citation format: [doc: Title | p.N]
CITE_PATTERN = re.compile(r'\[doc:\s*(.+?)\s*\|\s*p\.?\s*(\d+)\]')


def load_prompt(name: str) -> str:
    """Load a prompt template from pipeline/prompts/<name>.md"""
    path = os.path.join(PROMPTS_DIR, f"{name}.md")
    with open(path) as f:
        return f.read().strip()


def call_llm(prompt: str, system: str = "", retries: int = 3) -> str:
    """Call Gemini Flash with retry + backoff."""
    model = genai.GenerativeModel(
        MODEL,
        system_instruction=system if system else None,
    )
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            if response.text:
                return response.text
            logger.warning("Empty LLM response (attempt %d)", attempt + 1)
        except Exception as e:
            logger.warning("LLM call failed (attempt %d): %s", attempt + 1, e)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return ""


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
    for match in CITE_PATTERN.finditer(text):
        title = match.group(1).strip()
        page = int(match.group(2))
        results.append({"document_title": title, "page": page, "span": match.span()})
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

    for length in [50, 30, 20, 15]:
        title_fragment = cited_doc[:length]
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

    logger.warning("Chunk not found: pp=%s doc='%s' page=%d", pp_number, cited_doc[:40], cited_page)
    return None
