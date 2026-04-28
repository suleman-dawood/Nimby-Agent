"""Embed chunks into PostgreSQL using pgvector + Gemini embeddings."""

from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from scraper.models import Chunk, Document, create_db_engine, create_session

logger = logging.getLogger(__name__)

EMBED_MODEL = "gemini-embedding-001"
BATCH_SIZE = 100
RATE_DELAY = 0.5


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


def embed_query(text: str) -> list[float]:
    """Embed a single query text."""
    from pipeline.llm_utils import get_client
    client = get_client()
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=text,
        config={"task_type": "RETRIEVAL_QUERY"},
    )
    return result.embeddings[0].values


def embed_all(session: Session, tiers: list[int] | None = None) -> None:
    """Embed all chunks without embeddings into PostgreSQL."""
    query = (
        session.query(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.extraction_method == "pdfplumber")
        .filter(Chunk.embedding.is_(None))
    )
    if tiers:
        query = query.filter(Document.tier.in_(tiers))

    chunks = query.order_by(Chunk.id).all()
    logger.info("Chunks to embed: %d", len(chunks))

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c.text for c in batch]

        try:
            embeddings = embed_texts(texts)
            for chunk, emb in zip(batch, embeddings):
                chunk.embedding = emb
            session.commit()
            logger.info("Embedded batch %d-%d / %d", i + 1, i + len(batch), len(chunks))
        except Exception as e:
            session.rollback()
            logger.error("Batch %d failed: %s", i, e)

        time.sleep(RATE_DELAY)

    total = session.query(Chunk).filter(Chunk.embedding.isnot(None)).count()
    print(f"\nEmbedding complete. Total with embeddings: {total}")


if __name__ == "__main__":
    import argparse

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
