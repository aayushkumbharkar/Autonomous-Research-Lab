"""
Feedback Loop.

When evaluation scores fall below threshold, automatically retry
with modifications to improve quality. Uses failure memory to
apply learned fixes first, then falls back to a fixed escalation strategy.

Logs all attempts with before/after scores for analysis.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.evaluation import FeedbackAttempt
from app.services.research_agent import research_query
from app.services.failure_memory import find_best_fix, record_fix, _classify_failure
from app.schemas.research import ResearchAnswerResponse
from app.utils.logging import get_logger

logger = get_logger(__name__)


# Escalation strategies: tried in order if failure memory has no match
RETRY_STRATEGIES = [
    {
        "type": "prompt_rewrite",
        "description": "Rephrase query for clarity and specificity",
        "top_k_multiplier": 1.0,
        "semantic_weight": None,
        "keyword_weight": None,
    },
    {
        "type": "retrieval_expand",
        "description": "Increase top-k to provide more context",
        "top_k_multiplier": 2.0,
        "semantic_weight": None,
        "keyword_weight": None,
    },
    {
        "type": "retrieval_filter",
        "description": "Adjust retrieval weights toward keyword matching",
        "top_k_multiplier": 1.5,
        "semantic_weight": 0.4,
        "keyword_weight": 0.6,
    },
]


def _rewrite_query(query: str, failure_type: str) -> str:
    """
    Rewrite a query to address the specific failure type.
    """
    if "coverage" in failure_type:
        return f"Provide a comprehensive and thorough answer to: {query}"
    elif "specificity" in failure_type:
        return f"With specific details, examples, and data points, answer: {query}"
    elif "faithfulness" in failure_type:
        return f"Using only the provided context, carefully answer: {query}"
    elif "retrieval" in failure_type:
        # Try to make query more searchable
        return query  # Keep original — retrieval weights will change
    else:
        return f"Please answer thoroughly and specifically: {query}"


async def run_feedback_loop(
    db: AsyncSession,
    query_id: str,
    query_text: str,
    current_scores: dict,
    current_composite: float,
) -> list[ResearchAnswerResponse]:
    """
    Run the feedback loop to improve answer quality.

    1. Check failure memory for learned fixes
    2. Apply the fix (or escalate through strategies)
    3. Re-evaluate
    4. Record what worked (or didn't) in failure memory

    Args:
        db: Database session
        query_id: The research query ID
        query_text: Original query text
        current_scores: Current evaluation scores by dimension
        current_composite: Current composite score

    Returns:
        List of all retry attempts (ResearchAnswerResponse)
    """
    settings = get_settings()
    max_attempts = settings.max_retry_attempts
    threshold = settings.eval_threshold

    attempts: list[ResearchAnswerResponse] = []
    best_score = current_composite
    failure_type = _classify_failure(current_scores)

    logger.info("feedback_loop_start",
                query_id=query_id[:8],
                current_score=current_composite,
                failure_type=failure_type,
                threshold=threshold)

    # Check failure memory first
    memory_fix = await find_best_fix(db, query_text, current_scores)

    strategies_to_try = []
    if memory_fix:
        # Use learned fix first
        strategies_to_try.append({
            "type": f"from_memory:{memory_fix['best_fix']}",
            "description": f"Learned fix from failure memory (used {memory_fix['success_count']}× before)",
            "top_k_multiplier": memory_fix.get("fix_details", {}).get("top_k_multiplier", 1.5),
            "semantic_weight": memory_fix.get("fix_details", {}).get("semantic_weight"),
            "keyword_weight": memory_fix.get("fix_details", {}).get("keyword_weight"),
        })

    # Add standard strategies
    strategies_to_try.extend(RETRY_STRATEGIES)

    for attempt_num, strategy in enumerate(strategies_to_try[:max_attempts], start=2):
        logger.info("feedback_attempt",
                     attempt=attempt_num,
                     strategy=strategy["type"])

        # Apply strategy
        modified_query = query_text
        if "prompt_rewrite" in strategy["type"]:
            modified_query = _rewrite_query(query_text, failure_type)

        top_k = int(settings.default_top_k * strategy.get("top_k_multiplier", 1.0))

        # Run research with modifications
        try:
            result = await research_query(
                db,
                modified_query,
                top_k=top_k,
                auto_evaluate=True,
                attempt_number=attempt_num,
                existing_query_id=query_id,
            )
            attempts.append(result)

            new_score = result.eval_scores.get("composite", 0.0) if result.eval_scores else 0.0
            improvement = new_score - current_composite

            # Log attempt
            feedback = FeedbackAttempt(
                query_id=query_id,
                attempt_number=attempt_num,
                modification_type=strategy["type"],
                previous_score=best_score,
                new_score=new_score,
                improvement=improvement,
                details={
                    "strategy": strategy,
                    "modified_query": modified_query if modified_query != query_text else None,
                    "top_k": top_k,
                },
            )
            db.add(feedback)

            # Record in failure memory if improvement is positive
            if improvement > 0.05:
                fix_type = strategy["type"].split(":")[-1] if "from_memory" in strategy["type"] else strategy["type"]
                await record_fix(
                    db, query_text, failure_type, fix_type,
                    improvement,
                    fix_details={
                        "top_k_multiplier": strategy.get("top_k_multiplier", 1.0),
                        "semantic_weight": strategy.get("semantic_weight"),
                        "keyword_weight": strategy.get("keyword_weight"),
                    },
                )

            if new_score > best_score:
                best_score = new_score

            # Stop if we've reached threshold
            if new_score >= threshold:
                logger.info("feedback_loop_success",
                            attempt=attempt_num,
                            final_score=new_score)
                break

        except Exception as e:
            logger.error("feedback_attempt_failed",
                         attempt=attempt_num,
                         error=str(e))
            continue

    await db.flush()

    logger.info("feedback_loop_complete",
                total_attempts=len(attempts),
                best_score=best_score,
                improved=best_score > current_composite)

    return attempts
