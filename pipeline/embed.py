"""Embed chunks into ChromaDB using Gemini text-embedding-004."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import chromadb
from sqlalchemy.orm import Session

from scraper.models import Chunk, Document, create_db_engine, create_session

logger = logging.getLogger(__name__)

CHROMA_DIR = Path("data/chroma")
COLLECTION_NAME = "pp_chunks"
EMBED_MODEL = "gemini-embedding-001"
BATCH_SIZE = 100  # Gemini allows up to 100 texts per embed call
RATE_DELAY = 0.5  # seconds between batches


def get_collection() -> chromadb.Collection:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using Gemini via ADC."""
    from pipeline.llm_utils import get_client
    client = get_client()
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
        config={"task_type": "RETRIEVAL_DOCUMENT"},
    )
    return [e.values for e in result.embeddings]


def embed_all(session: Session, tiers: list[int] | None = None) -> None:
    """Embed all chunks (optionally filtered by tier) into ChromaDB."""
    # ADC credentials used automatically via get_client()

    collection = get_collection()
    existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()
    logger.info("ChromaDB has %d existing vectors", len(existing_ids))

    query = (
        session.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.extraction_method == "pdfplumber")
    )
    if tiers:
        query = query.filter(Document.tier.in_(tiers))

    rows = query.order_by(Chunk.id).all()
    logger.info("Found %d chunks to embed", len(rows))

    # Filter out already-embedded
    to_embed = [(chunk, doc) for chunk, doc in rows if str(chunk.id) not in existing_ids]
    logger.info("New chunks to embed: %d (skipping %d)", len(to_embed), len(rows) - len(to_embed))

    for i in range(0, len(to_embed), BATCH_SIZE):
        batch = to_embed[i : i + BATCH_SIZE]

        ids = [str(chunk.id) for chunk, _ in batch]
        texts = [chunk.text for chunk, _ in batch]
        metadatas = [
            {
                "chunk_id": chunk.id,
                "document_id": doc.id,
                "pp_number": chunk.pp_number,
                "page_number": chunk.page_number,
                "document_title": doc.title or "",
                "category": doc.category or "",
                "tier": doc.tier or 0,
                "sub_tier": doc.sub_tier or "",
                "concern_tag": doc.concern_tag or "",
            }
            for chunk, doc in batch
        ]

        try:
            embeddings = embed_texts(texts)
            collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
            logger.info("Embedded batch %d-%d / %d", i + 1, i + len(batch), len(to_embed))
        except Exception as e:
            logger.error("Batch %d failed: %s", i, e)

        time.sleep(RATE_DELAY)

    print(f"\nEmbedding complete:")
    print(f"  Total in ChromaDB: {collection.count()}")


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--tiers", type=int, nargs="+", default=[1, 2])
    args = parser.parse_args()

    engine = create_db_engine()
    session = create_session(engine)

    try:
        embed_all(session, args.tiers)
    finally:
        session.close()
