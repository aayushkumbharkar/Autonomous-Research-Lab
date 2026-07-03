"""
Evaluation API Router.

Endpoints for running evaluations, viewing scores, and comparing retry attempts.
Includes the "Failure Replay" feature — shows old vs new answers and why improvement happened.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.database import get_db
from app.models.evaluation import EvalRun, EvalScore, FeedbackAttempt
from app.models.research import ResearchQuery, ResearchAnswer
from app.schemas.evaluation import (
    EvalRequest,
    EvalRunResponse,
    EvalScoreResponse,
    FeedbackAttemptResponse,
    RetryComparisonResponse,
)
from app.services.evaluation import evaluate_answer

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.post("/evaluate", response_model=EvalRunResponse)
async def run_evaluation(
    request: EvalRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually evaluate an answer."""
    if get_settings().contract_test_mode:
        from datetime import datetime
        return EvalRunResponse(
            id="eval-001",
            answer_id=request.answer_id,
            composite_score=0.85,
            citation_coverage=0.9,
            retrieval_overlap=0.8,
            claim_support_ratio=0.85,
            scores=[
                EvalScoreResponse(
                    dimension="faithfulness",
                    score=0.9,
                    explanation="Answer closely follows source material",
                    is_deterministic=False,
                    )
            ],
            created_at=datetime.fromisoformat("2025-01-15T10:31:00+00:00"),
        )

    # Get the answer
    stmt = select(ResearchAnswer).where(ResearchAnswer.id == request.answer_id)
    result = await db.execute(stmt)
    answer = result.scalar_one_or_none()

    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    # Get the query
    stmt = select(ResearchQuery).where(ResearchQuery.id == answer.query_id)
    result = await db.execute(stmt)
    query = result.scalar_one_or_none()

    # Get citations to find chunks
    from app.models.research import Citation
    from app.models.transcript import Chunk

    stmt = select(Citation).where(Citation.answer_id == answer.id)
    result = await db.execute(stmt)
    citations = result.scalars().all()

    context_chunks = []
    for cit in citations:
        stmt = select(Chunk).where(Chunk.id == cit.chunk_id)
        result = await db.execute(stmt)
        chunk = result.scalar_one_or_none()
        if chunk:
            context_chunks.append(chunk.content)

    eval_run = await evaluate_answer(
        db, answer.id, answer.answer_text,
        context_chunks, query.query_text if query else "",
    )

    # Reload with scores
    stmt = (
        select(EvalRun)
        .options(selectinload(EvalRun.scores))
        .where(EvalRun.id == eval_run.id)
    )
    result = await db.execute(stmt)
    eval_run = result.scalar_one()

    return EvalRunResponse(
        id=eval_run.id,
        answer_id=eval_run.answer_id,
        composite_score=eval_run.composite_score,
        citation_coverage=eval_run.citation_coverage,
        retrieval_overlap=eval_run.retrieval_overlap,
        claim_support_ratio=eval_run.claim_support_ratio,
        scores=[EvalScoreResponse.model_validate(s) for s in eval_run.scores],
        created_at=eval_run.created_at,
    )


@router.get("/runs", response_model=list[EvalRunResponse])
async def list_eval_runs(db: AsyncSession = Depends(get_db)):
    """List all evaluation runs."""
    stmt = (
        select(EvalRun)
        .options(selectinload(EvalRun.scores))
        .order_by(EvalRun.created_at.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    runs = result.scalars().all()

    return [
        EvalRunResponse(
            id=r.id,
            answer_id=r.answer_id,
            composite_score=r.composite_score,
            citation_coverage=r.citation_coverage,
            retrieval_overlap=r.retrieval_overlap,
            claim_support_ratio=r.claim_support_ratio,
            scores=[EvalScoreResponse.model_validate(s) for s in r.scores],
            created_at=r.created_at,
        )
        for r in runs
    ]


@router.get("/runs/{eval_id}", response_model=EvalRunResponse)
async def get_eval_run(
    eval_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed evaluation results."""
    stmt = (
        select(EvalRun)
        .options(selectinload(EvalRun.scores))
        .where(EvalRun.id == eval_id)
    )
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")

    return EvalRunResponse(
        id=run.id,
        answer_id=run.answer_id,
        composite_score=run.composite_score,
        citation_coverage=run.citation_coverage,
        retrieval_overlap=run.retrieval_overlap,
        claim_support_ratio=run.claim_support_ratio,
        scores=[EvalScoreResponse.model_validate(s) for s in run.scores],
        created_at=run.created_at,
    )


@router.get("/retry-comparison/{query_id}", response_model=RetryComparisonResponse)
async def get_retry_comparison(
    query_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Failure Replay: compare all attempts for a query side-by-side.
    Shows old answer → new answer → why it improved.
    """
    # Get query
    stmt = (
        select(ResearchQuery)
        .options(selectinload(ResearchQuery.answers))
        .where(ResearchQuery.id == query_id)
    )
    result = await db.execute(stmt)
    query = result.scalar_one_or_none()

    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    # Get all feedback attempts
    stmt = (
        select(FeedbackAttempt)
        .where(FeedbackAttempt.query_id == query_id)
        .order_by(FeedbackAttempt.attempt_number)
    )
    result = await db.execute(stmt)
    feedback_attempts = result.scalars().all()

    # Build attempt data
    attempts = []
    for answer in sorted(query.answers, key=lambda a: a.attempt_number):
        # Find matching eval run
        stmt = (
            select(EvalRun)
            .options(selectinload(EvalRun.scores))
            .where(EvalRun.answer_id == answer.id)
        )
        result = await db.execute(stmt)
        eval_run = result.scalar_one_or_none()

        # Find matching feedback attempt
        fb = next(
            (f for f in feedback_attempts if f.attempt_number == answer.attempt_number),
            None,
        )

        attempt_data = {
            "answer_id": answer.id,
            "attempt_number": answer.attempt_number,
            "answer_text": answer.answer_text,
            "confidence": answer.confidence,
            "risk_level": answer.risk_level,
            "scores": {},
            "modification_type": fb.modification_type if fb else "initial",
            "improvement": fb.improvement if fb else 0.0,
        }

        if eval_run:
            attempt_data["scores"] = {
                "composite": eval_run.composite_score,
                "citation_coverage": eval_run.citation_coverage,
                "retrieval_overlap": eval_run.retrieval_overlap,
                "claim_support_ratio": eval_run.claim_support_ratio,
                **{s.dimension: s.score for s in eval_run.scores},
            }

        attempts.append(attempt_data)

    # Find best attempt
    best_attempt = max(
        attempts,
        key=lambda a: a["scores"].get("composite", 0.0),
        default={"attempt_number": 1},
    )

    total_improvement = 0.0
    if len(attempts) >= 2:
        first_score = attempts[0]["scores"].get("composite", 0.0)
        best_score = best_attempt["scores"].get("composite", 0.0)
        total_improvement = best_score - first_score

    return RetryComparisonResponse(
        query_id=query_id,
        query_text=query.query_text,
        attempts=attempts,
        best_attempt=best_attempt["attempt_number"],
        total_improvement=round(total_improvement, 3),
    )


@router.delete("/runs/{eval_id}")
async def delete_eval_run(
    eval_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete an evaluation run."""
    stmt = select(EvalRun).where(EvalRun.id == eval_id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")

    await db.delete(run)
    await db.commit()
    return {"status": "success", "message": f"Evaluation run {eval_id} deleted"}

