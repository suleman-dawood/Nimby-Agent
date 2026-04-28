"""HTTP layer: single client, retries, backoff, polite delays."""

from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "nsw-ppr-scraper/0.1 (+github.com/<placeholder>)"
TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}
BACKOFF_BASE = 2  # seconds: 2, 4, 8
POLITE_DELAY = 1.5  # seconds between requests to same host

_last_request_time: float = 0.0


def create_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=True,
    )


def fetch(client: httpx.Client, url: str) -> httpx.Response:
    """Fetch a URL with retry logic, backoff, and polite delays."""
    global _last_request_time

    # Polite delay
    elapsed_since_last = time.monotonic() - _last_request_time
    if elapsed_since_last < POLITE_DELAY:
        time.sleep(POLITE_DELAY - elapsed_since_last)

    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            wait = BACKOFF_BASE ** attempt
            logger.info("Retry %d/%d for %s (waiting %ds)", attempt, MAX_RETRIES, url, wait)
            time.sleep(wait)

        start = time.monotonic()
        try:
            resp = client.get(url)
            elapsed = time.monotonic() - start
            _last_request_time = time.monotonic()
            logger.info("%s %d %.1fs %s", "GET", resp.status_code, elapsed, url)

            if resp.status_code in RETRY_STATUSES:
                last_exc = httpx.HTTPStatusError(
                    f"Server error {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
                continue

            resp.raise_for_status()
            return resp

        except httpx.HTTPStatusError as e:
            if e.response.status_code not in RETRY_STATUSES:
                raise
            last_exc = e
            continue

        except httpx.TransportError as e:
            elapsed = time.monotonic() - start
            logger.warning("Transport error %.1fs %s: %s", elapsed, url, e)
            last_exc = e
            continue

    raise last_exc  # type: ignore[misc]
