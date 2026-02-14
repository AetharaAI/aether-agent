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

import os
from fabric_a2a import AsyncFabricClient

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
        async with AsyncFabricClient(
            base_url=os.getenv("FABRIC_BASE_URL", "https://fabric.perceptor.us"),
            token=os.getenv("FABRIC_AUTH_TOKEN", "dev-shared-secret")
        ) as client:
            # Note: the new API uses tool_name and arguments
            result = await client.call(
                tool_name=request.tool_id,
                arguments=request.parameters
            )
            
            # CallResult might be an object, check if it has 'data'
            data = getattr(result, 'data', result)
            
            return ToolCallResponse(
                success=True,
                result=data
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
        async with AsyncFabricClient(
            base_url=os.getenv("FABRIC_BASE_URL", "https://fabric.perceptor.us"),
            token=os.getenv("FABRIC_AUTH_TOKEN", "dev-shared-secret")
        ) as client:
            result = await client.call(
                tool_name="web.brave_search",
                arguments={"query": query, "max_results": max_results, "recency_days": recency_days}
            )
            data = getattr(result, 'data', result)
            return {
                "success": True,
                "results": data
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
        async with AsyncFabricClient(
            base_url=os.getenv("FABRIC_BASE_URL", "https://fabric.perceptor.us"),
            token=os.getenv("FABRIC_AUTH_TOKEN", "dev-shared-secret")
        ) as client:
            result = await client.call(
                tool_name="math.calculate",
                arguments={"expression": expression}
            )
            data = getattr(result, 'data', result)
            val = data.get("result", 0.0) if isinstance(data, dict) else data
            return {
                "success": True,
                "result": val
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
        async with AsyncFabricClient(
            base_url=os.getenv("FABRIC_BASE_URL", "https://fabric.perceptor.us"),
            token=os.getenv("FABRIC_AUTH_TOKEN", "dev-shared-secret")
        ) as client:
            result = await client.call(
                tool_name="io.read_file",
                arguments={"path": path, "max_lines": max_lines}
            )
            data = getattr(result, 'data', result)
            content = data.get("content", "") if isinstance(data, dict) else data
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
        async with AsyncFabricClient(
            base_url=os.getenv("FABRIC_BASE_URL", "https://fabric.perceptor.us"),
            token=os.getenv("FABRIC_AUTH_TOKEN", "dev-shared-secret")
        ) as client:
            result = await client.call(
                tool_name="io.write_file",
                arguments={"path": path, "content": content, "append": append}
            )
            data = getattr(result, 'data', result)
            return {
                "success": True,
                "result": data
            }
    except Exception as e:
        logger.error(f"Write error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
