"""
Tools API - Fabric MCP Integration

================================================================================
REST API for external tool execution via Fabric MCP.
Provides web search, file operations, calculations, etc.
================================================================================
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .fabric_client import FabricClient, FabricConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolCallRequest(BaseModel):
    tool_id: str
    capability: str
    parameters: Dict[str, Any]


class ToolCallResponse(BaseModel):
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ToolInfo(BaseModel):
    id: str
    name: str
    description: str
    capabilities: List[str]


# Available tools registry
AVAILABLE_TOOLS: List[ToolInfo] = [
    ToolInfo(
        id="web.brave_search",
        name="Web Search",
        description="Search the web using Brave search engine",
        capabilities=["search"]
    ),
    ToolInfo(
        id="io.read_file",
        name="Read File",
        description="Read contents of a file",
        capabilities=["read"]
    ),
    ToolInfo(
        id="io.write_file",
        name="Write File",
        description="Write content to a file",
        capabilities=["write"]
    ),
    ToolInfo(
        id="math.calculate",
        name="Calculator",
        description="Perform mathematical calculations",
        capabilities=["calculate"]
    ),
    ToolInfo(
        id="text.summarize",
        name="Text Summarizer",
        description="Summarize long text content",
        capabilities=["summarize"]
    ),
]


@router.get("/list")
async def list_tools() -> List[ToolInfo]:
    """List all available tools."""
    return AVAILABLE_TOOLS


@router.post("/call")
async def call_tool(request: ToolCallRequest) -> ToolCallResponse:
    """Call a specific tool via Fabric MCP."""
    try:
        async with FabricClient() as client:
            result = await client.call_tool(
                tool_id=request.tool_id,
                capability=request.capability,
                parameters=request.parameters
            )
            
            return ToolCallResponse(
                success=True,
                result=result
            )
            
    except Exception as e:
        logger.error(f"Tool call error: {e}")
        return ToolCallResponse(
            success=False,
            error=str(e)
        )


@router.get("/search")
async def search_web(
    query: str = Query(..., description="Search query"),
    max_results: int = Query(5, ge=1, le=20),
    recency_days: int = Query(7, ge=1, le=365)
) -> Dict[str, Any]:
    """Search the web using Brave."""
    try:
        async with FabricClient() as client:
            result = await client.search_web(
                query=query,
                max_results=max_results,
                recency_days=recency_days
            )
            return {
                "success": True,
                "results": result
            }
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calculate")
async def calculate(
    expression: str = Query(..., description="Mathematical expression")
) -> Dict[str, Any]:
    """Perform a calculation."""
    try:
        async with FabricClient() as client:
            result = await client.calculate(expression)
            return {
                "success": True,
                "result": result
            }
    except Exception as e:
        logger.error(f"Calculation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/read")
async def read_file(
    path: str = Query(..., description="File path to read"),
    max_lines: Optional[int] = Query(None)
) -> Dict[str, Any]:
    """Read a file via Fabric."""
    try:
        async with FabricClient() as client:
            content = await client.read_file(path, max_lines)
            return {
                "success": True,
                "content": content
            }
    except Exception as e:
        logger.error(f"Read error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/write")
async def write_file(
    path: str = Query(..., description="File path to write"),
    content: str = Query(..., description="Content to write"),
    append: bool = Query(False)
) -> Dict[str, Any]:
    """Write to a file via Fabric."""
    try:
        async with FabricClient() as client:
            result = await client.write_file(path, content, append)
            return {
                "success": True,
                "result": result
            }
    except Exception as e:
        logger.error(f"Write error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
