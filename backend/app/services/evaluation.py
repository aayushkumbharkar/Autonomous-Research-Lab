"""
Evaluation Engine.

Hybrid evaluation combining:
1. Deterministic signals (citation coverage, retrieval overlap, claim support)
2. LLM-as-judge signals (faithfulness, coverage, specificity, retrieval quality)

The composite score is a weighted blend of both signal types,
making evaluation more robust than LLM-only approaches.
"""

import asyncio
import re
import json
import os
from typing import Optional

from groq import Groq
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.evaluation import EvalRun, EvalScore
from app.utils.logging import get_logger

logger = get_logger(__name__)


# ─── Deterministic Scoring Functions ───────────────────────────────────────

def _citation_coverage(answer_text: str) -> tuple[float, str]:
    """
    Compute what % of sentences in the answer have a citation marker [N].

    Returns (score, explanation).
    """
    sentences = re.split(r'(?<=[.!?])\s+', answer_text.strip())
    sentences = [s for s in sentences if len(s.strip()) > 10]

    if not sentences:
        return 0.0, "No sentences found in answer"

    cited = sum(1 for s in sentences if re.search(r'\[\d+\]', s))
    ratio = cited / len(sentences)

    return round(ratio, 3), f"{cited}/{len(sentences)} sentences have citations"


def _retrieval_overlap(answer_text: str, context_chunks: list[str]) -> tuple[float, str]:
    """
    Compute token overlap: what fraction of answer content tokens
    appear in the retrieved chunks.

    This is a fast, deterministic proxy for faithfulness.
    """
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
        'on', 'with', 'at', 'by', 'from', 'as', 'and', 'but', 'or', 'not',
        'this', 'that', 'it', 'its', 'they', 'their', 'them', 'we', 'you',
    }

    # Remove citation markers from answer
    clean_answer = re.sub(r'\[\d+\]', '', answer_text)
    answer_tokens = set(re.findall(r'\b[a-z0-9]+\b', clean_answer.lower())) - stop_words

    if not answer_tokens:
        return 0.0, "No content tokens in answer"

    context_text = " ".join(context_chunks)
    context_tokens = set(re.findall(r'\b[a-z0-9]+\b', context_text.lower())) - stop_words

    overlap = answer_tokens & context_tokens
    ratio = len(overlap) / len(answer_tokens)
    return round(ratio, 3), f"{len(overlap)}/{len(answer_tokens)} answer tokens found in context"


# ─── LLM-as-Judge Scoring ─────────────────────────────────────────────────

_UNIFIED_EVAL_PROMPT_TEMPLATE = """You are a strict evaluator for AI-generated research answers.

Evaluate the answer on the following four dimensions using the specified rubrics:

1. FAITHFULNESS
Every factual claim in the answer must be directly supported by the provided context chunks.
- 1.0: Every claim is directly stated in or clearly inferable from the context.
- 0.7: Most claims are supported, minor inferences are reasonable.
- 0.4: Some claims lack support, or answer includes information not in context.
- 0.1: Answer contains significant unsupported claims or contradicts context.
- 0.0: Answer is entirely fabricated or unrelated to context.

2. COVERAGE
The answer should address all aspects of the query using the available context.
- 1.0: All aspects of the query are thoroughly addressed.
- 0.7: Most aspects addressed, minor gaps.
- 0.4: Key aspects missing or superficially addressed.
- 0.1: Answer barely addresses the query.
- 0.0: Answer does not address the query at all.

3. SPECIFICITY
The answer should contain specific details, not vague generalities.
- 1.0: Rich in specific details, data points, names, or examples from context.
- 0.7: Good specificity with some concrete details.
- 0.4: Mix of specific and vague statements.
- 0.1: Mostly vague or generic statements.
- 0.0: Entirely vague with no concrete details.

4. RETRIEVAL QUALITY
The retrieved context chunks should be relevant to the query.
- 1.0: All chunks are highly relevant to the query.
- 0.7: Most chunks are relevant, some tangential.
- 0.4: Mixed relevance, significant noise.
- 0.1: Mostly irrelevant chunks.
- 0.0: Context chunks are entirely unrelated to query.

CONTEXT CHUNKS:
{context}

QUERY: {query}

ANSWER: {answer}

Respond ONLY with a valid JSON object formatted exactly as follows:
{{
  "faithfulness": {{"score": <float 0.0 to 1.0>, "explanation": "<specific evidence-based explanation>"}},
  "coverage": {{"score": <float 0.0 to 1.0>, "explanation": "<specific evidence-based explanation>"}},
  "specificity": {{"score": <float 0.0 to 1.0>, "explanation": "<specific evidence-based explanation>"}},
  "retrieval_quality": {{"score": <float 0.0 to 1.0>, "explanation": "<specific evidence-based explanation>"}}
}}"""


