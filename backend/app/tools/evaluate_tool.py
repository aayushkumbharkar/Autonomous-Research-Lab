"""Evaluate Tool — wraps evaluation engine for MCP interface."""

from app.tools.registry import BaseTool, ToolResult


class EvaluateTool(BaseTool):
    @property
    def name(self) -> str:
        return "evaluate"

    @property
    def description(self) -> str:
        return (
            "Evaluate the quality of an AI-generated answer against source context. "
            "Best for checking faithfulness, coverage, and specificity of responses."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "answer": {"type": "string", "description": "Answer to evaluate"},
                "context": {"type": "array", "items": {"type": "string"}, "description": "Source context chunks"},
                "query": {"type": "string", "description": "Original query"},
            },
            "required": ["answer", "context", "query"],
        }

    async def execute(self, params: dict) -> ToolResult:
        answer = params.get("answer", "")
        context = params.get("context", [])
        query = params.get("query", "")

        if not answer or not query:
            return ToolResult(
                data=None,
                errors=["Answer and query are required"],
                success=False,
            )

        try:
            # Import here to avoid circular dependency
            from app.services.evaluation import (
                _citation_coverage,
                _retrieval_overlap,
                _llm_score,
            )
            from app.services.claim_verifier import verify_claims

            # Deterministic scores
            cit_cov, cit_expl = _citation_coverage(answer)
            ret_ovl, ret_expl = _retrieval_overlap(answer, context)

            # Claim verification
            chunks_for_verify = [{"id": str(i), "content": c} for i, c in enumerate(context)]
            claims, support_ratio = verify_claims(answer, chunks_for_verify)

            # LLM scores
            context_str = "\n\n---\n\n".join(context)
            faith, faith_e = await _llm_score("faithfulness", answer, context_str, query)
            cover, cover_e = await _llm_score("coverage", answer, context_str, query)

            return ToolResult(
                data={
                    "scores": {
                        "faithfulness": round(faith * support_ratio, 3),
                        "coverage": round(cover, 3),
                        "citation_coverage": cit_cov,
                        "retrieval_overlap": ret_ovl,
                        "claim_support_ratio": round(support_ratio, 3),
                    },
                    "explanations": {
                        "faithfulness": faith_e,
                        "coverage": cover_e,
                        "citation_coverage": cit_expl,
                        "retrieval_overlap": ret_expl,
                    },
                    "claims": [
                        {"claim": c.claim, "status": c.status, "score": c.best_overlap_score}
                        for c in claims
                    ],
                },
            )

        except Exception as e:
            return ToolResult(data=None, errors=[str(e)], success=False)
