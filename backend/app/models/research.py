"""
Research Query, Answer, and Citation ORM models.

Every research answer is traceable: query → context → answer → citations → evaluation.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class ResearchQuery(Base):
    __tablename__ = "research_queries"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    answers: Mapped[list["ResearchAnswer"]] = relationship(
        "ResearchAnswer", back_populates="query", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ResearchQuery {self.id[:8]}>"


class ResearchAnswer(Base):
    __tablename__ = "research_answers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    query_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_queries.id"), nullable=False
    )
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_trace: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(20), default="unknown")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    query: Mapped["ResearchQuery"] = relationship(
        "ResearchQuery", back_populates="answers"
    )
    citations: Mapped[list["Citation"]] = relationship(
        "Citation", back_populates="answer", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ResearchAnswer {self.id[:8]} attempt={self.attempt_number}>"


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    answer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_answers.id"), nullable=False
    )
    chunk_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chunks.id"), nullable=False
    )
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    citation_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    answer: Mapped["ResearchAnswer"] = relationship(
        "ResearchAnswer", back_populates="citations"
    )

    def __repr__(self):
        return f"<Citation [{self.citation_index}] chunk={self.chunk_id[:8]}>"
