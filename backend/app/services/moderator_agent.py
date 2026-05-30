"""
Moderator Agent.

Conducts adaptive interviews:
- Asks follow-up questions based on previous answers
- Maintains conversational context
- Tracks covered vs remaining topics
- Produces session summaries
"""

from typing import Optional

from groq import Groq
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.interview import InterviewSession, InterviewMessage
from app.schemas.interview import (
    SessionResponse,
    MessageResponse,
    ModeratorResponse,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


MODERATOR_SYSTEM_PROMPT = """You are an expert research interviewer conducting a structured interview.

INTERVIEW GUIDELINES:
1. Start with broad, open-ended questions to establish context.
2. Ask specific follow-up questions based on what the participant says.
3. Probe for specifics: "Can you give a concrete example?", "What exactly happened?"
4. Gently redirect if the participant goes off-topic.
5. Avoid yes/no questions — ask open-ended questions that elicit detailed responses.
6. Track what topics have been covered and what remains.
7. Show active listening by referencing previous answers.

RESPONSE FORMAT:
Respond with your next question or follow-up. Be concise but thoughtful.
At the end of your response, include a line:
TOPICS_COVERED: <comma-separated list of topics discussed so far>
TOPICS_REMAINING: <comma-separated list of topics still to explore>"""


SUMMARY_PROMPT = """Summarize the following interview transcript.

Include:
1. Key themes and insights
2. Important quotes or data points mentioned
3. Areas that need further exploration
4. Overall assessment of the interview quality

Transcript:
{transcript}

Provide a structured, professional summary."""


async def start_session(
    db: AsyncSession,
    topic: str,
) -> SessionResponse:
    """
    Start a new interview session.

    Creates the session and generates the first moderator question.
    """
    settings = get_settings()

    session = InterviewSession(topic=topic)
    db.add(session)
    await db.flush()

    # Generate opening question
    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model=settings.groq_fast_model,
        messages=[
            {"role": "system", "content": MODERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": f"Begin an interview about: {topic}\n\nAsk your opening question."},
        ],
        temperature=0.7,
        max_tokens=512,
    )

    opening_text = response.choices[0].message.content or "Tell me about your experience with this topic."

    # Parse topics if present
    clean_text, _, _ = _parse_topics(opening_text)

    opening_msg = InterviewMessage(
        session_id=session.id,
        role="moderator",
        content=clean_text,
    )
    db.add(opening_msg)
    await db.flush()

    return SessionResponse(
        id=session.id,
        topic=session.topic,
        status=session.status,
        messages=[MessageResponse(
            id=opening_msg.id,
            role=opening_msg.role,
            content=opening_msg.content,
            created_at=opening_msg.created_at,
        )],
        created_at=session.created_at,
    )


def _parse_topics(text: str) -> tuple[str, list[str], list[str]]:
    """Extract topic tracking from moderator response."""
    import re

    covered = []
    remaining = []
    clean_text = text

    covered_match = re.search(r'TOPICS_COVERED:\s*(.+?)(?:\n|$)', text)
    if covered_match:
        covered = [t.strip() for t in covered_match.group(1).split(',') if t.strip()]
        clean_text = clean_text.replace(covered_match.group(0), '').strip()

    remaining_match = re.search(r'TOPICS_REMAINING:\s*(.+?)(?:\n|$)', text)
    if remaining_match:
        remaining = [t.strip() for t in remaining_match.group(1).split(',') if t.strip()]
        clean_text = clean_text.replace(remaining_match.group(0), '').strip()

    return clean_text, covered, remaining


async def send_message(
    db: AsyncSession,
    session_id: str,
    message: str,
) -> ModeratorResponse:
    """
    Process a participant message and generate moderator follow-up.

    Maintains full conversation context.
    """
    settings = get_settings()

    # Load session with messages
    stmt = (
        select(InterviewSession)
        .options(selectinload(InterviewSession.messages))
        .where(InterviewSession.id == session_id)
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise ValueError(f"Session {session_id} not found")

    if session.status != "active":
        raise ValueError(f"Session {session_id} is not active")

    # Save participant message
    participant_msg = InterviewMessage(
        session_id=session_id,
        role="participant",
        content=message,
    )
    db.add(participant_msg)
    await db.flush()

    # Build conversation history
    chat_history = [
        {"role": "system", "content": MODERATOR_SYSTEM_PROMPT + f"\n\nInterview topic: {session.topic}"},
    ]
    for msg in session.messages:
        role = "assistant" if msg.role == "moderator" else "user"
        chat_history.append({"role": role, "content": msg.content})
    chat_history.append({"role": "user", "content": message})

    # Sliding window: keep last 20 messages + system prompt
    if len(chat_history) > 21:
        chat_history = [chat_history[0]] + chat_history[-20:]

    # Generate follow-up
    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model=settings.groq_fast_model,
        messages=chat_history,
        temperature=0.7,
        max_tokens=512,
    )

    followup_text = response.choices[0].message.content or ""
    clean_text, covered, remaining = _parse_topics(followup_text)

    # Save moderator response
    moderator_msg = InterviewMessage(
        session_id=session_id,
        role="moderator",
        content=clean_text,
    )
    db.add(moderator_msg)
    await db.flush()

    return ModeratorResponse(
        message=MessageResponse(
            id=moderator_msg.id,
            role=moderator_msg.role,
            content=moderator_msg.content,
            created_at=moderator_msg.created_at,
        ),
        suggested_topics=remaining,
        topics_covered=covered,
    )


async def end_session(
    db: AsyncSession,
    session_id: str,
) -> SessionResponse:
    """End a session and generate a summary."""
    settings = get_settings()

    stmt = (
        select(InterviewSession)
        .options(selectinload(InterviewSession.messages))
        .where(InterviewSession.id == session_id)
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise ValueError(f"Session {session_id} not found")

    # Build transcript for summary
    transcript_lines = []
    for msg in session.messages:
        role_label = "Moderator" if msg.role == "moderator" else "Participant"
        transcript_lines.append(f"{role_label}: {msg.content}")
    transcript = "\n\n".join(transcript_lines)

    # Generate summary
    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model=settings.groq_fast_model,
        messages=[
            {"role": "user", "content": SUMMARY_PROMPT.format(transcript=transcript)},
        ],
        temperature=0.3,
        max_tokens=1024,
    )

    session.summary = response.choices[0].message.content or ""
    session.status = "completed"
    await db.flush()

    # Automatically chunk and ingest the transcript into the database & ChromaDB
    from app.services.ingestion import ingest_text
    from app.services.retrieval import rebuild_bm25

    filename = f"interview_session_{session.id}.txt"
    metadata = {
        "session_id": session.id,
        "topic": session.topic,
        "source": "interview",
    }
    try:
        _, chunks = await ingest_text(db, transcript, filename, metadata)
        if chunks:
            rebuild_bm25()
        logger.info("interview_auto_ingestion_success", session_id=session.id, chunk_count=len(chunks))
    except Exception as e:
        logger.error("interview_auto_ingestion_failed", session_id=session.id, error=str(e))

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
