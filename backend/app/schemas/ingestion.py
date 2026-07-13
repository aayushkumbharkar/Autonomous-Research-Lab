"""Pydantic schemas for the Ingestion module."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, StrictStr


class IngestTextRequest(BaseModel):
    """Request to ingest a text transcript."""
    model_config = ConfigDict(strict=True)

    text: StrictStr = Field(..., min_length=1, description="Raw transcript text")
    filename: StrictStr = Field(..., min_length=1, description="Source filename")
    metadata: Optional[dict] = Field(None, description="Additional metadata (speakers, context, etc.)")


class ChunkResponse(BaseModel):
    """A single chunk returned from the system."""
    id: str
    content: str
    chunk_index: int
    speaker: Optional[str] = None
    timestamp_start: Optional[float] = None
    timestamp_end: Optional[float] = None
    embedding_id: str

    model_config = {"from_attributes": True}


class TranscriptResponse(BaseModel):
    """Full transcript metadata response."""
    id: str
    filename: str
    source_type: str
    status: str
    error_message: Optional[str] = None
    metadata_json: Optional[dict] = None
    created_at: datetime
    chunk_count: int = 0

    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    """Response after successful ingestion."""
    transcript_id: str
    filename: str
    source_type: str
    chunk_count: int
    status: str
    message: str
