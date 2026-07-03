"""
MCP Tool Registry & Router.

Provides a registry of tools that agents can invoke programmatically.
Supports both rule-based and LLM-driven tool selection.

Each tool implements BaseTool with structured inputs/outputs.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from groq import Groq

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ToolResult:
    """Structured result from a tool execution."""
    data: Any
    metadata: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    success: bool = True


class BaseTool(ABC):
    """Base class for all MCP tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for LLM tool selection."""
        ...

    @property
    @abstractmethod
    def parameters_schema(self) -> dict:
        """JSON schema for tool parameters."""
        ...

    @abstractmethod
    async def execute(self, params: dict) -> ToolResult:
        """Execute the tool with given parameters."""
        ...


class ToolRegistry:
    """
    Central registry for all MCP tools.

    Supports:
    - Manual tool registration
    - Tool listing with descriptions
    - Direct execution by name
    - LLM-driven tool selection based on query
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info("tool_registered", name=tool.name)

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        """List all registered tools with descriptions."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
            }
            for t in self._tools.values()
        ]

    async def execute(self, name: str, params: dict) -> ToolResult:
        """Execute a tool by name."""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                data=None,
                errors=[f"Tool '{name}' not found"],
                success=False,
            )

        try:
            logger.info("tool_executing", name=name)
            result = await tool.execute(params)
            logger.info("tool_executed",
                        name=name,
                        success=result.success,
                        errors=result.errors)
            return result
        except Exception as e:
            logger.error("tool_execution_failed", name=name, error=str(e))
            return ToolResult(
                data=None,
                errors=[str(e)],
                success=False,
            )

    async def auto_select_and_execute(
        self, query: str, context: Optional[str] = None
    ) -> tuple[str, ToolResult]:
        """
        LLM-driven tool selection: given a query, pick the best tool and execute it.

        Uses a lightweight prompt to classify the query intent
        and map it to the most appropriate tool.
        """
        settings = get_settings()
        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in self._tools.values()
        )

        selection_prompt = f"""Given this user query, select the single most appropriate tool.

Available tools:
{tool_descriptions}

Query: {query}

Respond with ONLY valid JSON:
{{"tool": "<tool_name>", "params": {{<relevant parameters>}}, "reasoning": "<one sentence why>"}}"""

        try:
            client = Groq(api_key=settings.groq_api_key)
            response = client.chat.completions.create(
                model=settings.groq_fast_model,
                messages=[{"role": "user", "content": selection_prompt}],
                temperature=0.1,
                max_tokens=256,
            )

            content = response.choices[0].message.content or ""
            import re
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                selection = json.loads(json_match.group())
                tool_name = selection.get("tool", "")
                params = selection.get("params", {})

                if query:
                    params.setdefault("query", query)

                logger.info("tool_auto_selected",
                            tool=tool_name,
                            reasoning=selection.get("reasoning", ""))

                result = await self.execute(tool_name, params)
                return tool_name, result

        except Exception as e:
            logger.warning("auto_select_failed", error=str(e))

        # Fallback to search
        return "search", await self.execute("search", {"query": query})


# Singleton registry
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def ensure_default_tools_registered() -> ToolRegistry:
    """Register built-in tools if startup registration has not run yet."""
    from app.tools.cluster_tool import ClusterTool
    from app.tools.evaluate_tool import EvaluateTool
    from app.tools.search_tool import SearchTool
    from app.tools.summarize_tool import SummarizeTool

    registry = get_registry()
    for tool in (SearchTool(), SummarizeTool(), ClusterTool(), EvaluateTool()):
        if registry.get(tool.name) is None:
            registry.register(tool)
    return registry
