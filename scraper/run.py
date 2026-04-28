"""Orchestrator: one serial pass, end to end."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

from scraper import repository
from scraper.detail import fetch_and_parse_detail
from scraper.download import download_document
from scraper.fetch import create_client
from scraper.index import fetch_index
from scraper.models import create_db_engine, create_session

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


def init_dirs() -> None:
    (DATA_DIR / "raw_html").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "documents").mkdir(parents=True, exist_ok=True)


def print_summary(session) -> None:
    """Print final summary stats."""
    pp_count = repository.count_pps(session)
    doc_count = repository.count_documents(session)
    ok_count = repository.count_downloads_ok(session)
    total_bytes = repository.total_bytes_downloaded(session)
    failures = repository.failure_summary(session)
    pending = repository.count_pending(session)

    print("\n" + "=" * 60)
    print("SCRAPE SUMMARY")
    print("=" * 60)
    print(f"PPs processed:       {pp_count}")
    print(f"Documents found:     {doc_count}")
    print(f"Downloads OK:        {ok_count}")
    print(f"Total size on disk:  {total_bytes / 1_048_576:.1f} MB")

    if failures:
        print(f"\nFailures ({sum(c for _, c in failures)} total):")
        for status, count in failures:
            print(f"  {status}: {count}")

    if pending:
        print(f"\nPending (not attempted): {pending}")

    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape NSW Planning Proposals")
    parser.add_argument("--limit", type=int, default=None, help="Process only N PPs (for testing)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    init_dirs()
    engine = create_db_engine()
    session = create_session(engine)
    client = create_client()

    try:
        # 1. Fetch index
        print("Fetching index...")
        entries = fetch_index(client, DATA_DIR)
        print(f"Found {len(entries)} PPs on index.")

        if args.limit:
            entries = entries[: args.limit]
            print(f"Limited to {len(entries)} PPs.")

        # 2. Process each PP
        for entry in tqdm(entries, desc="Processing PPs"):
            pp_number = entry.get("pp_number") or entry["slug"]
            now = datetime.now(timezone.utc)

            try:
                # Upsert stub row
                repository.upsert_pp(session, pp_number, entry.get("slug", ""), entry["detail_url"], now)

                # Fetch + parse detail
                meta = fetch_and_parse_detail(
                    client, entry["detail_url"], pp_number, DATA_DIR
                )

                # PP number may have been refined by the detail parser
                if meta["pp_number"] != pp_number:
                    repository.delete_pp(session, pp_number)
                    pp_number = meta["pp_number"]
                    repository.upsert_pp(session, pp_number, meta["slug"], meta["detail_url"], now)

                repository.update_pp_metadata(
                    session,
                    pp_number,
                    title=meta["title"],
                    council=meta["council"],
                    addresses=meta["addresses"],
                    description=meta["description"],
                    exhibition_start=meta["exhibition_start"],
                    exhibition_end=meta["exhibition_end"],
                    stage=meta["stage"],
                    relevant_planning_authority=meta["relevant_planning_authority"],
                    raw_html_path=meta.get("raw_html_path", ""),
                    scraped_at=now,
                )

                # Upsert documents
                docs = meta.get("documents", [])
                for doc in docs:
                    repository.upsert_document(session, pp_number, doc["title"], doc.get("category"), doc["url"], now)

                # Download documents
                for i, doc in enumerate(docs):
                    print(f"  [{i + 1}/{len(docs)}] {doc['title'][:60]}")
                    download_document(client, pp_number, doc["url"], DATA_DIR, session)

            except Exception:
                logger.exception("Failed to process PP %s", pp_number)
                continue

        # 3. Summary
        print_summary(session)

    finally:
        client.close()
        session.close()


if __name__ == "__main__":
    main()
