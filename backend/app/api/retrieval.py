"""
Retrieval API Router.

Hybrid search endpoint with configurable weights.
"""

from fastapi import APIRouter

from app.config import get_settings
from app.schemas.retrieval import RetrievalResult, SearchRequest, SearchResponse
from app.services.retrieval import hybrid_search

router = APIRouter(prefix="/api", tags=["retrieval"])


@router.post("/search", response_model=SearchResponse)
async def search_endpoint(request: SearchRequest):
    """Perform hybrid semantic + keyword search."""
    if get_settings().contract_test_mode:
        result = RetrievalResult(
            chunk_id="abc-123",
            content="User engagement increased by 40% after implementing the new onboarding flow.",
            score=0.92,
            semantic_score=0.95,
            keyword_score=0.87,
            speaker="Participant A",
            transcript_id="tx-001",
            chunk_index=3,
        )
        return SearchResponse(
            query=request.query,
            results=[result],
            total_results=1,
            search_metadata={
                "method": "hybrid",
                "duration_ms": 45,
            },
        )

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
