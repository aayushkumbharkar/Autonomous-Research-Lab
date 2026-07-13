"""
Confidence & Uncertainty Service.

Implements dual-run disagreement detection:
- Generate 2 answers with different temperatures
- Compute agreement/disagreement score
- Expose confidence level and risk rating

This gives users a real signal about output reliability,
beyond just evaluation scores.
"""

import asyncio
import re
import os
from groq import Groq

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _tokenize(text: str) -> set[str]:
    """Extract content tokens from text."""
    return set(re.findall(r'\b[a-z0-9]+\b', text.lower()))


def compute_agreement_score(answer1: str, answer2: str) -> float:
    """
    Compute agreement between two answer texts.

    Uses Jaccard similarity on content tokens.
    Higher score = more agreement = higher confidence.
    """
    tokens1 = _tokenize(answer1)
    tokens2 = _tokenize(answer2)

    if not tokens1 or not tokens2:
        return 0.0

    intersection = tokens1 & tokens2
    union = tokens1 | tokens2

    return len(intersection) / len(union) if union else 0.0


def compute_confidence(
    answer_text: str,
    context_chunks: list[dict],
    eval_composite_score: float,
    claim_support_ratio: float,
    disagreement_score: float | None = None,
) -> dict:
    """
    Compute confidence signal from multiple sources.

    Args:
        answer_text: The generated answer
        context_chunks: Source chunks
        eval_composite_score: Composite evaluation score
        claim_support_ratio: From claim verification
        disagreement_score: If dual-run was performed (0 = full agreement, 1 = full disagreement)

    Returns:
        Dict with confidence, risk_level, explanation
    """
    signals = []

    # Signal 1: Evaluation score
    signals.append(("eval_score", eval_composite_score, 0.3))

    # Signal 2: Claim support ratio
    signals.append(("claim_support", claim_support_ratio, 0.35))

    # Signal 3: Context coverage (do we have enough context?)
    if context_chunks:
        total_context_len = sum(len(c["content"]) for c in context_chunks)
        # Heuristic: more context = more confidence, up to a point
        context_signal = min(total_context_len / 2000.0, 1.0)
    else:
        context_signal = 0.0
    signals.append(("context_coverage", context_signal, 0.15))

    # Signal 4: Disagreement (if available)
    if disagreement_score is not None:
        agreement = 1.0 - disagreement_score
        signals.append(("agreement", agreement, 0.2))
    else:
        # Redistribute weight
        total_weight = sum(w for _, _, w in signals)
        signals = [(n, s, w / total_weight) for n, s, w in signals]

    # Weighted confidence
    confidence = sum(score * weight for _, score, weight in signals)
    confidence = max(0.0, min(1.0, confidence))

    # Risk level
    if confidence >= 0.8:
        risk_level = "low"
    elif confidence >= 0.5:
        risk_level = "medium"
    else:
        risk_level = "high"

    # Explanation
    explanations = []
    for name, score, _ in signals:
        if score < 0.5:
            explanations.append(f"Low {name.replace('_', ' ')}: {score:.0%}")

    explanation = "; ".join(explanations) if explanations else "All signals healthy"

    result = {
        "confidence": round(confidence, 3),
        "risk_level": risk_level,
        "disagreement_score": disagreement_score,
        "explanation": explanation,
        "signals": {name: round(score, 3) for name, score, _ in signals},
    }

    logger.info("confidence_computed",
                confidence=result["confidence"],
                risk=risk_level)

    return result


async def generate_alternative_answer(
    query: str,
    context: str,
    system_prompt: str,
) -> str:
    """
    Generate a second answer with higher temperature for disagreement detection.
    """
    import os
    if os.environ.get("MOCK_LLM") == "true":
        return "Based on the available context, the participants expressed high satisfaction with the new dashboard's speed and layout [1]."

    settings = get_settings()
    client = Groq(
        api_key=settings.groq_api_key,
        timeout=settings.request_timeout,
    )

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuery: {query}"},
        ]
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=settings.groq_fast_model,
                messages=messages,
                temperature=0.8,  # Higher temperature for diversity
                max_tokens=2048,
            ),
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.warning("alternative_answer_failed", error=str(e))
        return ""
