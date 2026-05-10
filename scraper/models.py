"""SQLAlchemy ORM models."""

import os

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
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
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

# Database URL: Railway provides DATABASE_URL, local dev uses SQLite fallback
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///manifest.sqlite",
)

# Railway Postgres URLs use postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

EMBEDDING_DIM = 3072  # gemini-embedding-001 output dimension


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
    geo_source = Column(String, nullable=True)

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
    tier = Column(Integer)
    sub_tier = Column(String)
    concern_tag = Column(String)
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
    extraction_method = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)

    document = relationship("Document")

    __table_args__ = (
        UniqueConstraint("document_id", "page_number", "chunk_index"),
        Index("idx_chunks_doc", "document_id"),
        Index("idx_chunks_pp", "pp_number"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    google_id = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    name = Column(String)
    avatar_url = Column(String)
    tokens_remaining = Column(Integer, nullable=False, default=50)
    tokens_used = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False)
    last_login = Column(DateTime, nullable=False)


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)       # "agent_chat" | "submission" | "brief"
    tokens_spent = Column(Integer, nullable=False)
    pp_number = Column(String)
    created_at = Column(DateTime, nullable=False)

    user = relationship("User")


class SiteContext(Base):
    __tablename__ = "site_contexts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pp_number = Column(String, ForeignKey("pps.pp_number"), unique=True, nullable=False)
    zoning = Column(String)
    max_height_m = Column(Float)
    max_fsr = Column(Float)
    min_lot_size_sqm = Column(Float)
    heritage_item = Column(String)
    heritage_state = Column(Boolean, default=False)
    bushfire_prone = Column(Boolean, default=False)
    bushfire_category = Column(String)
    flood_planning = Column(Boolean, default=False)
    landslide_risk = Column(String)
    acid_sulfate_class = Column(Integer)
    biodiversity_sensitive = Column(Boolean, default=False)
    drinking_water_catchment = Column(Boolean, default=False)
    wetlands_nearby = Column(Boolean, default=False)
    environmentally_sensitive = Column(String)
    raw_json = Column(Text)
    queried_at = Column(DateTime, nullable=False)

    pp = relationship("PP")


class Brief(Base):
    __tablename__ = "briefs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pp_number = Column(String, ForeignKey("pps.pp_number"), unique=True, nullable=False)
    markdown = Column(Text, nullable=False)
    doc_count = Column(Integer)  # number of docs used to generate
    chunk_count = Column(Integer)  # number of chunks at generation time
    generated_at = Column(DateTime, nullable=False)

    pp = relationship("PP")


class Watcher(Base):
    __tablename__ = "watchers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    email = Column(String, nullable=False)
    address = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False, default=5.0)
    webhook_url = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    active = Column(Boolean, nullable=False, default=True)

    user = relationship("User")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    watcher_id = Column(Integer, ForeignKey("watchers.id"), nullable=False)
    pp_number = Column(String, ForeignKey("pps.pp_number"), nullable=False)
    channel = Column(String, nullable=False)
    status = Column(String, nullable=False)
    payload = Column(Text)
    sent_at = Column(DateTime, nullable=False)

    watcher = relationship("Watcher")


def create_db_engine(db_url: str = DATABASE_URL):
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}

    engine = create_engine(db_url, echo=False, connect_args=connect_args)

    # Enable pgvector extension if using Postgres
    if "postgresql" in db_url:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

    Base.metadata.create_all(engine)
    return engine


def create_session(engine) -> Session:
    return sessionmaker(bind=engine)()
