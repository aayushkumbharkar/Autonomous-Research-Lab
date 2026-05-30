"""Summarize Tool — generates summaries via Groq LLM."""

from groq import Groq
from app.config import get_settings
from app.tools.registry import BaseTool, ToolResult
from app.services.retrieval import hybrid_search


class SummarizeTool(BaseTool):
    @property
    def name(self) -> str:
        return "summarize"

    @property
    def description(self) -> str:
        return (
            "Summarize content from the knowledge base. Best for getting "
            "an overview of a topic, creating executive summaries, or "
            "condensing large amounts of information."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Topic to summarize"},
                "max_length": {"type": "string", "enum": ["brief", "standard", "detailed"], "default": "standard"},
            },
            "required": ["query"],
        }

    async def execute(self, params: dict) -> ToolResult:
        query = params.get("query", "")
        max_length = params.get("max_length", "standard")

        if not query:
            return ToolResult(data=None, errors=["Query is required"], success=False)

        length_tokens = {"brief": 256, "standard": 512, "detailed": 1024}

        try:
            # Retrieve relevant chunks
            results, metadata = hybrid_search(query, top_k=15)
            if not results:
                return ToolResult(
                    data={"summary": "No relevant content found to summarize."},
                    metadata=metadata,
                )

            context = "\n\n".join([r.content for r in results])

            settings = get_settings()
            client = Groq(api_key=settings.groq_api_key)
            response = client.chat.completions.create(
                model=settings.groq_fast_model,
                messages=[
                    {"role": "system", "content": "You are a precise summarizer. Summarize ONLY based on the provided content. Do not add information."},
                    {"role": "user", "content": f"Summarize the following content about '{query}':\n\n{context}"},
                ],
                temperature=0.3,
                max_tokens=length_tokens.get(max_length, 512),
            )

            summary = response.choices[0].message.content or ""

            return ToolResult(
                data={
                    "summary": summary,
                    "source_chunk_count": len(results),
                    "length": max_length,
                },
                metadata=metadata,
            )

        except Exception as e:
            return ToolResult(data=None, errors=[str(e)], success=False)
