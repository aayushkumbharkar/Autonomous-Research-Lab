"""
Evaluation ORM models: EvalRun, EvalScore, FeedbackAttempt, FailurePattern.

The FailurePattern table is the core of the Failure Memory System —
it stores learned fix strategies across sessions for similar query patterns.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    answer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_answers.id"), nullable=False
    )
    composite_score: Mapped[float] = mapped_column(Float, default=0.0)
    # Deterministic signals (new — hybrid evaluation)
    citation_coverage: Mapped[float] = mapped_column(
        Float, default=0.0
    )  # % of sentences with citations
    retrieval_overlap: Mapped[float] = mapped_column(
        Float, default=0.0
    )  # token overlap ratio
    claim_support_ratio: Mapped[float] = mapped_column(
        Float, default=0.0
    )  # verified claims / total claims
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    scores: Mapped[list["EvalScore"]] = relationship(
        "EvalScore", back_populates="eval_run", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<EvalRun {self.id[:8]} score={self.composite_score:.2f}>"


class EvalScore(Base):
    __tablename__ = "eval_scores"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    eval_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("eval_runs.id"), nullable=False
    )
    dimension: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # faithfulness | coverage | specificity | retrieval_quality
    score: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    is_deterministic: Mapped[bool] = mapped_column(
        default=False
    )  # True = rule-based, False = LLM-based

    # Relationships
    eval_run: Mapped["EvalRun"] = relationship("EvalRun", back_populates="scores")

    def __repr__(self):
        return f"<EvalScore {self.dimension}={self.score:.2f}>"


class FeedbackAttempt(Base):
    __tablename__ = "feedback_attempts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    query_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_queries.id"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    modification_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "prompt_rewrite" | "retrieval_expand" | "retrieval_filter" | "from_memory"
    previous_score: Mapped[float] = mapped_column(Float, nullable=False)
    new_score: Mapped[float] = mapped_column(Float, nullable=False)
    improvement: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    def __repr__(self):
        return f"<FeedbackAttempt #{self.attempt_number} Δ={self.improvement:+.2f}>"


class FailurePattern(Base):
    """
    Failure Memory System: stores learned fixes across sessions.
    When a retry strategy succeeds, we record the pattern so future
    queries with similar failure types can skip to the best fix.
    """
    __tablename__ = "failure_patterns"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    query_pattern: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # Generalized query pattern
    failure_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "low_faithfulness" | "low_coverage" | "low_specificity" | "low_retrieval"
    best_fix: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # The modification_type that worked
    fix_details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    success_count: Mapped[int] = mapped_column(Integer, default=1)
    avg_improvement: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self):
        return f"<FailurePattern '{self.failure_type}' fix='{self.best_fix}' ×{self.success_count}>"
