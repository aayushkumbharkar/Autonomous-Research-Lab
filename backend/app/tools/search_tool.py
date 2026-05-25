"""Search Tool — wraps HybridRetriever for MCP interface."""

from app.tools.registry import BaseTool, ToolResult
from app.services.retrieval import hybrid_search


class SearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "search"

    @property
    def description(self) -> str:
        return (
            "Search through interview transcripts and documents using hybrid "
            "semantic + keyword search. Best for finding specific information, "
            "facts, quotes, or data points."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "default": 10},
                "semantic_weight": {"type": "number", "default": 0.6},
                "keyword_weight": {"type": "number", "default": 0.4},
            },
            "required": ["query"],
        }

    async def execute(self, params: dict) -> ToolResult:
        query = params.get("query", "")
        if not query:
            return ToolResult(data=[], errors=["Query is required"], success=False)

        try:
            results, metadata = hybrid_search(
                query,
                top_k=params.get("top_k", 10),
                semantic_weight=params.get("semantic_weight", 0.6),
                keyword_weight=params.get("keyword_weight", 0.4),
            )

            return ToolResult(
                data=[r.model_dump() for r in results],
                metadata=metadata,
            )
        except Exception as e:
            return ToolResult(data=[], errors=[str(e)], success=False)
