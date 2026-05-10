"""PDF text extraction: page-level chunks into the chunks table.

Each page = one chunk. No sub-page splitting yet — page-level gives
natural citation grounding (doc + page number).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import pdfplumber
from sqlalchemy.orm import Session

from scraper import repository
from scraper.models import Document, create_db_engine, create_session

logger = logging.getLogger(__name__)

MIN_CHARS_PER_PAGE = 50  # Below this, mark as 'failed' (likely scan/image)
MAX_FILE_SIZE_MB = 100   # Skip files larger than this (huge map PDFs hang pdfplumber)


def extract_document(session: Session, doc: Document) -> dict:
    """Extract text from a single PDF, one chunk per page.

    Returns stats dict: {pages, chunks_ok, chunks_failed}
    """
    if not doc.file_path or not os.path.exists(doc.file_path):
        logger.warning("File missing for doc %d (%s): %s", doc.id, doc.pp_number, doc.file_path)
        return {"pages": 0, "chunks_ok": 0, "chunks_failed": 0}

    file_size_mb = os.path.getsize(doc.file_path) / 1048576
    if file_size_mb > MAX_FILE_SIZE_MB:
        logger.warning("Skipping doc %d — too large (%.0f MB): %s", doc.id, file_size_mb, doc.title)
        return {"pages": 0, "chunks_ok": 0, "chunks_failed": 0, "skipped_large": True}

    if repository.has_chunks(session, doc.id):
        logger.debug("Skipping doc %d — already has chunks", doc.id)
        return {"pages": 0, "chunks_ok": 0, "chunks_failed": 0, "skipped": True}

    now = datetime.now(timezone.utc)
    stats = {"pages": 0, "chunks_ok": 0, "chunks_failed": 0}

    try:
        with pdfplumber.open(doc.file_path) as pdf:
            stats["pages"] = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text() or ""
                except Exception as e:
                    logger.warning("Page %d extraction error in doc %d: %s", page_num, doc.id, e)
                    text = ""

                text = text.strip()
                text = text.replace("\x00", "")  # Strip null bytes (crashes PostgreSQL)

                if len(text) < MIN_CHARS_PER_PAGE:
                    method = "failed"
                    stats["chunks_failed"] += 1
                    if not text:
                        continue  # Skip completely empty pages
                else:
                    method = "pdfplumber"
                    stats["chunks_ok"] += 1

                repository.add_chunk(
                    session,
                    document_id=doc.id,
                    pp_number=doc.pp_number,
                    page_number=page_num,
                    chunk_index=0,  # One chunk per page for now
                    text=text,
                    extraction_method=method,
                    created_at=now,
                )

        session.commit()

    except Exception as e:
        logger.error("Failed to process doc %d (%s): %s", doc.id, doc.pp_number, e)
        session.rollback()

    return stats


def extract_by_tier(session: Session, tiers: list[int]) -> None:
    """Extract text from all docs matching the given tiers."""
    docs = (
        session.query(Document)
        .filter(Document.tier.in_(tiers), Document.download_status == "ok")
        .order_by(Document.pp_number, Document.id)
        .all()
    )

    total_pages = 0
    total_ok = 0
    total_failed = 0
    skipped = 0
    skipped_large = 0

    for i, doc in enumerate(docs):
        logger.info(
            "[%d/%d] Extracting doc %d: %s — %s",
            i + 1, len(docs), doc.id, doc.pp_number, (doc.title or "")[:50],
        )
        stats = extract_document(session, doc)
        if stats.get("skipped"):
            skipped += 1
            continue
        if stats.get("skipped_large"):
            skipped_large += 1
            continue
        total_pages += stats["pages"]
        total_ok += stats["chunks_ok"]
        total_failed += stats["chunks_failed"]

    print(f"\nExtraction complete for tiers {tiers}:")
    print(f"  Documents processed: {len(docs) - skipped - skipped_large}")
    print(f"  Skipped (already done): {skipped}")
    print(f"  Skipped (>100MB):       {skipped_large}")
    print(f"  Total pages:            {total_pages}")
    print(f"  Chunks OK:              {total_ok}")
    print(f"  Chunks failed:          {total_failed} (image/scan pages)")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Extract text from PDFs")
    parser.add_argument(
        "--tiers", type=int, nargs="+", default=[1],
        help="Which tiers to extract (default: 1)",
    )
    args = parser.parse_args()

    engine = create_db_engine()
    session = create_session(engine)

    try:
        extract_by_tier(session, args.tiers)
    finally:
        session.close()
