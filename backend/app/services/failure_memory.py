"""
Failure Memory System.

Stores and retrieves learned fix strategies across sessions.
When a retry strategy succeeds, we record what worked so future
queries with similar failure types skip to the best fix first.

This makes the feedback loop smarter over time — not just fixed-sequence retries.
"""

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evaluation import FailurePattern
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _classify_failure(scores: dict) -> str:
    """
    Determine the primary failure type from dimension scores.

    Returns the dimension with the lowest score.
    """
    primary_dims = {
        "faithfulness": scores.get("faithfulness", 1.0),
        "coverage": scores.get("coverage", 1.0),
        "specificity": scores.get("specificity", 1.0),
        "retrieval_quality": scores.get("retrieval_quality", 1.0),
    }

    worst_dim = min(primary_dims, key=primary_dims.get)
    return f"low_{worst_dim}"


def _generalize_query(query: str) -> str:
    """
    Generalize a query to a pattern for matching.

    Simple approach: extract question type and key topics.
    """
    query_lower = query.lower().strip()

    # Classify query type
    if query_lower.startswith(("what ", "what's ")):
        qtype = "what"
    elif query_lower.startswith(("how ", "how's ")):
        qtype = "how"
    elif query_lower.startswith(("why ")):
        qtype = "why"
    elif query_lower.startswith(("who ")):
        qtype = "who"
    elif query_lower.startswith(("when ")):
        qtype = "when"
    elif query_lower.startswith(("compare", "contrast", "difference")):
        qtype = "comparison"
    elif query_lower.startswith(("summarize", "summary")):
        qtype = "summary"
    else:
        qtype = "general"

    # Length classification
    if len(query.split()) <= 5:
        complexity = "simple"
    elif len(query.split()) <= 15:
        complexity = "moderate"
    else:
        complexity = "complex"

    return f"{qtype}:{complexity}"


async def find_best_fix(
    db: AsyncSession,
    query: str,
    scores: dict,
) -> Optional[dict]:
    """
    Look up failure memory for a matching pattern.

    Args:
        db: Database session
        query: The current query
        scores: Current evaluation scores

    Returns:
        Dict with best_fix and details, or None if no match
    """
    failure_type = _classify_failure(scores)
    query_pattern = _generalize_query(query)

    # Look for matching patterns
    stmt = (
        select(FailurePattern)
        .where(
            FailurePattern.failure_type == failure_type,
        )
        .order_by(FailurePattern.success_count.desc(), FailurePattern.avg_improvement.desc())
        .limit(1)
    )

    result = await db.execute(stmt)
    pattern = result.scalar_one_or_none()

    if pattern and pattern.success_count >= 1:
        logger.info("failure_memory_hit",
                     failure_type=failure_type,
                     best_fix=pattern.best_fix,
                     success_count=pattern.success_count)
        return {
            "best_fix": pattern.best_fix,
            "fix_details": pattern.fix_details,
            "success_count": pattern.success_count,
            "avg_improvement": pattern.avg_improvement,
            "source": "failure_memory",
        }

    logger.info("failure_memory_miss", failure_type=failure_type, query_pattern=query_pattern)
    return None


async def record_fix(
    db: AsyncSession,
    query: str,
    failure_type: str,
    fix_type: str,
    improvement: float,
    fix_details: Optional[dict] = None,
):
    """
    Record a successful fix in failure memory.

    If a pattern already exists for this failure type + fix, update it.
    Otherwise, create a new pattern.
    """
    query_pattern = _generalize_query(query)

    # Check for existing pattern
    stmt = (
        select(FailurePattern)
        .where(
            FailurePattern.failure_type == failure_type,
            FailurePattern.best_fix == fix_type,
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.success_count += 1
        existing.avg_improvement = (
            (existing.avg_improvement * (existing.success_count - 1) + improvement)
            / existing.success_count
        )
        if fix_details:
            existing.fix_details = fix_details
        logger.info("failure_pattern_updated",
                     failure_type=failure_type,
                     fix=fix_type,
                     count=existing.success_count)
    else:
        pattern = FailurePattern(
            query_pattern=query_pattern,
            failure_type=failure_type,
            best_fix=fix_type,
            fix_details=fix_details,
            success_count=1,
            avg_improvement=improvement,
        )
        db.add(pattern)
        logger.info("failure_pattern_created",
                     failure_type=failure_type,
                     fix=fix_type)

    await db.flush()
