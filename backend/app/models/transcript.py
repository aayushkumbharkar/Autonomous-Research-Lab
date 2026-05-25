"""
Transcript and Chunk ORM models.

Transcripts are the raw input (text or audio-derived).
Chunks are the indexed units stored in ChromaDB for retrieval.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="text"
    )  # "text" | "audio"
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    status: Mapped[str] = mapped_column(
        String(20), default="processed"
    )  # "processing" | "processed" | "failed"
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    chunks: Mapped[list["Chunk"]] = relationship(
        "Chunk", back_populates="transcript", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Transcript {self.id[:8]} '{self.filename}'>"


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    transcript_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("transcripts.id"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timestamp_start: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp_end: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    embedding_id: Mapped[str] = mapped_column(
        String(36), nullable=False
    )  # ChromaDB document ID
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    # Relationships
    transcript: Mapped["Transcript"] = relationship(
        "Transcript", back_populates="chunks"
    )

    def __repr__(self):
        return f"<Chunk {self.id[:8]} idx={self.chunk_index}>"
