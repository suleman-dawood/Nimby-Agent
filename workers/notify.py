"""Match new proposals to watchers and dispatch notifications."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

from scraper.models import Notification, PP, SiteContext, Watcher, create_db_engine, create_session
from workers.email import send_email_notification
from workers.webhook import fire_webhook

logger = logging.getLogger(__name__)


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance in km between two points."""
    R = 6371.0
    lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlng / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _build_payload(pp: PP, site_ctx: SiteContext | None, watcher: Watcher, distance_km: float) -> dict:
    """Build webhook notification payload."""
    payload = {
        "event": "new_proposal_nearby",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "proposal": {
            "pp_number": pp.pp_number,
            "title": pp.title,
            "council": pp.council,
            "stage": pp.stage,
            "distance_km": round(distance_km, 2),
            "exhibition_end": str(pp.exhibition_end) if pp.exhibition_end else None,
        },
        "watcher": {
            "address": watcher.address,
            "radius_km": watcher.radius_km,
        },
    }
    if site_ctx:
        payload["proposal"]["site_context"] = {
            "zoning": site_ctx.zoning,
            "max_height_m": site_ctx.max_height_m,
            "bushfire_prone": site_ctx.bushfire_prone,
            "flood_planning": site_ctx.flood_planning,
            "heritage_item": site_ctx.heritage_item,
        }
    return payload


def _record_notification(session, watcher_id: int, pp_number: str, channel: str, status: str, payload: dict):
    """Record a notification in the DB."""
    notif = Notification(
        watcher_id=watcher_id,
        pp_number=pp_number,
        channel=channel,
        status=status,
        payload=json.dumps(payload),
        sent_at=datetime.now(timezone.utc),
    )
    session.add(notif)
    session.commit()


async def notify_watchers_for_new_pps(new_pp_numbers: list[str]):
    """Find watchers within radius of new proposals and dispatch notifications."""
    engine = create_db_engine()
    session = create_session(engine)

    try:
        watchers = session.query(Watcher).filter_by(active=True).all()
        if not watchers:
            logger.info("No active watchers — skipping notifications")
            return

        for pp_number in new_pp_numbers:
            pp = session.get(PP, pp_number)
            if not pp or not pp.latitude or not pp.longitude:
                continue

            site_ctx = session.query(SiteContext).filter_by(pp_number=pp_number).first()

            for watcher in watchers:
                dist = _haversine(watcher.lat, watcher.lng, pp.latitude, pp.longitude)
                if dist > watcher.radius_km:
                    continue

                logger.info("PP %s is %.1fkm from watcher %d (%s)", pp_number, dist, watcher.id, watcher.address[:30])
                payload = _build_payload(pp, site_ctx, watcher, dist)

                # Fire webhook if registered
                if watcher.webhook_url:
                    status = await fire_webhook(watcher.webhook_url, payload)
                    _record_notification(session, watcher.id, pp_number, "webhook", status, payload)

                # Send email
                status = await send_email_notification(watcher.email, pp, dist)
                _record_notification(session, watcher.id, pp_number, "email", status, payload)

    finally:
        session.close()
