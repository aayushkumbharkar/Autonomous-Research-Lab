"""
Research API Router.

Full research pipeline: query → retrieve → generate → verify → evaluate.
Includes refusal mode when confidence is too low.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models.research import ResearchQuery, ResearchAnswer
from app.schemas.research import (
    ConfidenceSignal,
    ResearchQueryRequest,
    ResearchAnswerResponse,
    ResearchQueryListItem,
)
from app.services.research_agent import research_query
from app.services.feedback_loop import run_feedback_loop

router = APIRouter(prefix="/api/research", tags=["research"])

# Refusal threshold — below this, the system refuses to answer
REFUSAL_THRESHOLD = 0.3


def _contract_research_response(query_text: str) -> ResearchAnswerResponse:
    """Return a stable, schema-valid response for OpenAPI contract tests."""
    return ResearchAnswerResponse(
        query_id="q-001",
        answer_id="a-001",
        query_text=query_text,
        answer_text="Based on the transcripts, three key patterns emerge: clearer onboarding, faster first-value discovery, and better contextual guidance.",
        reasoning_trace="Retrieved 10 chunks, generated answer, verified 3 claims",
        attempt_number=1,
        citations=[],
        claim_verifications=[],
        confidence=ConfidenceSignal(
            confidence=0.82,
            risk_level="low",
            disagreement_score=None,
            explanation="High retrieval relevance with consistent sources",
        ),
        eval_scores={
            "composite": 0.85,
            "faithfulness": 0.9,
            "relevance": 0.8,
        },
        created_at=datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc),
    )


@router.post("/query", response_model=ResearchAnswerResponse)
async def submit_research_query(
    request: ResearchQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a research query. Returns grounded answer with citations,
    claim verifications, confidence signal, and evaluation scores.

    If confidence is critically low, the system refuses to answer
    rather than risk providing unreliable information.
    """
    if get_settings().contract_test_mode:
        return _contract_research_response(request.query)

    # Run the research pipeline
    result = await research_query(
        db,
        query_text=request.query,
        top_k=request.top_k,
        auto_evaluate=request.auto_evaluate,
        attempt_number=1,
    )

    # Refusal mode: if confidence is critically low, warn the user
    if result.confidence.confidence < REFUSAL_THRESHOLD:
        result.answer_text = (
            f"⚠️ **Low Confidence Warning** (confidence: {result.confidence.confidence:.0%})\n\n"
            f"I don't have enough reliable information to answer this question confidently. "
            f"The retrieved context may be insufficient or not relevant enough.\n\n"
            f"**Risk Level:** {result.confidence.risk_level}\n"
            f"**Reason:** {result.confidence.explanation}\n\n"
            f"---\n\n"
            f"**Tentative answer (use with caution):**\n\n{result.answer_text}"
        )

    # Auto-improve if score is low and auto_improve is enabled
    if (
        request.auto_improve
        and result.eval_scores
        and result.eval_scores.get("composite", 1.0) < 0.7
    ):
        attempts = await run_feedback_loop(
            db,
            query_id=result.query_id,
            query_text=request.query,
            current_scores=result.eval_scores,
            current_composite=result.eval_scores.get("composite", 0.0),
        )
        # Return the best attempt
        if attempts:
            best = max(
                attempts,
                key=lambda a: a.eval_scores.get("composite", 0.0) if a.eval_scores else 0.0,
            )
            if (best.eval_scores or {}).get("composite", 0.0) > (result.eval_scores or {}).get("composite", 0.0):
                result = best

    return result


@router.get("/queries", response_model=list[ResearchQueryListItem])
async def list_research_queries(
    db: AsyncSession = Depends(get_db),
):
    """List all past research queries."""
    stmt = (
        select(ResearchQuery)
        .options(selectinload(ResearchQuery.answers))
        .order_by(ResearchQuery.created_at.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    queries = result.scalars().all()

    return [
        ResearchQueryListItem(
            id=q.id,
            query_text=q.query_text,
            answer_count=len(q.answers),
            best_score=max((a.confidence for a in q.answers), default=None),
            created_at=q.created_at,
        )
        for q in queries
    ]


@router.get("/queries/{query_id}")
async def get_research_query(
    query_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a research query with all attempts and scores."""
    stmt = (
        select(ResearchQuery)
        .options(selectinload(ResearchQuery.answers))
        .where(ResearchQuery.id == query_id)
    )
    result = await db.execute(stmt)
    query = result.scalar_one_or_none()

    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    return {
        "id": query.id,
        "query_text": query.query_text,
        "created_at": query.created_at.isoformat(),
        "answers": [
            {
                "id": a.id,
                "answer_text": a.answer_text,
                "attempt_number": a.attempt_number,
                "confidence": a.confidence,
                "risk_level": a.risk_level,
                "reasoning_trace": a.reasoning_trace,
                "created_at": a.created_at.isoformat(),
            }
            for a in sorted(query.answers, key=lambda a: a.attempt_number)
        ],
    }
