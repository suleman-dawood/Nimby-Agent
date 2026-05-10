"""Batch processor: scrape → classify → extract → embed → delete PDFs.

Processes PPs in small batches to stay within Railway's 5GB volume limit.
Each batch: download docs, extract text, embed chunks, delete PDFs.
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from scraper import repository
from scraper.detail import fetch_and_parse_detail
from scraper.download import download_document
from scraper.fetch import create_client
from scraper.index import fetch_all_stages
from scraper.models import PP, Document, Chunk, create_db_engine, create_session
from pipeline.classify import classify_document
from pipeline.spatial import enrich_pp

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


def _delete_pdfs():
    """Delete all downloaded PDFs to free disk space."""
    docs_dir = DATA_DIR / "documents"
    if docs_dir.exists():
        count = 0
        for f in docs_dir.iterdir():
            if f.is_file():
                f.unlink()
                count += 1
        logger.info("Deleted %d PDF files", count)


def _extract_and_embed_pp(session, pp_number: str):
    """Extract text and embed chunks for all docs of a PP."""
    from pipeline.extract import extract_document
    from pipeline.embed import embed_chunks_for_document

    docs = (
        session.query(Document)
        .filter_by(pp_number=pp_number, download_status="ok")
        .filter(Document.tier.in_([1, 2]))
        .all()
    )

    for doc in docs:
        # Skip if already has chunks
        if session.query(Chunk).filter_by(document_id=doc.id).first():
            continue

        if not doc.file_path or not os.path.exists(doc.file_path):
            continue

        # Skip huge files (>100MB)
        try:
            size = os.path.getsize(doc.file_path)
            if size > 100_000_000:
                logger.warning("Skipping %s — too large (%d MB)", doc.title[:40], size // 1_000_000)
                continue
        except OSError:
            continue

        try:
            extract_document(session, doc)
        except Exception:
            logger.exception("Extract failed for doc %d (%s)", doc.id, doc.title[:40])
            continue

    # Embed all un-embedded chunks for this PP
    chunks = (
        session.query(Chunk)
        .filter_by(pp_number=pp_number)
        .filter(Chunk.embedding.is_(None))
        .all()
    )
    if chunks:
        try:
            from pipeline.embed import embed_chunks
            embed_chunks(session, chunks)
        except Exception:
            logger.exception("Embedding failed for %s", pp_number)


def process_all_batched(stages: list[str] | None = None, batch_size: int = 10):
    """Process all PPs in batches to stay within disk limits."""
    engine = create_db_engine()
    session = create_session(engine)
    client = create_client()

    (DATA_DIR / "raw_html").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "documents").mkdir(parents=True, exist_ok=True)

    try:
        # 1. Fetch all indexes
        print(f"Fetching indexes (stages: {stages or 'all'})...")
        all_entries = fetch_all_stages(client, DATA_DIR, stages=stages)
        print(f"Found {len(all_entries)} PPs total")

        # 2. Process in batches
        for batch_start in range(0, len(all_entries), batch_size):
            batch = all_entries[batch_start:batch_start + batch_size]
            batch_end = min(batch_start + batch_size, len(all_entries))
            print(f"\n{'='*60}")
            print(f"BATCH {batch_start // batch_size + 1}: PPs {batch_start + 1}-{batch_end} of {len(all_entries)}")
            print(f"{'='*60}")

            batch_pp_numbers = []

            # 2a. Scrape + download
            for entry in batch:
                pp_number = entry.get("pp_number") or entry["slug"]
                now = datetime.now(timezone.utc)

                try:
                    repository.upsert_pp(session, pp_number, entry.get("slug", ""), entry["detail_url"], now)

                    meta = fetch_and_parse_detail(client, entry["detail_url"], pp_number, DATA_DIR)

                    if meta["pp_number"] != pp_number:
                        repository.delete_pp(session, pp_number)
                        pp_number = meta["pp_number"]
                        repository.upsert_pp(session, pp_number, meta["slug"], meta["detail_url"], now)

                    stage = entry.get("stage") or meta["stage"]
                    repository.update_pp_metadata(
                        session, pp_number,
                        title=meta["title"], council=meta["council"],
                        addresses=meta["addresses"], description=meta["description"],
                        exhibition_start=meta["exhibition_start"],
                        exhibition_end=meta["exhibition_end"],
                        stage=stage,
                        relevant_planning_authority=meta["relevant_planning_authority"],
                        raw_html_path=meta.get("raw_html_path", ""),
                        scraped_at=now,
                    )

                    # Classify + download docs
                    docs = meta.get("documents", [])
                    for doc in docs:
                        repository.upsert_document(session, pp_number, doc["title"], doc.get("category"), doc["url"], now)

                    for doc in docs:
                        download_document(client, pp_number, doc["url"], DATA_DIR, session)

                    batch_pp_numbers.append(pp_number)

                except Exception:
                    logger.exception("Failed to scrape %s", pp_number)
                    continue

            # 2b. Classify all docs in batch
            print(f"Classifying documents...")
            from pipeline.classify import classify_all
            classify_all(session)

            # 2c. Extract + embed for each PP in batch
            for pp_number in batch_pp_numbers:
                print(f"Extracting + embedding {pp_number}...")
                try:
                    _extract_and_embed_pp(session, pp_number)
                except Exception:
                    logger.exception("Extract/embed failed for %s", pp_number)

            # 2d. Spatial enrichment
            for pp_number in batch_pp_numbers:
                pp = session.get(PP, pp_number)
                if pp and pp.latitude and pp.longitude:
                    try:
                        enrich_pp(session, pp_number, pp.latitude, pp.longitude)
                    except Exception:
                        logger.exception("Spatial enrich failed for %s", pp_number)

            # 2e. Delete PDFs to free space
            print(f"Cleaning up PDFs...")
            _delete_pdfs()

            # Summary for this batch
            print(f"Batch complete: {len(batch_pp_numbers)} PPs processed")

        # Final summary
        pp_count = repository.count_pps(session)
        doc_count = repository.count_documents(session)
        chunk_count = session.query(Chunk).count()
        embedded = session.query(Chunk).filter(Chunk.embedding.isnot(None)).count()

        print(f"\n{'='*60}")
        print(f"FINAL SUMMARY")
        print(f"{'='*60}")
        print(f"PPs in DB:          {pp_count}")
        print(f"Documents:          {doc_count}")
        print(f"Chunks:             {chunk_count}")
        print(f"Embedded chunks:    {embedded}")
        print(f"{'='*60}")

    finally:
        client.close()
        session.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Batch process PPs: scrape → extract → embed → cleanup")
    parser.add_argument("--stages", type=str, default=None, help="Comma-separated stages or 'all'")
    parser.add_argument("--batch-size", type=int, default=10, help="PPs per batch (default 10)")
    args = parser.parse_args()

    stages = None
    if args.stages:
        if args.stages.lower() == "all":
            stages = None
        else:
            stages = [s.strip() for s in args.stages.split(",")]
    else:
        stages = ["Under Exhibition"]

    process_all_batched(stages=stages, batch_size=args.batch_size)
