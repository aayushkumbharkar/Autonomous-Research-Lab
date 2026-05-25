"""
Hybrid Retrieval Service.

Combines semantic search (ChromaDB) with keyword search (BM25)
using Reciprocal Rank Fusion (RRF) for robust retrieval.

Includes TTL-based caching to avoid redundant searches.
"""

import time
from typing import Optional

from app.services.embeddings import embed_query
from app.services.ingestion import get_collection, get_all_chunk_documents
from app.utils.bm25 import BM25Index, BM25Result
from app.schemas.retrieval import RetrievalResult
from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level BM25 index
_bm25_index = BM25Index()

# Simple TTL cache for retrieval results
_retrieval_cache: dict[str, tuple[float, list[RetrievalResult]]] = {}


def init_bm25():
    """Build BM25 index from all existing documents. Called at startup."""
    docs = get_all_chunk_documents()
    if docs:
        _bm25_index.build(docs)
        logger.info("bm25_initialized", doc_count=len(docs))
    else:
        logger.info("bm25_no_documents")


def rebuild_bm25():
    """Rebuild BM25 index. Called after ingestion."""
    docs = get_all_chunk_documents()
    _bm25_index.build(docs)
    # Invalidate cache on index rebuild
    _retrieval_cache.clear()
    logger.info("bm25_rebuilt", doc_count=len(docs))


def _cache_key(query: str, top_k: int, sw: float, kw: float) -> str:
    return f"{query}|{top_k}|{sw}|{kw}"


def _reciprocal_rank_fusion(
    semantic_results: list[dict],
    keyword_results: list[BM25Result],
    semantic_weight: float,
    keyword_weight: float,
    k: int = 60,
) -> list[dict]:
    """
    Reciprocal Rank Fusion (RRF) to merge two ranked lists.

    RRF score = sum(weight / (k + rank)) for each list the document appears in.

    Args:
        semantic_results: Results from ChromaDB semantic search
        keyword_results: Results from BM25 keyword search
        semantic_weight: Weight for semantic scores
        keyword_weight: Weight for keyword scores
        k: RRF constant (default 60)

    Returns:
        Fused results sorted by combined RRF score
    """
    scores: dict[str, dict] = {}

    # Process semantic results
    for rank, result in enumerate(semantic_results):
        doc_id = result["id"]
        rrf_score = semantic_weight / (k + rank + 1)
        scores[doc_id] = {
            "rrf_score": rrf_score,
            "semantic_score": result.get("distance", 0.0),
            "keyword_score": 0.0,
            "content": result.get("content", ""),
            "metadata": result.get("metadata", {}),
        }

    # Process keyword results
    for result in keyword_results:
        doc_id = result.doc_id
        rrf_score = keyword_weight / (k + result.rank)
        if doc_id in scores:
            scores[doc_id]["rrf_score"] += rrf_score
            scores[doc_id]["keyword_score"] = result.score
        else:
            scores[doc_id] = {
                "rrf_score": rrf_score,
                "semantic_score": 0.0,
                "keyword_score": result.score,
                "content": "",  # Will be filled from ChromaDB
                "metadata": {},
            }

    # Sort by RRF score
    sorted_results = sorted(scores.items(), key=lambda x: x[1]["rrf_score"], reverse=True)
    return [{"id": doc_id, **data} for doc_id, data in sorted_results]


def hybrid_search(
    query: str,
    top_k: int = 10,
    semantic_weight: float = 0.6,
    keyword_weight: float = 0.4,
    filters: Optional[dict] = None,
) -> tuple[list[RetrievalResult], dict]:
    """
    Perform hybrid search combining semantic and keyword search.

    Args:
        query: Search query
        top_k: Number of results to return
        semantic_weight: Weight for semantic search (0-1)
        keyword_weight: Weight for keyword search (0-1)
        filters: Optional metadata filters for ChromaDB

    Returns:
        Tuple of (results, search_metadata)
    """
    settings = get_settings()
    start_time = time.time()

    # Check cache
    cache_key = _cache_key(query, top_k, semantic_weight, keyword_weight)
    if cache_key in _retrieval_cache:
        cached_time, cached_results = _retrieval_cache[cache_key]
        if time.time() - cached_time < settings.retrieval_cache_ttl:
            logger.info("retrieval_cache_hit", query=query[:50])
            metadata = {
                "cached": True,
                "total_time_ms": round((time.time() - start_time) * 1000, 2),
            }
            return cached_results, metadata

    collection = get_collection()
    if collection.count() == 0:
        logger.warning("retrieval_empty_collection")
        return [], {"warning": "No documents indexed", "total_time_ms": 0}

    # 1. Semantic search via ChromaDB
    semantic_start = time.time()
    query_embedding = embed_query(query)

    chroma_kwargs = {
        "query_embeddings": [query_embedding.tolist()],
        "n_results": min(top_k * 2, collection.count()),  # Fetch more for fusion
        "include": ["documents", "metadatas", "distances"],
    }
    if filters:
        chroma_kwargs["where"] = filters

    chroma_results = collection.query(**chroma_kwargs)
    semantic_time = time.time() - semantic_start

    semantic_results = []
    if chroma_results["ids"] and chroma_results["ids"][0]:
        for i, doc_id in enumerate(chroma_results["ids"][0]):
            semantic_results.append({
                "id": doc_id,
                "content": chroma_results["documents"][0][i],
                "distance": 1 - chroma_results["distances"][0][i],  # Convert distance to similarity
                "metadata": chroma_results["metadatas"][0][i] if chroma_results["metadatas"] else {},
            })

    # 2. BM25 keyword search
    keyword_start = time.time()
    keyword_results = _bm25_index.search(query, top_k=top_k * 2)
    keyword_time = time.time() - keyword_start

    # 3. RRF Fusion
    fused = _reciprocal_rank_fusion(
        semantic_results, keyword_results,
        semantic_weight, keyword_weight,
    )

    # Build final results (top_k)
    results = []
    for item in fused[:top_k]:
        # Ensure we have content (might be missing for keyword-only matches)
        content = item["content"]
        if not content and item["id"]:
            # Fetch from ChromaDB
            try:
                doc = collection.get(ids=[item["id"]], include=["documents", "metadatas"])
                content = doc["documents"][0] if doc["documents"] else ""
                item["metadata"] = doc["metadatas"][0] if doc["metadatas"] else {}
            except Exception:
                continue

        metadata = item.get("metadata", {})
        results.append(RetrievalResult(
            chunk_id=item["id"],
            content=content,
            score=round(item["rrf_score"], 4),
            semantic_score=round(item["semantic_score"], 4),
            keyword_score=round(item["keyword_score"], 4),
            speaker=metadata.get("speaker", None) or None,
            transcript_id=metadata.get("transcript_id", ""),
            chunk_index=metadata.get("chunk_index", 0),
        ))

    total_time = time.time() - start_time

    search_metadata = {
        "cached": False,
        "semantic_time_ms": round(semantic_time * 1000, 2),
        "keyword_time_ms": round(keyword_time * 1000, 2),
        "total_time_ms": round(total_time * 1000, 2),
        "semantic_results_count": len(semantic_results),
        "keyword_results_count": len(keyword_results),
        "fused_results_count": len(results),
    }

    # Cache results
    _retrieval_cache[cache_key] = (time.time(), results)

    logger.info("hybrid_search_complete",
                query=query[:50],
                results=len(results),
                time_ms=search_metadata["total_time_ms"])

    return results, search_metadata
