"""Migrate data from local SQLite + ChromaDB → Railway PostgreSQL.

Usage:
    DATABASE_URL="postgresql://user:pass@host:port/db" python scripts/migrate_to_postgres.py

Reads from:
    - manifest.sqlite (local SQLite)
    - data/chroma/ (ChromaDB embeddings)

Writes to:
    - PostgreSQL (DATABASE_URL) with pgvector
"""

import os
import sys
from pathlib import Path

import chromadb
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scraper.models import Base, PP, Document, Chunk, EMBEDDING_DIM


def main():
    pg_url = os.environ.get("DATABASE_URL")
    if not pg_url:
        print("ERROR: Set DATABASE_URL env var to your Railway Postgres URL")
        print("Example: DATABASE_URL='postgresql://postgres:xxx@xxx.railway.app:5432/railway'")
        sys.exit(1)

    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    # Source: local SQLite
    sqlite_engine = create_engine("sqlite:///manifest.sqlite", echo=False)
    SqliteSession = sessionmaker(bind=sqlite_engine)
    sqlite_session = SqliteSession()

    # Target: Railway Postgres
    pg_engine = create_engine(pg_url, echo=False)
    with pg_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(pg_engine)
    PgSession = sessionmaker(bind=pg_engine)
    pg_session = PgSession()

    # Load ChromaDB embeddings
    chroma_dir = Path("data/chroma")
    chroma_embeddings = {}
    if chroma_dir.exists():
        print("Loading ChromaDB embeddings...")
        client = chromadb.PersistentClient(path=str(chroma_dir))
        try:
            collection = client.get_collection("pp_chunks")
            all_data = collection.get(include=["embeddings"])
            for id_, embedding in zip(all_data["ids"], all_data["embeddings"]):
                chroma_embeddings[int(id_)] = embedding
            print(f"  Loaded {len(chroma_embeddings)} embeddings from ChromaDB")
        except Exception as e:
            print(f"  ChromaDB load failed: {e}")
    else:
        print("No ChromaDB found, migrating without embeddings")

    # Migrate PPs
    print("\nMigrating PPs...")
    pps = sqlite_session.query(PP).all()
    for pp in pps:
        existing = pg_session.get(PP, pp.pp_number)
        if existing:
            continue
        pg_pp = PP(
            pp_number=pp.pp_number,
            slug=pp.slug,
            detail_url=pp.detail_url,
            title=pp.title,
            council=pp.council,
            addresses=pp.addresses,
            description=pp.description,
            exhibition_start=pp.exhibition_start,
            exhibition_end=pp.exhibition_end,
            stage=pp.stage,
            relevant_planning_authority=pp.relevant_planning_authority,
            raw_html_path=pp.raw_html_path,
            scraped_at=pp.scraped_at,
            latitude=pp.latitude,
            longitude=pp.longitude,
            geo_source=pp.geo_source,
        )
        pg_session.add(pg_pp)
    pg_session.commit()
    print(f"  Migrated {len(pps)} PPs")

    # Migrate Documents
    print("Migrating Documents...")
    docs = sqlite_session.query(Document).all()
    for doc in docs:
        existing = pg_session.query(Document).filter_by(
            pp_number=doc.pp_number, url=doc.url
        ).first()
        if existing:
            continue
        pg_doc = Document(
            pp_number=doc.pp_number,
            title=doc.title,
            category=doc.category,
            url=doc.url,
            sha256=doc.sha256,
            file_path=doc.file_path,
            content_type=doc.content_type,
            byte_size=doc.byte_size,
            download_status=doc.download_status,
            tier=doc.tier,
            sub_tier=doc.sub_tier,
            concern_tag=doc.concern_tag,
            scraped_at=doc.scraped_at,
        )
        pg_session.add(pg_doc)
    pg_session.commit()
    print(f"  Migrated {len(docs)} Documents")

    # Build document ID mapping (SQLite IDs → Postgres IDs)
    print("Building document ID mapping...")
    id_map = {}
    for doc in docs:
        pg_doc = pg_session.query(Document).filter_by(
            pp_number=doc.pp_number, url=doc.url
        ).first()
        if pg_doc:
            id_map[doc.id] = pg_doc.id

    # Migrate Chunks with embeddings
    print("Migrating Chunks + embeddings...")
    # Query SQLite without the embedding column (it doesn't exist there)
    from sqlalchemy import select, column, table
    chunks_table = table("chunks",
        column("id"), column("document_id"), column("pp_number"),
        column("page_number"), column("chunk_index"), column("text"),
        column("char_count"), column("extraction_method"), column("created_at"),
    )
    raw_chunks = sqlite_session.execute(select(chunks_table)).fetchall()

    # Convert to simple objects
    class ChunkRow:
        pass

    chunks = []
    for row in raw_chunks:
        c = ChunkRow()
        c.id, c.document_id, c.pp_number, c.page_number, c.chunk_index, \
            c.text, c.char_count, c.extraction_method, c.created_at = row
        chunks.append(c)
    batch_size = 500
    migrated = 0
    skipped = 0

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        for chunk in batch:
            pg_doc_id = id_map.get(chunk.document_id)
            if not pg_doc_id:
                skipped += 1
                continue

            existing = pg_session.query(Chunk).filter_by(
                document_id=pg_doc_id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
            ).first()
            if existing:
                # Update embedding if we have one and it's missing
                if existing.embedding is None and chunk.id in chroma_embeddings:
                    existing.embedding = chroma_embeddings[chunk.id]
                skipped += 1
                continue

            embedding = chroma_embeddings.get(chunk.id)

            pg_chunk = Chunk(
                document_id=pg_doc_id,
                pp_number=chunk.pp_number,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                char_count=chunk.char_count,
                extraction_method=chunk.extraction_method,
                created_at=chunk.created_at,
                embedding=embedding,
            )
            pg_session.add(pg_chunk)
            migrated += 1

        pg_session.commit()
        print(f"  Batch {i+1}-{i+len(batch)} / {len(chunks)} (migrated: {migrated}, skipped: {skipped})")

    pg_session.commit()

    # Create vector index for fast similarity search
    print("\nCreating pgvector index...")
    with pg_engine.connect() as conn:
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding
            ON chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """))
        conn.commit()

    # Summary
    pg_pp_count = pg_session.query(PP).count()
    pg_doc_count = pg_session.query(Document).count()
    pg_chunk_count = pg_session.query(Chunk).count()
    pg_embedded = pg_session.query(Chunk).filter(Chunk.embedding.isnot(None)).count()

    print(f"\n✓ Migration complete!")
    print(f"  PPs: {pg_pp_count}")
    print(f"  Documents: {pg_doc_count}")
    print(f"  Chunks: {pg_chunk_count}")
    print(f"  With embeddings: {pg_embedded}")

    sqlite_session.close()
    pg_session.close()


if __name__ == "__main__":
    main()