async def _run_unified_llm_eval(
    answer: str,
    context: str,
    query: str,
) -> dict[str, tuple[float, str]]:
    """
    Evaluate all 4 dimensions in a single LLM call.
    Returns a dict mapping dimension name to (score, explanation).
    """
    if os.environ.get("MOCK_LLM") == "true":
        return {
            "faithfulness": (1.0, "Mocked faithfulness"),
            "coverage": (1.0, "Mocked coverage"),
            "specificity": (1.0, "Mocked specificity"),
            "retrieval_quality": (1.0, "Mocked retrieval quality"),
        }

    settings = get_settings()
    client = Groq(api_key=settings.groq_api_key)

    prompt = _UNIFIED_EVAL_PROMPT_TEMPLATE.format(
        context=context[:4000],  # Truncate to avoid token limits
        query=query,
        answer=answer,
    )

    default_results = {
        "faithfulness": (0.5, "LLM evaluation failed or timed out"),
        "coverage": (0.5, "LLM evaluation failed or timed out"),
        "specificity": (0.5, "LLM evaluation failed or timed out"),
        "retrieval_quality": (0.5, "LLM evaluation failed or timed out"),
    }

    try:
        client = Groq(
            api_key=settings.groq_api_key,
            timeout=settings.request_timeout,
        )
        messages = [{"role": "user", "content": prompt}]
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=settings.groq_fast_model,
                messages=messages,
                temperature=0.1,  # Low temperature for consistent scoring
                max_tokens=1000,
            ),
        )

        content = response.choices[0].message.content or ""

        # Parse JSON response
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            results = {}
            for dim in ["faithfulness", "coverage", "specificity", "retrieval_quality"]:
                dim_data = data.get(dim, {})
                # Safely parse scores
                try:
                    score = max(0.0, min(1.0, float(dim_data.get("score", 0.5))))
                except (ValueError, TypeError):
                    score = 0.5
                explanation = dim_data.get("explanation", "No explanation provided")
                results[dim] = (score, explanation)
            return results

        logger.warning("unified_eval_parse_failed", content=content[:100])
        return default_results

    except Exception as e:
        logger.error("unified_eval_failed", error=str(e))
        return default_results


# ─── Main Evaluation Function ─────────────────────────────────────────────

async def evaluate_answer(
    db: AsyncSession,
    answer_id: str,
    answer_text: str,
    context_chunks: list[str],
    query: str,
    claim_support_ratio: float = 1.0,
) -> EvalRun:
    """
    Run full hybrid evaluation on an answer.

    Combines deterministic signals with LLM-as-judge scores.

    Args:
        db: Database session
        answer_id: ID of the answer being evaluated
        answer_text: The answer text
        context_chunks: Source chunk texts
        query: The original query
        claim_support_ratio: From claim verifier

    Returns:
        EvalRun with all scores
    """
    logger.info("evaluating_answer", answer_id=answer_id[:8])

    # 1. Deterministic signals
    cit_coverage, cit_explanation = _citation_coverage(answer_text)
    ret_overlap, ret_explanation = _retrieval_overlap(answer_text, context_chunks)

    # 2. LLM-as-judge signals (run all 4 dimensions in a single call)
    context_str = "\n\n---\n\n".join(context_chunks)
    eval_results = await _run_unified_llm_eval(answer_text, context_str, query)

    faith_score, faith_expl = eval_results["faithfulness"]
    cover_score, cover_expl = eval_results["coverage"]
    spec_score, spec_expl = eval_results["specificity"]
    retq_score, retq_expl = eval_results["retrieval_quality"]

    # 3. Apply claim verification penalty to faithfulness
    # If claims are unsupported, HARD penalize faithfulness
    adjusted_faithfulness = faith_score * claim_support_ratio
    if claim_support_ratio < 0.7:
        faith_expl += f" [PENALIZED: claim support ratio {claim_support_ratio:.0%}]"

    # 4. Composite score: blend of deterministic + LLM signals
    # Weights: faithfulness(0.3) + coverage(0.2) + specificity(0.15) +
    #          retrieval_quality(0.15) + citation_coverage(0.1) + retrieval_overlap(0.1)
    composite = (
        adjusted_faithfulness * 0.30
        + cover_score * 0.20
        + spec_score * 0.15
        + retq_score * 0.15
        + cit_coverage * 0.10
        + ret_overlap * 0.10
    )

    # Create EvalRun
    eval_run = EvalRun(
        answer_id=answer_id,
        composite_score=round(composite, 3),
        citation_coverage=cit_coverage,
        retrieval_overlap=ret_overlap,
        claim_support_ratio=claim_support_ratio,
    )
    db.add(eval_run)
    await db.flush()

    # Create EvalScores
    scores_data = [
        ("faithfulness", adjusted_faithfulness, faith_expl, False),
        ("coverage", cover_score, cover_expl, False),
        ("specificity", spec_score, spec_expl, False),
        ("retrieval_quality", retq_score, retq_expl, False),
        ("citation_coverage", cit_coverage, cit_explanation, True),
        ("retrieval_overlap", ret_overlap, ret_explanation, True),
        ("claim_support_ratio", claim_support_ratio,
         f"Ratio of verified claims: {claim_support_ratio:.0%}", True),
    ]

    for dimension, score, explanation, is_det in scores_data:
        eval_score = EvalScore(
            eval_run_id=eval_run.id,
            dimension=dimension,
            score=round(score, 3),
            explanation=explanation,
            is_deterministic=is_det,
        )
        db.add(eval_score)

    await db.flush()

    logger.info("evaluation_complete",
                answer_id=answer_id[:8],
                composite=round(composite, 3),
                faithfulness=round(adjusted_faithfulness, 3),
                coverage=round(cover_score, 3))

    return eval_run
