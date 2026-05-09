"""Fire webhook POST to registered URLs."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def fire_webhook(url: str, payload: dict) -> str:
    """POST payload to webhook URL. Returns 'sent' or 'failed'."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            status = "sent" if resp.status_code < 400 else "failed"
            logger.info("Webhook %s → %s (%d)", url[:50], status, resp.status_code)
            return status
    except Exception as e:
        logger.warning("Webhook failed for %s: %s", url[:50], e)
        return "failed"
