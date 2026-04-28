"""Hybrid retrieval: pgvector dense search + BM25 keyword search + reranker.

Flow:
  1. Vector search (pgvector cosine) → top 20 candidates
  2. BM25 search → top 20 candidates
  3. Reciprocal Rank Fusion (RRF) → merged top 20
  4. Cohere rerank → top K (default 6)
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict

import cohere
from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session

from scraper.models import Chunk, Document, create_db_engine, create_session
from pipeline.embed import embed_query

logger = logging.getLogger(__name__)

# Cache BM25 index per (pp_number, tier_filter_key)
_bm25_cache: dict[str, tuple[BM25Okapi, list[dict]]] = {}


def _to_result_dict(chunk: Chunk, doc: Document, score: float = 0.0) -> dict:
    return {
        "chunk_id": chunk.id,
        "text": chunk.text,
        "page_number": chunk.page_number,
        "document_title": doc.title,
        "category": doc.category or "",
        "tier": doc.tier or 0,
        "sub_tier": doc.sub_tier or "",
        "concern_tag": doc.concern_tag or "",
        "score": score,
    }


# ---------------------------------------------------------------------------
# Vector search (pgvector)
# ---------------------------------------------------------------------------

def _vector_search(
    session: Session, query: str, pp_number: str,
    tier_filter: list[int] | None, n: int = 20
) -> list[dict]:
    query_embedding = embed_query(query)

    q = (
        session.query(Chunk, Document, Chunk.embedding.cosine_distance(query_embedding).label("distance"))
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.pp_number == pp_number)
        .filter(Chunk.embedding.isnot(None))
    )
    if tier_filter:
        q = q.filter(Document.tier.in_(tier_filter))

    q = q.order_by("distance").limit(n)

    results = []
    for chunk, doc, distance in q.all():
        results.append(_to_result_dict(chunk, doc, float(distance)))

    return results


# ---------------------------------------------------------------------------
# BM25 search
# ---------------------------------------------------------------------------

def _get_bm25_index(
    session: Session, pp_number: str, tier_filter: list[int] | None
) -> tuple[BM25Okapi, list[dict]]:
    cache_key = f"{pp_number}|{sorted(tier_filter) if tier_filter else 'all'}"

    if cache_key in _bm25_cache:
        return _bm25_cache[cache_key]

    q = (
        session.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.pp_number == pp_number)
        .filter(Chunk.extraction_method == "pdfplumber")
    )
    if tier_filter:
        q = q.filter(Document.tier.in_(tier_filter))

    rows = q.all()
    docs = []
    tokenized = []
    for chunk, doc in rows:
        docs.append(_to_result_dict(chunk, doc))
        tokenized.append(chunk.text.lower().split())

    if not tokenized:
        _bm25_cache[cache_key] = (BM25Okapi([[""]]), [])
        return _bm25_cache[cache_key]

    bm25 = BM25Okapi(tokenized)
    _bm25_cache[cache_key] = (bm25, docs)

    logger.debug("Built BM25 index for %s: %d documents", cache_key, len(docs))
    return bm25, docs


def _bm25_search(
    session: Session, query: str, pp_number: str,
    tier_filter: list[int] | None, n: int = 20
) -> list[dict]:
    bm25, docs = _get_bm25_index(session, pp_number, tier_filter)

    if not docs:
        return []

    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]

    output = []
    for idx in ranked:
        if scores[idx] > 0:
            result = dict(docs[idx])
            result["score"] = float(scores[idx])
            output.append(result)

    return output


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

def _rrf_merge(vector_results: list[dict], bm25_results: list[dict], k: int = 60) -> list[dict]:
    scores: dict[int, float] = defaultdict(float)
    chunk_map: dict[int, dict] = {}

    for rank, r in enumerate(vector_results):
        cid = r["chunk_id"]
        scores[cid] += 1.0 / (k + rank)
        chunk_map[cid] = r

    for rank, r in enumerate(bm25_results):
        cid = r["chunk_id"]
        scores[cid] += 1.0 / (k + rank)
        if cid not in chunk_map:
            chunk_map[cid] = r

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    output = []
    for cid, score in ranked:
        result = dict(chunk_map[cid])
        result["rrf_score"] = score
        output.append(result)

    return output


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------

def _rerank(query: str, candidates: list[dict], top_k: int = 6) -> list[dict]:
    api_key = os.environ.get("COHERE_API_KEY")

    if not api_key or not candidates:
        return candidates[:top_k]

    try:
        co = cohere.ClientV2(api_key=api_key)
        texts = [r["text"][:2000] for r in candidates]

        response = co.rerank(
            model="rerank-v3.5",
            query=query,
            documents=texts,
            top_n=top_k,
        )

        output = []
        for result in response.results:
            candidate = dict(candidates[result.index])
            candidate["rerank_score"] = result.relevance_score
            output.append(candidate)

        return output

    except Exception as e:
        logger.warning("Reranker failed, falling back to RRF top-k: %s", e)
        return candidates[:top_k]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def retrieve(
    pp_number: str,
    query: str,
    k: int = 6,
    tier_filter: list[int] | None = None,
) -> list[dict]:
    """Hybrid retrieve: pgvector + BM25 + RRF merge + rerank."""
    engine = create_db_engine()
    session = create_session(engine)

    try:
        vector_results = _vector_search(session, query, pp_number, tier_filter, n=20)
        bm25_results = _bm25_search(session, query, pp_number, tier_filter, n=20)

        merged = _rrf_merge(vector_results, bm25_results)
        reranked = _rerank(query, merged[:20], top_k=k)

        return reranked
    finally:
        session.close()


if __name__ == "__main__":
    import sys

    pp = sys.argv[1] if len(sys.argv) > 1 else "PP-2023-2828"
    query = sys.argv[2] if len(sys.argv) > 2 else "proposed building heights"

    results = retrieve(pp, query)
    print(f"Query: '{query}' for {pp}\n")
    for r in results:
        rerank = f" rerank={r['rerank_score']:.3f}" if "rerank_score" in r else ""
        rrf = f" rrf={r.get('rrf_score', 0):.4f}"
        print(f"  [{r['document_title'][:45]}] p.{r['page_number']}{rrf}{rerank}")
        print(f"    {r['text'][:150]}...")
        print()
