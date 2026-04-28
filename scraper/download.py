"""Download documents: fetch bytes, hash, store, deduplicate."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from scraper.fetch import fetch
from scraper import repository

logger = logging.getLogger(__name__)


def download_document(
    client: httpx.Client,
    pp_number: str,
    doc_url: str,
    data_dir: Path,
    session: Session,
) -> None:
    """Download a single document, validate, store, and update manifest."""
    docs_dir = data_dir / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    # Check if already downloaded
    status = repository.get_document_status(session, pp_number, doc_url)
    if status == "ok":
        logger.debug("Skipping already-downloaded: %s", doc_url)
        return

    try:
        resp = fetch(client, doc_url)
        content = resp.content
        content_type = resp.headers.get("content-type", "")

        # Validate PDF
        if not content.startswith(b"%PDF-"):
            repository.update_document_download(
                session, pp_number, doc_url,
                download_status="failed_not_pdf",
                scraped_at=now,
            )
            logger.warning("Not a PDF (%s): %s", content_type, doc_url)
            return

        sha256 = hashlib.sha256(content).hexdigest()
        file_path = docs_dir / f"{sha256}.pdf"
        relative_path = f"data/documents/{sha256}.pdf"

        # Dedup: don't rewrite if file already exists from another PP
        if not file_path.exists():
            file_path.write_bytes(content)

        repository.update_document_download(
            session, pp_number, doc_url,
            sha256=sha256,
            file_path=relative_path,
            content_type=content_type,
            byte_size=len(content),
            download_status="ok",
            scraped_at=now,
        )
        logger.info("Downloaded %s -> %s (%d bytes)", doc_url, sha256[:12], len(content))

    except Exception as e:
        status = f"failed_{type(e).__name__}"
        if isinstance(e, httpx.HTTPStatusError):
            status = f"failed_{e.response.status_code}"

        repository.update_document_download(
            session, pp_number, doc_url,
            download_status=status,
            scraped_at=now,
        )
        logger.error("Download failed for %s: %s", doc_url, e)
