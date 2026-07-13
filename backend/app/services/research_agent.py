"""
Research Agent.

The core intelligence module: accepts a query, retrieves context,
generates a grounded answer with citations, verifies claims,
computes confidence, and triggers evaluation + feedback loop.

Every output is fully traceable.
"""

import asyncio
import re
import uuid
import os
from typing import Optional

from groq import Groq
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.research import ResearchQuery, ResearchAnswer, Citation
from app.models.transcript import Chunk
from app.services.retrieval import hybrid_search
from app.services.claim_verifier import verify_claims
from app.services.confidence import (
    compute_confidence,
    compute_agreement_score,
    generate_alternative_answer,
)
from app.services.evaluation import evaluate_answer
from app.schemas.research import (
    ResearchAnswerResponse,
    ClaimVerification,
    CitationDetail,
    ConfidenceSignal,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = """You are a research assistant analyzing interview transcripts and documents.

CRITICAL RULES:
1. ONLY use information from the provided context chunks to answer.
2. If the context doesn't contain enough information, say "Based on the available context, I cannot fully answer this question" and explain what's missing.
3. CITE your sources using [1], [2], etc. corresponding to the chunk numbers provided.
4. Every factual claim MUST have at least one citation.
5. Be specific — use exact quotes, names, numbers, and details from the context.
6. Structure your reasoning clearly.

DO NOT make up information. DO NOT use prior knowledge. Only use the provided context."""


def _build_context_prompt(chunks: list[dict]) -> str:
    """Build numbered context from retrieval results."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        speaker = chunk.get("speaker", "")
        speaker_str = f" (Speaker: {speaker})" if speaker else ""
        parts.append(f"[{i}]{speaker_str}: {chunk['content']}")
    return "\n\n".join(parts)


def _extract_citation_indices(answer: str) -> list[int]:
    """Extract all citation indices [N] from the answer."""
    return [int(m) for m in re.findall(r'\[(\d+)\]', answer)]


async def research_query(
    db: AsyncSession,
    query_text: str,
    top_k: int = 10,
    auto_evaluate: bool = True,
    attempt_number: int = 1,
    existing_query_id: Optional[str] = None,
) -> ResearchAnswerResponse:
    """
    Full research pipeline: retrieve → generate → verify → evaluate.

    Args:
        db: Database session
        query_text: The research question
        top_k: Number of context chunks to retrieve
        auto_evaluate: Whether to run evaluation
        attempt_number: Which attempt this is (for feedback loop)
        existing_query_id: Reuse existing query (for retries)

    Returns:
        ResearchAnswerResponse with full observability data
    """
    settings = get_settings()
    logger.info("research_query_start", query=query_text[:80], attempt=attempt_number)

    # 1. Create or reuse query record
    if existing_query_id:
        query_id = existing_query_id
    else:
        query_record = ResearchQuery(query_text=query_text)
        db.add(query_record)
        await db.flush()
        query_id = query_record.id

    # 2. Retrieve context
    retrieval_results, search_metadata = hybrid_search(
        query_text, top_k=top_k,
        semantic_weight=settings.semantic_weight,
        keyword_weight=settings.keyword_weight,
    )

    context_chunks = [
        {
            "id": r.chunk_id,
            "content": r.content,
            "speaker": r.speaker,
            "score": r.score,
            "transcript_id": r.transcript_id,
            "chunk_index": r.chunk_index,
        }
        for r in retrieval_results
    ]

    # 3. Generate answer
    if not context_chunks:
        answer_text = "Based on the available context, I cannot fully answer this question because no relevant documents or transcripts were found in the database."
        context_prompt = ""
    else:
        context_prompt = _build_context_prompt(context_chunks)
        if os.environ.get("MOCK_LLM") == "true":
            answer_text = "Based on the available context, the participants expressed high satisfaction with the new dashboard's speed and layout [1]."
        else:
            try:
                client = Groq(
                    api_key=settings.groq_api_key,
                    timeout=settings.request_timeout,
                )
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Context Chunks:\n{context_prompt}\n\nResearch Question: {query_text}"},
                ]
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: client.chat.completions.create(
                        model=settings.groq_model,
                        messages=messages,
                        temperature=0.3,
                        max_tokens=4096,
                    ),
                )
                answer_text = response.choices[0].message.content or ""
            except Exception as e:
                logger.error("groq_generation_failed", error=str(e))
                answer_text = f"Based on the available context, I cannot fully answer this question because the LLM generation service is currently unavailable or misconfigured (error: {str(e)[:100]})."

    reasoning_trace = f"Retrieved {len(context_chunks)} chunks via hybrid search. " \
                      f"Search metadata: {search_metadata}"

    # 4. Verify claims
    verified_claims, claim_support_ratio = verify_claims(
        answer_text,
        [{"id": c["id"], "content": c["content"]} for c in context_chunks],
    )

    # 5. Extract and validate citations
    cited_indices = _extract_citation_indices(answer_text)
    citations = []
    for idx in sorted(set(cited_indices)):
        if 1 <= idx <= len(context_chunks):
            chunk = context_chunks[idx - 1]
            citations.append(CitationDetail(
                index=idx,
                chunk_id=chunk["id"],
                content=chunk["content"],
                relevance_score=chunk["score"],
            ))

    # 6. Dual-run for disagreement detection (only on first attempt to save API calls)
    disagreement_score = None
    if attempt_number == 1 and context_chunks:
        alt_answer = await generate_alternative_answer(
            query_text, context_prompt, SYSTEM_PROMPT,
        )
        if alt_answer:
            disagreement_score = 1.0 - compute_agreement_score(answer_text, alt_answer)

    # 7. Evaluate (if requested)
    eval_scores_dict = None
    composite_score = 0.0
    if auto_evaluate and context_chunks:
        eval_run = await evaluate_answer(
            db, "pending",  # Will update after answer is saved
            answer_text,
            [c["content"] for c in context_chunks],
            query_text,
            claim_support_ratio,
        )
        composite_score = eval_run.composite_score
        eval_scores_dict = {
            "composite": eval_run.composite_score,
            "citation_coverage": eval_run.citation_coverage,
            "retrieval_overlap": eval_run.retrieval_overlap,
            "claim_support_ratio": eval_run.claim_support_ratio,
        }

    # 8. Compute confidence
    confidence_data = compute_confidence(
        answer_text, context_chunks,
        composite_score, claim_support_ratio,
        disagreement_score,
    )

    # 9. Save answer
    answer_record = ResearchAnswer(
        query_id=query_id,
        answer_text=answer_text,
        reasoning_trace=reasoning_trace,
        attempt_number=attempt_number,
        confidence=confidence_data["confidence"],
        risk_level=confidence_data["risk_level"],
    )
    db.add(answer_record)
    await db.flush()

    # Save citations
    for cit in citations:
        citation_record = Citation(
            answer_id=answer_record.id,
            chunk_id=cit.chunk_id,
            relevance_score=cit.relevance_score,
            citation_index=cit.index,
        )
        db.add(citation_record)

    # Update eval run with actual answer ID
    if auto_evaluate and eval_scores_dict:
        eval_run.answer_id = answer_record.id

    await db.flush()

    # 10. Build response
    claim_verifications = [
        ClaimVerification(
            claim=vc.claim,
            status=vc.status,
            supporting_chunk_ids=vc.supporting_chunk_ids,
            confidence=vc.best_overlap_score,
        )
        for vc in verified_claims
    ]

    confidence_signal = ConfidenceSignal(
        confidence=confidence_data["confidence"],
        risk_level=confidence_data["risk_level"],
        disagreement_score=disagreement_score,
        explanation=confidence_data["explanation"],
    )

    result = ResearchAnswerResponse(
        query_id=query_id,
        answer_id=answer_record.id,
        query_text=query_text,
        answer_text=answer_text,
        reasoning_trace=reasoning_trace,
        attempt_number=attempt_number,
        citations=citations,
        claim_verifications=claim_verifications,
        confidence=confidence_signal,
        eval_scores=eval_scores_dict,
        created_at=answer_record.created_at,
    )

    logger.info("research_query_complete",
                query_id=query_id[:8],
                answer_id=answer_record.id[:8],
                confidence=confidence_data["confidence"],
                risk=confidence_data["risk_level"],
                claims_verified=len(verified_claims))

    return result
