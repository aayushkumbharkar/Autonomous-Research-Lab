"""Pydantic schemas for the Retrieval module."""

from typing import Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Hybrid search request."""
    query: str = Field(..., min_length=1, description="Search query")
    top_k: int = Field(10, ge=1, le=100, description="Number of results")
    semantic_weight: float = Field(0.6, ge=0.0, le=1.0)
    keyword_weight: float = Field(0.4, ge=0.0, le=1.0)
    filters: Optional[dict] = Field(None, description="Metadata filters")


class RetrievalResult(BaseModel):
    """A single retrieval result with provenance."""
    chunk_id: str
    content: str
    score: float
    semantic_score: float
    keyword_score: float
    speaker: Optional[str] = None
    transcript_id: str
    chunk_index: int


class SearchResponse(BaseModel):
    """Search response with metadata for observability."""
    query: str
    results: list[RetrievalResult]
    total_results: int
    search_metadata: dict = Field(
        default_factory=dict,
        description="Timing, method breakdown, cache status",
    )
