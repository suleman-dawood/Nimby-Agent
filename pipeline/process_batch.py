"""Batch processor: scrape → classify → extract → embed → delete PDFs.

Processes PPs in small batches to stay within Railway's 5GB volume limit.
Each batch: download docs, extract text, embed chunks, delete PDFs.
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from scraper import repository
from scraper.detail import fetch_and_parse_detail
from scraper.download import download_document
from scraper.fetch import create_client
from scraper.index import fetch_all_stages
from scraper.models import PP, Document, Chunk, create_db_engine, create_session
from pipeline.extract import extract_document
from pipeline.embed import embed_all
from pipeline.classify import classify_all
from pipeline.spatial import enrich_pp

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


def _delete_pdfs():
    """Delete all downloaded PDFs to free disk space."""
    docs_dir = DATA_DIR / "documents"
    if not docs_dir.exists():
        return
    count = 0
    for f in docs_dir.iterdir():
        if f.is_file():
            f.unlink()
            count += 1
    if count:
        logger.info("Deleted %d PDF files", count)


def _extract_pp(session, pp_number: str) -> int:
    """Extract text from all downloaded tier 1/2 docs for a PP. Returns chunk count."""
    docs = (
        session.query(Document)
        .filter_by(pp_number=pp_number, download_status="ok")
        .filter(Document.tier.in_([1, 2]))
        .all()
    )

    chunks_created = 0
    for doc in docs:
        if repository.has_chunks(session, doc.id):
            continue
        if not doc.file_path or not os.path.exists(doc.file_path):
            logger.warning("File missing: doc %d (%s) path=%s", doc.id, doc.title[:40], doc.file_path)
            continue

        try:
            stats = extract_document(session, doc)
            chunks_created += stats.get("chunks_ok", 0)
        except Exception:
            logger.exception("Extract failed: doc %d (%s)", doc.id, doc.title[:40])

    return chunks_created


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

        # Filter to PPs that need chunks
        pps_with_chunks = set(r[0] for r in session.query(Chunk.pp_number).distinct().all())
        entries_needing_work = [
            e for e in all_entries
            if (e.get("pp_number") or e.get("slug")) not in pps_with_chunks
        ]
        print(f"PPs already with chunks: {len(pps_with_chunks)}")
        print(f"PPs needing processing: {len(entries_needing_work)}")

        total_chunks = 0
        total_embedded = 0

        # 2. Process in batches
        for batch_start in range(0, len(entries_needing_work), batch_size):
            batch = entries_needing_work[batch_start:batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            total_batches = (len(entries_needing_work) + batch_size - 1) // batch_size
            print(f"\n{'='*60}")
            print(f"BATCH {batch_num}/{total_batches}: PPs {batch_start+1}-{batch_start+len(batch)}")
            print(f"{'='*60}")

            batch_pp_numbers = []

            # 2a. Scrape + download each PP
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

                    docs = meta.get("documents", [])
                    for doc in docs:
                        repository.upsert_document(session, pp_number, doc["title"], doc.get("category"), doc["url"], now)

                    for doc in docs:
                        download_document(client, pp_number, doc["url"], DATA_DIR, session)

                    batch_pp_numbers.append(pp_number)
                    print(f"  Scraped {pp_number} ({len(docs)} docs)")

                except Exception:
                    logger.exception("Failed to scrape %s", pp_number)

            # 2b. Classify
            print("Classifying...")
            classify_all(session)

            # 2c. Extract text from PDFs
            batch_chunks = 0
            for pp_number in batch_pp_numbers:
                n = _extract_pp(session, pp_number)
                batch_chunks += n
                if n:
                    print(f"  Extracted {pp_number}: {n} chunks")

            total_chunks += batch_chunks
            print(f"Batch chunks extracted: {batch_chunks}")

            # 2d. Embed all new chunks
            pre_embed = session.query(Chunk).filter(Chunk.embedding.isnot(None)).count()
            if batch_chunks > 0:
                print("Embedding...")
                embed_all(session, tiers=[1, 2])
            post_embed = session.query(Chunk).filter(Chunk.embedding.isnot(None)).count()
            new_embedded = post_embed - pre_embed
            total_embedded += new_embedded
            print(f"Batch embedded: {new_embedded}")

            # 2e. Delete PDFs
            _delete_pdfs()
            print(f"PDFs cleaned up")

        # Final summary
        pp_count = session.query(PP).count()
        doc_count = session.query(Document).count()
        chunk_count = session.query(Chunk).count()
        embedded = session.query(Chunk).filter(Chunk.embedding.isnot(None)).count()

        print(f"\n{'='*60}")
        print(f"FINAL SUMMARY")
        print(f"{'='*60}")
        print(f"PPs in DB:          {pp_count}")
        print(f"Documents:          {doc_count}")
        print(f"Total chunks:       {chunk_count}")
        print(f"Embedded chunks:    {embedded}")
        print(f"New chunks:         {total_chunks}")
        print(f"New embedded:       {total_embedded}")
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
