"""Pydantic schemas for the Research module."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ResearchQueryRequest(BaseModel):
    """Research query submission."""
    query: str = Field(..., min_length=1, description="Research question")
    top_k: int = Field(10, ge=1, le=50, description="Context chunks to retrieve")
    auto_evaluate: bool = Field(True, description="Run evaluation automatically")
    auto_improve: bool = Field(True, description="Trigger feedback loop if score is low")


class ClaimVerification(BaseModel):
    """Verification result for a single claim."""
    claim: str
    status: str  # "supported" | "partially_supported" | "unsupported"
    supporting_chunk_ids: list[str] = []
    confidence: float = 0.0


class CitationDetail(BaseModel):
    """Citation with full context."""
    index: int
    chunk_id: str
    content: str
    relevance_score: float


class ConfidenceSignal(BaseModel):
    """Confidence and uncertainty information."""
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_level: str  # "low" | "medium" | "high"
    disagreement_score: Optional[float] = None
    explanation: str = ""


class ResearchAnswerResponse(BaseModel):
    """Full research answer with all observability data."""
    query_id: str
    answer_id: str
    query_text: str
    answer_text: str
    reasoning_trace: Optional[str] = None
    attempt_number: int
    citations: list[CitationDetail] = []
    claim_verifications: list[ClaimVerification] = []
    confidence: ConfidenceSignal
    eval_scores: Optional[dict] = None
    created_at: datetime


class ResearchQueryListItem(BaseModel):
    """Summary of a research query for listing."""
    id: str
    query_text: str
    answer_count: int
    best_score: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}
