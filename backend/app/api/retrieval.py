"""
Retrieval API Router.

Hybrid search endpoint with configurable weights.
"""

from fastapi import APIRouter

from app.schemas.retrieval import SearchRequest, SearchResponse
from app.services.retrieval import hybrid_search

router = APIRouter(prefix="/api", tags=["retrieval"])


@router.post("/search", response_model=SearchResponse)
async def search_endpoint(request: SearchRequest):
    """Perform hybrid semantic + keyword search."""
    results, metadata = hybrid_search(
        query=request.query,
        top_k=request.top_k,
        semantic_weight=request.semantic_weight,
        keyword_weight=request.keyword_weight,
        filters=request.filters,
    )

    return SearchResponse(
        query=request.query,
        results=results,
        total_results=len(results),
        search_metadata=metadata,
    )
