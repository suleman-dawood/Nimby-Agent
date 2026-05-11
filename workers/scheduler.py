"""Background worker loop for auto-scraping and notifications.

Handles:
- New proposals across all stages
- Document changes (added/removed) on existing proposals
- Stage transitions
- Geocoding, spatial enrichment
- Brief generation for PPs with chunks but no brief
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCRAPE_INTERVAL_HOURS = 6
DATA_DIR = Path("/tmp/nimby_scrape")


async def worker_loop():
    """Main background worker. Runs every 6 hours."""
    await asyncio.sleep(30)

    while True:
        try:
            logger.info("Worker: starting cycle")
            result = await asyncio.to_thread(_run_cycle)
            logger.info("Worker: cycle complete — %s", result)
        except Exception:
            logger.exception("Worker: cycle failed")

        await asyncio.sleep(SCRAPE_INTERVAL_HOURS * 3600)


def _run_cycle() -> dict:
    """Full sync cycle. Runs in thread."""
    from scraper.index import fetch_all_stages
    from scraper.detail import fetch_and_parse_detail
    from scraper.download import download_document
    from scraper.fetch import create_client
    from scraper import repository
    from scraper.models import PP, Document, Chunk, create_db_engine, create_session
    from pipeline.spatial import enrich_pp
    from pipeline.geocode import geocode_pp
    from pipeline.extract import extract_document
    from pipeline.embed import embed_all
    from pipeline.classify import classify_all

    engine = create_db_engine()
    session = create_session(engine)
    client = create_client()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "raw_html").mkdir(exist_ok=True)
    (DATA_DIR / "documents").mkdir(exist_ok=True)

    stats = {
        "new_pps": [],
        "stage_changes": [],
        "doc_changes": [],
        "geocoded": 0,
        "spatial_enriched": 0,
        "briefs_generated": 0,
    }

    try:
        # 1. Fetch all stage indexes
        all_entries = fetch_all_stages(client, DATA_DIR, stages=None)
        existing_pps = {pp.pp_number: pp for pp in session.query(PP).all()}
        logger.info("Worker: %d entries from portal, %d in DB", len(all_entries), len(existing_pps))

        for entry in all_entries:
            pp_number = entry.get("pp_number")
            if not pp_number:
                continue
            now = datetime.now(timezone.utc)

            try:
                if pp_number not in existing_pps:
                    # --- NEW PP ---
                    _process_new_pp(session, client, entry, now)
                    stats["new_pps"].append(pp_number)
                else:
                    # --- EXISTING PP: check stage + docs ---
                    pp = existing_pps[pp_number]

                    # Stage transition
                    new_stage = entry.get("stage")
                    if new_stage and pp.stage != new_stage:
                        old_stage = pp.stage
                        logger.info("Stage: %s %s → %s", pp_number, old_stage, new_stage)
                        pp.stage = new_stage
                        session.commit()
                        stats["stage_changes"].append(pp_number)
                        _notify_subscribers(session, pp_number, "stage_change",
                            f"{pp_number} moved to {new_stage}",
                            f"Stage changed from {old_stage} to {new_stage}.",
                            "notify_stage")

                    # Doc changes — re-fetch detail and diff
                    doc_changes = _check_doc_changes(session, client, pp, entry, now)
                    if doc_changes:
                        stats["doc_changes"].append(pp_number)
                        _notify_subscribers(session, pp_number, "new_docs",
                            f"New documents for {pp_number}",
                            "New documents have been uploaded to this proposal.",
                            "notify_docs")

            except Exception:
                logger.exception("Worker: failed %s", pp_number)

        # 2. Geocode PPs missing coordinates
        ungeo = session.query(PP).filter(PP.latitude.is_(None)).all()
        for pp in ungeo[:20]:  # batch 20 at a time to avoid rate limits
            try:
                result = geocode_pp(session, pp)
                if result:
                    lat, lng, src = result
                    repository.update_pp_geocode(session, pp.pp_number, lat, lng, src)
                    stats["geocoded"] += 1
            except Exception:
                pass

        # 3. Spatial enrichment for PPs with coords but no context
        from scraper.models import SiteContext
        enriched_pps = {sc.pp_number for sc in session.query(SiteContext.pp_number).all()}
        need_enrich = (
            session.query(PP)
            .filter(PP.latitude.isnot(None), ~PP.pp_number.in_(enriched_pps))
            .all()
        )
        for pp in need_enrich:
            try:
                enrich_pp(session, pp.pp_number, pp.latitude, pp.longitude)
                stats["spatial_enriched"] += 1
            except Exception:
                pass

        # 4. Generate briefs for PPs that have chunks but no brief in DB
        stats["briefs_generated"] = _generate_missing_briefs(session)

        # 5. Check exhibition expiry — warn subscribers 7 days before
        _check_expiry_warnings(session)

    finally:
        client.close()
        session.close()

    return stats


def _process_new_pp(session, client, entry, now):
    """Full pipeline for a new PP."""
    from scraper.detail import fetch_and_parse_detail
    from scraper.download import download_document
    from scraper import repository
    from scraper.models import PP
    from pipeline.geocode import geocode_pp
    from pipeline.spatial import enrich_pp

    pp_number = entry.get("pp_number") or entry["slug"]

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

    # Download docs
    docs = meta.get("documents", [])
    for doc in docs:
        repository.upsert_document(session, pp_number, doc["title"], doc.get("category"), doc["url"], now)
    for doc in docs:
        download_document(client, pp_number, doc["url"], DATA_DIR, session)

    # Geocode
    pp = session.get(PP, pp_number)
    if pp and not pp.latitude:
        try:
            result = geocode_pp(session, pp)
            if result:
                lat, lng, src = result
                repository.update_pp_geocode(session, pp_number, lat, lng, src)
        except Exception:
            pass

    # Spatial
    pp = session.get(PP, pp_number)
    if pp and pp.latitude and pp.longitude:
        try:
            enrich_pp(session, pp_number, pp.latitude, pp.longitude)
        except Exception:
            pass

    logger.info("Worker: new PP %s processed", pp_number)


def _check_doc_changes(session, client, pp, entry, now) -> bool:
    """Re-fetch detail page, diff document list against DB. Returns True if changes found."""
    from scraper.detail import fetch_and_parse_detail
    from scraper.download import download_document
    from scraper.models import Document
    from scraper import repository

    try:
        meta = fetch_and_parse_detail(client, entry["detail_url"], pp.pp_number, DATA_DIR)
    except Exception:
        return False

    portal_docs = {doc["url"] for doc in meta.get("documents", [])}
    db_docs = {doc.url for doc in session.query(Document).filter_by(pp_number=pp.pp_number).all()}

    new_urls = portal_docs - db_docs
    removed_urls = db_docs - portal_docs

    if not new_urls and not removed_urls:
        return False

    if new_urls:
        logger.info("Worker: %s has %d new docs", pp.pp_number, len(new_urls))
        for doc in meta.get("documents", []):
            if doc["url"] in new_urls:
                repository.upsert_document(session, pp.pp_number, doc["title"], doc.get("category"), doc["url"], now)
                download_document(client, pp.pp_number, doc["url"], DATA_DIR, session)

    if removed_urls:
        logger.info("Worker: %s has %d removed docs", pp.pp_number, len(removed_urls))
        # Mark removed docs — don't delete, just log for now
        for url in removed_urls:
            doc = session.query(Document).filter_by(pp_number=pp.pp_number, url=url).first()
            if doc:
                doc.download_status = "removed"
                session.commit()

    return True


def _generate_missing_briefs(session) -> int:
    """Generate/update briefs in DB for PPs with chunks.

    Generates if: no brief exists.
    Regenerates if: chunk count changed (new docs added/removed).
    """
    from scraper.models import Brief, Chunk
    from sqlalchemy import func
    from pipeline.brief import generate_brief

    # PPs with chunks and their chunk counts
    chunk_counts = dict(
        session.query(Chunk.pp_number, func.count(Chunk.id))
        .group_by(Chunk.pp_number)
        .all()
    )

    # Existing briefs
    existing_briefs = {
        b.pp_number: b
        for b in session.query(Brief).all()
    }

    generated = 0
    for pp_number, chunk_count in chunk_counts.items():
        existing = existing_briefs.get(pp_number)

        # Skip if brief exists and chunk count hasn't changed
        if existing and existing.chunk_count == chunk_count:
            continue

        action = "regenerating" if existing else "generating"

        try:
            logger.info("Worker: %s brief for %s (%d chunks)", action, pp_number, chunk_count)
            brief_md = generate_brief(pp_number)
            if not brief_md:
                continue

            now = datetime.now(timezone.utc)
            doc_count = session.query(func.count()).select_from(
                session.query(Chunk.document_id).filter_by(pp_number=pp_number).distinct().subquery()
            ).scalar()

            if existing:
                existing.markdown = brief_md
                existing.chunk_count = chunk_count
                existing.doc_count = doc_count
                existing.generated_at = now
            else:
                brief = Brief(
                    pp_number=pp_number,
                    markdown=brief_md,
                    doc_count=doc_count,
                    chunk_count=chunk_count,
                    generated_at=now,
                )
                session.add(brief)

            session.commit()
            generated += 1
            logger.info("Worker: brief %s for %s", action, pp_number)

        except Exception:
            session.rollback()
            logger.exception("Worker: brief failed for %s", pp_number)

        # Limit per cycle to conserve Gemini credits
        if generated >= 5:
            logger.info("Worker: brief limit reached (5 per cycle)")
            break

    return generated


def _notify_subscribers(session, pp_number: str, event_type: str, title: str, message: str, pref_field: str):
    """Create in-app notifications + send emails for PP subscribers."""
    from scraper.models import InAppNotification, Subscription
    from workers.email import send_email_notification_sync

    subs = (
        session.query(Subscription)
        .filter_by(pp_number=pp_number, active=True)
        .all()
    )

    for sub in subs:
        # Check notification preference
        if not getattr(sub, pref_field, True):
            continue

        # In-app notification
        notif = InAppNotification(
            user_id=sub.user_id,
            pp_number=pp_number,
            event_type=event_type,
            title=title,
            message=message,
            read=False,
            created_at=datetime.now(timezone.utc),
        )
        session.add(notif)

        # Email
        try:
            from scraper.models import User
            user = session.get(User, sub.user_id)
            if user and user.email:
                _send_subscription_email(user.email, pp_number, title, message)
        except Exception:
            logger.warning("Email failed for user %d on %s", sub.user_id, pp_number)

    session.commit()
    if subs:
        logger.info("Notified %d subscribers for %s (%s)", len(subs), pp_number, event_type)


def _send_subscription_email(to_email: str, pp_number: str, title: str, message: str):
    """Send subscription notification email synchronously."""
    import httpx
    import os

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        return

    httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": os.environ.get("FROM_EMAIL", "onboarding@resend.dev"),
            "to": to_email,
            "subject": title,
            "html": f"""
            <div style="font-family: 'Public Sans', Arial, sans-serif; max-width: 600px;">
                <h2 style="color: #002664;">{title}</h2>
                <p>{message}</p>
                <p><a href="https://api-service-production-6a0d.up.railway.app/brief/{pp_number}"
                   style="background: #002664; color: white; padding: 10px 20px; text-decoration: none;">
                   View Proposal</a></p>
            </div>""",
        },
        timeout=10.0,
    )


def _check_expiry_warnings(session):
    """Warn subscribers when exhibition ends within 7 days."""
    from scraper.models import PP, Subscription, InAppNotification
    from datetime import date, timedelta

    soon = date.today() + timedelta(days=7)
    today = date.today()

    expiring = (
        session.query(PP)
        .filter(PP.exhibition_end.isnot(None))
        .filter(PP.exhibition_end > today)
        .filter(PP.exhibition_end <= soon)
        .all()
    )

    for pp in expiring:
        days_left = (pp.exhibition_end - today).days

        # Find subscribers who want expiry notifications
        subs = (
            session.query(Subscription)
            .filter_by(pp_number=pp.pp_number, active=True, notify_expiry=True)
            .all()
        )

        for sub in subs:
            # Don't double-notify — check if already notified about this expiry
            existing = (
                session.query(InAppNotification)
                .filter_by(user_id=sub.user_id, pp_number=pp.pp_number, event_type="expiry_warning")
                .first()
            )
            if existing:
                continue

            notif = InAppNotification(
                user_id=sub.user_id,
                pp_number=pp.pp_number,
                event_type="expiry_warning",
                title=f"{pp.pp_number} exhibition closes in {days_left} days",
                message=f"Exhibition for {pp.title or pp.pp_number} closes on {pp.exhibition_end}. Submit your response before it closes.",
                read=False,
                created_at=datetime.now(timezone.utc),
            )
            session.add(notif)

            # Email warning too
            try:
                from scraper.models import User
                user = session.get(User, sub.user_id)
                if user:
                    _send_subscription_email(
                        user.email, pp.pp_number,
                        f"{pp.pp_number} closes in {days_left} days",
                        f"Exhibition for {pp.title or pp.pp_number} closes on {pp.exhibition_end}.",
                    )
            except Exception:
                pass

    session.commit()
    if expiring:
        logger.info("Checked expiry for %d PPs", len(expiring))


async def trigger_scrape() -> dict:
    """Manual trigger for demos. Returns summary."""
    result = await asyncio.to_thread(_run_cycle)

    # Notify watchers for new PPs
    if result.get("new_pps"):
        from workers.notify import notify_watchers_for_new_pps
        await notify_watchers_for_new_pps(result["new_pps"])

    return result
