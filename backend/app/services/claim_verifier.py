"""
Claim Verification Service.

Extracts atomic claims from an answer, then verifies each claim
against the source chunks. This is the truth alignment enforcement layer.

A claim is "supported" if there is sufficient token/semantic overlap
with at least one source chunk. Unsupported claims are flagged and
can be stripped from the final answer.
"""

import re
from dataclasses import dataclass
from typing import Optional

from app.services.embeddings import embed_texts
from app.utils.logging import get_logger
import numpy as np

logger = get_logger(__name__)


@dataclass
class VerifiedClaim:
    """Result of verifying a single claim."""
    claim: str
    status: str  # "supported" | "partially_supported" | "unsupported"
    supporting_chunk_ids: list[str]
    best_overlap_score: float
    explanation: str


def _extract_claims(text: str) -> list[str]:
    """
    Extract atomic claims from an answer text.

    Strategy: split into sentences, filter out meta-sentences
    (e.g., "Based on the context...", "I don't know").
    """
    # Remove citation markers for claim extraction
    clean_text = re.sub(r'\[\d+\]', '', text)

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', clean_text)

    claims = []
    skip_patterns = [
        r'^(based on|according to|the (context|data|information))',
        r'^(i don\'t know|insufficient|cannot determine)',
        r'^(in summary|to summarize|overall)',
        r'^(note:|disclaimer:)',
    ]

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 15:
            continue

        # Skip meta-sentences
        is_meta = any(re.match(pat, sentence, re.IGNORECASE) for pat in skip_patterns)
        if is_meta:
            continue

        claims.append(sentence)

    return claims


def _compute_token_overlap(claim: str, chunk: str) -> float:
    """
    Compute token-level overlap between a claim and a chunk.
    Returns ratio of claim tokens found in chunk.
    """
    claim_tokens = set(re.findall(r'\b[a-z0-9]+\b', claim.lower()))
    chunk_tokens = set(re.findall(r'\b[a-z0-9]+\b', chunk.lower()))

    if not claim_tokens:
        return 0.0

    # Remove common stop words to focus on content tokens
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for',
        'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'and', 'but', 'or',
        'not', 'no', 'this', 'that', 'these', 'those', 'it', 'its', 'they',
        'their', 'them', 'he', 'she', 'his', 'her', 'we', 'our', 'you', 'your',
    }

    claim_content = claim_tokens - stop_words
    chunk_content = chunk_tokens - stop_words

    if not claim_content:
        return 0.5  # All stop words = can't determine

    overlap = claim_content & chunk_content
    return len(overlap) / len(claim_content)


def verify_claims(
    answer_text: str,
    context_chunks: list[dict],
    support_threshold: float = 0.4,
    partial_threshold: float = 0.2,
) -> tuple[list[VerifiedClaim], float]:
    """
    Verify all claims in an answer against source chunks.

    Uses a two-stage approach:
    1. Token overlap (fast, deterministic)
    2. Semantic similarity (for borderline cases)

    Args:
        answer_text: The generated answer
        context_chunks: List of {"id": str, "content": str} source chunks
        support_threshold: Min overlap for "supported" (default 0.4 = 40% content tokens)
        partial_threshold: Min overlap for "partially_supported"

    Returns:
        Tuple of (verified_claims, claim_support_ratio)
    """
    claims = _extract_claims(answer_text)
    if not claims:
        return [], 1.0  # No claims to verify

    if not context_chunks:
        # No context — all claims are unsupported
        unsupported = [
            VerifiedClaim(
                claim=c,
                status="unsupported",
                supporting_chunk_ids=[],
                best_overlap_score=0.0,
                explanation="No source chunks available for verification",
            )
            for c in claims
        ]
        return unsupported, 0.0

    # Stage 1: Token overlap
    verified = []
    for claim in claims:
        best_score = 0.0
        supporting_ids = []

        for chunk in context_chunks:
            overlap = _compute_token_overlap(claim, chunk["content"])
            if overlap > best_score:
                best_score = overlap

            if overlap >= partial_threshold:
                supporting_ids.append(chunk["id"])

        # Determine status
        if best_score >= support_threshold:
            status = "supported"
            explanation = f"Token overlap {best_score:.0%} with {len(supporting_ids)} chunk(s)"
        elif best_score >= partial_threshold:
            status = "partially_supported"
            explanation = f"Partial token overlap {best_score:.0%} — claim may be an inference"
        else:
            status = "unsupported"
            explanation = f"Low token overlap {best_score:.0%} — claim not grounded in sources"

        verified.append(VerifiedClaim(
            claim=claim,
            status=status,
            supporting_chunk_ids=supporting_ids[:3],  # Limit to top 3
            best_overlap_score=best_score,
            explanation=explanation,
        ))

    # Stage 2: Semantic similarity for unsupported claims (gives them a second chance)
    unsupported_claims = [v for v in verified if v.status == "unsupported"]
    if unsupported_claims and len(unsupported_claims) <= 20:
        try:
            claim_texts = [v.claim for v in unsupported_claims]
            chunk_texts = [c["content"] for c in context_chunks]

            claim_embeddings = embed_texts(claim_texts)
            chunk_embeddings = embed_texts(chunk_texts)

            # Cosine similarity matrix
            similarities = np.dot(claim_embeddings, chunk_embeddings.T)

            for i, vc in enumerate(unsupported_claims):
                max_sim = float(np.max(similarities[i]))
                if max_sim >= 0.6:  # Semantic similarity threshold
                    vc.status = "partially_supported"
                    best_chunk_idx = int(np.argmax(similarities[i]))
                    vc.supporting_chunk_ids = [context_chunks[best_chunk_idx]["id"]]
                    vc.best_overlap_score = max_sim
                    vc.explanation = (
                        f"Semantically similar ({max_sim:.0%}) to source "
                        f"but low lexical overlap — may be a paraphrase"
                    )
        except Exception as e:
            logger.warning("semantic_verification_failed", error=str(e))

    # Calculate claim support ratio
    supported_count = sum(
        1 for v in verified if v.status in ("supported", "partially_supported")
    )
    claim_support_ratio = supported_count / len(verified) if verified else 1.0

    logger.info("claims_verified",
                total=len(verified),
                supported=sum(1 for v in verified if v.status == "supported"),
                partial=sum(1 for v in verified if v.status == "partially_supported"),
                unsupported=sum(1 for v in verified if v.status == "unsupported"),
                ratio=round(claim_support_ratio, 3))

    return verified, claim_support_ratio
