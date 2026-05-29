"""
Interview API Router.

Chat-based interview endpoints with session management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.interview import InterviewSession, InterviewMessage
from app.schemas.interview import (
    StartSessionRequest,
    SendMessageRequest,
    SessionResponse,
    SessionListItem,
    ModeratorResponse,
)
from app.services.moderator_agent import start_session, send_message, end_session

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Start a new interview session with an opening question."""
    return await start_session(db, request.topic)


@router.post("/sessions/{session_id}/messages", response_model=ModeratorResponse)
async def post_message(
    session_id: str,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a participant message and receive a moderator follow-up."""
    try:
        return await send_message(db, session_id, request.message)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sessions/{session_id}/end", response_model=SessionResponse)
async def end_session_endpoint(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """End a session and generate a summary."""
    try:
        return await end_session(db, session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """List all interview sessions."""
    stmt = select(InterviewSession).order_by(InterviewSession.created_at.desc())
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        count_stmt = select(func.count()).where(InterviewMessage.session_id == s.id)
        count_result = await db.execute(count_stmt)
        msg_count = count_result.scalar() or 0

        items.append(SessionListItem(
            id=s.id,
            topic=s.topic,
            status=s.status,
            message_count=msg_count,
            created_at=s.created_at,
        ))

    return items


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a full session with all messages."""
    from sqlalchemy.orm import selectinload

    stmt = (
        select(InterviewSession)
        .options(selectinload(InterviewSession.messages))
        .where(InterviewSession.id == session_id)
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from app.schemas.interview import MessageResponse
    messages = [
        MessageResponse(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
        )
        for msg in session.messages
    ]

    return SessionResponse(
        id=session.id,
        topic=session.topic,
        status=session.status,
        summary=session.summary,
        messages=messages,
        created_at=session.created_at,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete an interview session and its messages."""
    stmt = select(InterviewSession).where(InterviewSession.id == session_id)
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.delete(session)
    await db.commit()
    return {"status": "success", "message": f"Session {session_id} deleted"}

