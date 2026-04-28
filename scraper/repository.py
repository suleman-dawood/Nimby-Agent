"""Repository pattern for all database access. No raw SQL outside this file."""

from __future__ import annotations

import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from scraper.models import PP, Document


# --- PP operations ---

def upsert_pp(session: Session, pp_number: str, slug: str, detail_url: str, now: datetime) -> PP:
    pp = session.get(PP, pp_number)
    if pp:
        pp.slug = slug
        pp.detail_url = detail_url
        pp.scraped_at = now
    else:
        pp = PP(
            pp_number=pp_number,
            slug=slug,
            detail_url=detail_url,
            raw_html_path="",
            scraped_at=now,
        )
        session.add(pp)
    session.commit()
    return pp


def update_pp_metadata(
    session: Session,
    pp_number: str,
    *,
    title: str | None,
    council: str | None,
    addresses: list[str],
    description: str | None,
    exhibition_start: date | None,
    exhibition_end: date | None,
    stage: str | None,
    relevant_planning_authority: str | None,
    raw_html_path: str,
    scraped_at: datetime,
) -> None:
    pp = session.get(PP, pp_number)
    if not pp:
        return
    pp.title = title
    pp.council = council
    pp.addresses = json.dumps(addresses)
    pp.description = description
    pp.exhibition_start = exhibition_start
    pp.exhibition_end = exhibition_end
    pp.stage = stage
    pp.relevant_planning_authority = relevant_planning_authority
    pp.raw_html_path = raw_html_path
    pp.scraped_at = scraped_at
    session.commit()


def delete_pp(session: Session, pp_number: str) -> None:
    pp = session.get(PP, pp_number)
    if pp:
        session.delete(pp)
        session.commit()


# --- Document operations ---

def upsert_document(
    session: Session, pp_number: str, title: str, category: str | None, url: str, now: datetime
) -> Document:
    doc = (
        session.query(Document)
        .filter_by(pp_number=pp_number, url=url)
        .first()
    )
    if doc:
        doc.title = title
        doc.category = category
        doc.scraped_at = now
    else:
        doc = Document(
            pp_number=pp_number,
            title=title,
            category=category,
            url=url,
            download_status="pending",
            scraped_at=now,
        )
        session.add(doc)
    session.commit()
    return doc


def get_document_status(session: Session, pp_number: str, url: str) -> str | None:
    doc = (
        session.query(Document)
        .filter_by(pp_number=pp_number, url=url)
        .first()
    )
    return doc.download_status if doc else None


def update_document_download(
    session: Session,
    pp_number: str,
    url: str,
    *,
    sha256: str | None = None,
    file_path: str | None = None,
    content_type: str | None = None,
    byte_size: int | None = None,
    download_status: str,
    scraped_at: datetime,
) -> None:
    doc = (
        session.query(Document)
        .filter_by(pp_number=pp_number, url=url)
        .first()
    )
    if not doc:
        return
    if sha256 is not None:
        doc.sha256 = sha256
    if file_path is not None:
        doc.file_path = file_path
    if content_type is not None:
        doc.content_type = content_type
    if byte_size is not None:
        doc.byte_size = byte_size
    doc.download_status = download_status
    doc.scraped_at = scraped_at
    session.commit()


# --- Summary queries ---

def count_pps(session: Session) -> int:
    return session.query(PP).count()


def count_documents(session: Session) -> int:
    return session.query(Document).count()


def count_downloads_ok(session: Session) -> int:
    return session.query(Document).filter_by(download_status="ok").count()


def total_bytes_downloaded(session: Session) -> int:
    from sqlalchemy import func
    result = (
        session.query(func.coalesce(func.sum(Document.byte_size), 0))
        .filter_by(download_status="ok")
        .scalar()
    )
    return result


def failure_summary(session: Session) -> list[tuple[str, int]]:
    from sqlalchemy import func
    return (
        session.query(Document.download_status, func.count())
        .filter(Document.download_status.notin_(["ok", "pending"]))
        .group_by(Document.download_status)
        .all()
    )


def count_pending(session: Session) -> int:
    return session.query(Document).filter_by(download_status="pending").count()


# --- Chunk operations ---

from scraper.models import Chunk


def add_chunk(
    session: Session,
    document_id: int,
    pp_number: str,
    page_number: int,
    chunk_index: int,
    text: str,
    extraction_method: str,
    created_at: datetime,
) -> Chunk:
    chunk = Chunk(
        document_id=document_id,
        pp_number=pp_number,
        page_number=page_number,
        chunk_index=chunk_index,
        text=text,
        char_count=len(text),
        extraction_method=extraction_method,
        created_at=created_at,
    )
    session.add(chunk)
    return chunk


def has_chunks(session: Session, document_id: int) -> bool:
    return session.query(Chunk).filter_by(document_id=document_id).first() is not None


def get_chunks_for_document(session: Session, document_id: int) -> list[Chunk]:
    return (
        session.query(Chunk)
        .filter_by(document_id=document_id)
        .order_by(Chunk.page_number, Chunk.chunk_index)
        .all()
    )


def get_chunks_for_pp(session: Session, pp_number: str, tier_filter: list[int] | None = None) -> list[Chunk]:
    query = (
        session.query(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.pp_number == pp_number)
    )
    if tier_filter:
        query = query.filter(Document.tier.in_(tier_filter))
    return query.order_by(Chunk.document_id, Chunk.page_number, Chunk.chunk_index).all()


# --- Geocode operations ---

def update_pp_geocode(
    session: Session, pp_number: str, latitude: float, longitude: float, geo_source: str,
) -> None:
    pp = session.get(PP, pp_number)
    if pp:
        pp.latitude = latitude
        pp.longitude = longitude
        pp.geo_source = geo_source
        session.commit()


def get_pps_with_geocode(session: Session) -> list[PP]:
    return session.query(PP).filter(PP.latitude != None, PP.longitude != None).all()


def get_pps_for_lga(session: Session, council_name: str) -> list[PP]:
    return session.query(PP).filter(PP.council == council_name).all()


def get_pp_by_number(session: Session, pp_number: str) -> PP | None:
    return session.get(PP, pp_number)
