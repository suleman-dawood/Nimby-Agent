"""Send email notifications via Resend API."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "onboarding@resend.dev")


async def send_email_notification(to_email: str, pp, distance_km: float) -> str:
    """Send email notification about a nearby proposal. Returns 'sent' or 'failed'."""
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping email to %s", to_email)
        return "failed"

    subject = f"New planning proposal {pp.pp_number} near you"
    html = f"""
    <div style="font-family: 'Public Sans', Arial, sans-serif; max-width: 600px;">
        <h2 style="color: #002664;">New Planning Proposal Nearby</h2>
        <p>A new planning proposal was found <strong>{distance_km:.1f}km</strong> from your watched address.</p>
        <div style="background: #f4f4f4; padding: 16px; border-radius: 4px; margin: 16px 0;">
            <p style="margin: 0 0 8px;"><strong>{pp.pp_number}</strong></p>
            <p style="margin: 0 0 8px;">{pp.title or 'Untitled proposal'}</p>
            <p style="margin: 0; color: #666;">{pp.council or 'Unknown council'}</p>
        </div>
        <p>
            <a href="https://api-service-production-6a0d.up.railway.app/brief/{pp.pp_number}"
               style="background: #002664; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px;">
                View Details
            </a>
        </p>
        <p style="color: #999; font-size: 12px; margin-top: 24px;">
            You're receiving this because you set up a proposal watcher on Nimby Agent.
        </p>
    </div>
    """

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from": FROM_EMAIL,
                    "to": to_email,
                    "subject": subject,
                    "html": html,
                },
            )
            status = "sent" if resp.status_code == 200 else "failed"
            logger.info("Email to %s: %s (%d)", to_email, status, resp.status_code)
            return status
    except Exception as e:
        logger.warning("Email failed for %s: %s", to_email, e)
        return "failed"
