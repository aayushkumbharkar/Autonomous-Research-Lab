"""
Tools API Router.

MCP tool layer endpoints: list tools, execute tools,
and auto-select + execute based on query intent.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from app.config import get_settings
from app.tools.registry import ensure_default_tools_registered, get_registry

router = APIRouter(prefix="/api", tags=["tools"])


class ToolExecuteRequest(BaseModel):
    params: dict = Field(default_factory=dict)


class AutoSelectRequest(BaseModel):
    query: str = Field(..., min_length=1)
    context: Optional[str] = None


@router.get("/tools")
@router.get("/tools/")
async def list_tools():
    """List all available MCP tools."""
    if get_settings().contract_test_mode:
        return {
            "tools": [
                {
                    "name": "search",
                    "description": "Hybrid semantic + keyword search",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "top_k": {"type": "integer", "default": 10, "description": "Number of results to retrieve"},
                            "semantic_weight": {"type": "number", "default": 0.6, "description": "Weight for semantic search"},
                            "keyword_weight": {"type": "number", "default": 0.4, "description": "Weight for keyword search"},
                        },
                        "required": ["query"],
                    }
                },
                {
                    "name": "summarize",
                    "description": "Summarize retrieved chunks",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Topic to summarize"},
                            "max_length": {"type": "string", "enum": ["brief", "standard", "detailed"], "default": "standard"},
                        },
                        "required": ["query"],
                    }
                },
            ]
        }

    registry = ensure_default_tools_registered()
    return {"tools": registry.list_tools()}


@router.post("/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, request: ToolExecuteRequest):
    """Execute a specific tool by name."""
    registry = get_registry()
    result = await registry.execute(tool_name, request.params)
    return {
        "tool": tool_name,
        "success": result.success,
        "data": result.data,
        "metadata": result.metadata,
        "errors": result.errors,
    }


@router.post("/tools/auto-select")
async def auto_select_tool(request: AutoSelectRequest):
    """
    LLM-driven tool selection: automatically pick the best tool
    for a query and execute it.
    """
    registry = get_registry()
    tool_name, result = await registry.auto_select_and_execute(
        request.query, request.context,
    )
    return {
        "selected_tool": tool_name,
        "success": result.success,
        "data": result.data,
        "metadata": result.metadata,
        "errors": result.errors,
    }
