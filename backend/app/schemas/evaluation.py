"""Pydantic schemas for the Evaluation module."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EvalRequest(BaseModel):
    """Manual evaluation request."""
    answer_id: str = Field(..., description="Answer to evaluate")


class EvalScoreResponse(BaseModel):
    """Single dimension score."""
    dimension: str
    score: float
    explanation: str
    is_deterministic: bool = False

    model_config = {"from_attributes": True}


class EvalRunResponse(BaseModel):
    """Full evaluation run result."""
    id: str
    answer_id: str
    composite_score: float
    citation_coverage: float
    retrieval_overlap: float
    claim_support_ratio: float
    scores: list[EvalScoreResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackAttemptResponse(BaseModel):
    """Feedback loop attempt details."""
    id: str
    attempt_number: int
    modification_type: str
    previous_score: float
    new_score: float
    improvement: float
    details: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RetryComparisonResponse(BaseModel):
    """Side-by-side retry comparison for the UI."""
    query_id: str
    query_text: str
    attempts: list[dict] = []  # Each has: answer_text, scores, attempt_number
    best_attempt: int
    total_improvement: float
