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

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolExecuteRequest(BaseModel):
    params: dict = Field(default_factory=dict)


class AutoSelectRequest(BaseModel):
    query: str = Field(..., min_length=1)
    context: Optional[str] = None


@router.get("")
@router.get("/")
async def list_tools():
    """List all available MCP tools."""
    if get_settings().contract_test_mode:
        return {
            "tools": [
                {
                    "name": "search",
                    "description": "Hybrid semantic + keyword search",
                },
                {
                    "name": "summarize",
                    "description": "Summarize retrieved chunks",
                },
            ]
        }

    registry = ensure_default_tools_registered()
    return {"tools": registry.list_tools()}


@router.post("/{tool_name}/execute")
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


@router.post("/auto-select")
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
