"""SQLAlchemy ORM models for the scraper manifest."""

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

import os as _os
# Railway volume at /data, local fallback
_DATA_DIR = "/data" if _os.path.isdir("/data") else "."
DB_PATH = _os.path.join(_DATA_DIR, "manifest.sqlite")


class Base(DeclarativeBase):
    pass


class PP(Base):
    __tablename__ = "pps"

    pp_number = Column(String, primary_key=True)
    slug = Column(String, nullable=False)
    detail_url = Column(String, nullable=False)
    title = Column(Text)
    council = Column(String)
    addresses = Column(Text)  # JSON array
    description = Column(Text)
    exhibition_start = Column(Date)
    exhibition_end = Column(Date)
    stage = Column(String)
    relevant_planning_authority = Column(String)
    raw_html_path = Column(String, nullable=False, default="")
    scraped_at = Column(DateTime, nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geo_source = Column(String, nullable=True)  # 'address' | 'lga_centroid' | None

    documents = relationship("Document", back_populates="pp", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pp_number = Column(String, ForeignKey("pps.pp_number"), nullable=False)
    title = Column(String, nullable=False)
    category = Column(String)
    url = Column(String, nullable=False)
    sha256 = Column(String)
    file_path = Column(String)
    content_type = Column(String)
    byte_size = Column(Integer)
    download_status = Column(String, nullable=False, default="pending")
    tier = Column(Integer)          # 1=proposal(1a=main,1b=supporting), 2=technical, 3=admin
    sub_tier = Column(String)       # '1a'=main proposal, '1b'=supporting proposal docs
    concern_tag = Column(String)    # traffic, bushfire, ecology, etc.
    scraped_at = Column(DateTime, nullable=False)

    pp = relationship("PP", back_populates="documents")

    __table_args__ = (
        UniqueConstraint("pp_number", "url"),
        Index("idx_docs_sha", "sha256"),
        Index("idx_docs_pp", "pp_number"),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    pp_number = Column(String, nullable=False)
    page_number = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    char_count = Column(Integer, nullable=False)
    extraction_method = Column(String, nullable=False)  # 'pdfplumber' | 'failed'
    created_at = Column(DateTime, nullable=False)

    document = relationship("Document")

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", "chunk_index"),
        Index("idx_chunks_doc", "document_id"),
        Index("idx_chunks_pp", "pp_number"),
    )


def create_db_engine(db_path: str = DB_PATH):
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return engine


def create_session(engine) -> Session:
    return sessionmaker(bind=engine)()
