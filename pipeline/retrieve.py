"""Hybrid retrieval: dense vector (Chroma) + BM25 keyword search + reranker.

Flow:
  1. Vector search → top 20 candidates
  2. BM25 search → top 20 candidates
  3. Reciprocal Rank Fusion (RRF) → merged top 20
  4. Cohere rerank → top K (default 6)
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict

import chromadb
import cohere
import google.generativeai as genai
from rank_bm25 import BM25Okapi

from pipeline.embed import CHROMA_DIR, COLLECTION_NAME, EMBED_MODEL

logger = logging.getLogger(__name__)

# Cache BM25 index per (pp_number, tier_filter_key)
_bm25_cache: dict[str, tuple[BM25Okapi, list[dict]]] = {}


def _get_collection() -> chromadb.Collection:
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(name=COLLECTION_NAME)


def _embed_query(text: str) -> list[float]:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    result = genai.embed_content(
        model=EMBED_MODEL,
        content=text,
        task_type="RETRIEVAL_QUERY",
    )
    return result["embedding"]


def _build_where_filter(pp_number: str, tier_filter: list[int] | None) -> dict:
    if tier_filter:
        if len(tier_filter) == 1:
            return {"$and": [{"pp_number": pp_number}, {"tier": tier_filter[0]}]}
        else:
            return {"$and": [{"pp_number": pp_number}, {"tier": {"$in": tier_filter}}]}
    return {"pp_number": pp_number}


def _to_result_dict(meta: dict, text: str, score: float = 0.0) -> dict:
    return {
        "chunk_id": meta["chunk_id"],
        "text": text,
        "page_number": meta["page_number"],
        "document_title": meta["document_title"],
        "category": meta["category"],
        "tier": meta["tier"],
        "sub_tier": meta.get("sub_tier", ""),
        "concern_tag": meta.get("concern_tag", ""),
        "score": score,
    }


# ---------------------------------------------------------------------------
# Vector search
# ---------------------------------------------------------------------------

def _vector_search(query: str, pp_number: str, tier_filter: list[int] | None, n: int = 20) -> list[dict]:
    collection = _get_collection()
    query_embedding = _embed_query(query)
    where = _build_where_filter(pp_number, tier_filter)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        output.append(_to_result_dict(meta, results["documents"][0][i], results["distances"][0][i]))

    return output


# ---------------------------------------------------------------------------
# BM25 search
# ---------------------------------------------------------------------------

def _get_bm25_index(pp_number: str, tier_filter: list[int] | None) -> tuple[BM25Okapi, list[dict]]:
    """Build or retrieve cached BM25 index for a PP+tier combo."""
    cache_key = f"{pp_number}|{sorted(tier_filter) if tier_filter else 'all'}"

    if cache_key in _bm25_cache:
        return _bm25_cache[cache_key]

    collection = _get_collection()
    where = _build_where_filter(pp_number, tier_filter)

    # Get all chunks for this PP+tier
    all_results = collection.get(
        where=where,
        include=["documents", "metadatas"],
    )

    docs = []
    tokenized = []
    for i in range(len(all_results["ids"])):
        text = all_results["documents"][i]
        meta = all_results["metadatas"][i]
        docs.append(_to_result_dict(meta, text))
        tokenized.append(text.lower().split())

    if not tokenized:
        _bm25_cache[cache_key] = (BM25Okapi([[""]]), [])
        return _bm25_cache[cache_key]

    bm25 = BM25Okapi(tokenized)
    _bm25_cache[cache_key] = (bm25, docs)

    logger.debug("Built BM25 index for %s: %d documents", cache_key, len(docs))
    return bm25, docs


def _bm25_search(query: str, pp_number: str, tier_filter: list[int] | None, n: int = 20) -> list[dict]:
    bm25, docs = _get_bm25_index(pp_number, tier_filter)

    if not docs:
        return []

    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    # Get top-n indices
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
    """Merge two ranked lists using Reciprocal Rank Fusion."""
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
    """Rerank candidates using Cohere rerank API."""
    api_key = os.environ.get("COHERE_API_KEY")

    if not api_key or not candidates:
        # No reranker available — return top-k by RRF score
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
    """Hybrid retrieve: vector + BM25 + RRF merge + rerank.

    Returns top-k chunks with full metadata.
    """
    # Step 1+2: parallel retrieval
    vector_results = _vector_search(query, pp_number, tier_filter, n=20)
    bm25_results = _bm25_search(query, pp_number, tier_filter, n=20)

    # Step 3: RRF merge
    merged = _rrf_merge(vector_results, bm25_results)

    # Step 4: Rerank (top 20 → top k)
    reranked = _rerank(query, merged[:20], top_k=k)

    return reranked


if __name__ == "__main__":
    import sys
    os.environ.setdefault("GOOGLE_API_KEY", open(".env").read().split("=")[1].strip())

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
