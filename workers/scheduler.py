"""Background worker loop for auto-scraping and notifications.

Runs inside FastAPI lifespan on Railway — no separate service needed.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCRAPE_INTERVAL_HOURS = 6


async def worker_loop():
    """Main background worker. Scrapes all stages, enriches, notifies."""
    # Wait 30s after startup before first run
    await asyncio.sleep(30)

    while True:
        try:
            logger.info("Worker: starting scrape cycle")
            new_pp_numbers = await _scrape_and_enrich()
            logger.info("Worker: found %d new proposals", len(new_pp_numbers))

            if new_pp_numbers:
                from workers.notify import notify_watchers_for_new_pps
                await notify_watchers_for_new_pps(new_pp_numbers)

            logger.info("Worker: cycle complete, sleeping %d hours", SCRAPE_INTERVAL_HOURS)
        except Exception:
            logger.exception("Worker: cycle failed")

        await asyncio.sleep(SCRAPE_INTERVAL_HOURS * 3600)


async def _scrape_and_enrich() -> list[str]:
    """Scrape all stages, detect new PPs, enrich with spatial data.

    Returns list of new pp_numbers.
    """
    from scraper.index import fetch_all_stages
    from scraper.detail import fetch_and_parse_detail
    from scraper.download import download_document
    from scraper.fetch import create_client
    from scraper import repository
    from scraper.models import PP, create_db_engine, create_session
    from pipeline.spatial import enrich_pp
    from pipeline.geocode import geocode_pp

    engine = create_db_engine()
    session = create_session(engine)
    client = create_client()
    data_dir = Path("/tmp/nimby_scrape")
    data_dir.mkdir(parents=True, exist_ok=True)

    new_pp_numbers = []

    try:
        # 1. Fetch all stage indexes
        all_entries = fetch_all_stages(client, data_dir, stages=["Under Exhibition"])

        # 2. Detect new entries (not in DB)
        existing = {pp.pp_number for pp in session.query(PP.pp_number).all()}

        new_entries = []
        for entry in all_entries:
            pp_num = entry.get("pp_number")
            if pp_num and pp_num not in existing:
                new_entries.append(entry)

        logger.info("Worker: %d new PPs detected (of %d total)", len(new_entries), len(all_entries))

        # 3. Process each new PP
        for entry in new_entries:
            pp_number = entry.get("pp_number") or entry["slug"]
            now = datetime.now(timezone.utc)

            try:
                repository.upsert_pp(session, pp_number, entry.get("slug", ""), entry["detail_url"], now)

                meta = fetch_and_parse_detail(client, entry["detail_url"], pp_number, data_dir)

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

                # Geocode
                pp = session.get(PP, pp_number)
                if pp and not pp.latitude:
                    try:
                        geocode_pp(session, pp)
                    except Exception:
                        logger.warning("Geocoding failed for %s", pp_number)

                # Spatial enrichment
                pp = session.get(PP, pp_number)
                if pp and pp.latitude and pp.longitude:
                    enrich_pp(session, pp_number, pp.latitude, pp.longitude)

                new_pp_numbers.append(pp_number)
                logger.info("Worker: processed %s", pp_number)

            except Exception:
                logger.exception("Worker: failed to process %s", pp_number)
                continue

        # 4. Detect stage transitions for existing PPs
        for entry in all_entries:
            pp_num = entry.get("pp_number")
            if pp_num and pp_num in existing:
                pp = session.get(PP, pp_num)
                new_stage = entry.get("stage")
                if pp and new_stage and pp.stage != new_stage:
                    logger.info("Stage transition: %s %s → %s", pp_num, pp.stage, new_stage)
                    pp.stage = new_stage
                    session.commit()

    finally:
        client.close()
        session.close()

    return new_pp_numbers


async def trigger_scrape() -> dict:
    """Manual trigger for demos. Returns summary."""
    new_pps = await _scrape_and_enrich()
    if new_pps:
        from workers.notify import notify_watchers_for_new_pps
        await notify_watchers_for_new_pps(new_pps)
    return {"new_proposals": len(new_pps), "pp_numbers": new_pps}
