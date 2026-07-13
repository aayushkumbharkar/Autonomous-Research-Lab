"""Pydantic schemas for the Interview module."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, StrictStr


class StartSessionRequest(BaseModel):
    """Start a new interview session."""
    model_config = ConfigDict(strict=True)

    topic: StrictStr = Field(..., min_length=1, description="Interview topic")


class SendMessageRequest(BaseModel):
    """Send a participant message."""
    model_config = ConfigDict(strict=True)

    message: StrictStr = Field(..., min_length=1, description="Participant response")


class MessageResponse(BaseModel):
    """A single chat message."""
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    """Full interview session with messages."""
    id: str
    topic: str
    status: str
    summary: Optional[str] = None
    messages: list[MessageResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionListItem(BaseModel):
    """Summary for session listing."""
    id: str
    topic: str
    status: str
    message_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class ModeratorResponse(BaseModel):
    """Response from the moderator agent."""
    message: MessageResponse
    suggested_topics: list[str] = []
    topics_covered: list[str] = []
