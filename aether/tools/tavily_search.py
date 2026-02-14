
import os
import aiohttp
import logging
from typing import Any, Dict, List, Optional
from .registry import Tool, ToolPermission, ToolResult

logger = logging.getLogger(__name__)

class TavilySearchTool(Tool):
    name = "web_search"  # Replacing the existing search tool name
    description = "Search the web for real-time information using Tavily. Provides detailed results and raw content."
    permission = ToolPermission.SEMI
    parameters = {
        "query": {
            "type": "string",
            "description": "The search query to execute",
            "required": True
        },
        "search_depth": {
            "type": "string",
            "description": "The depth of the search: 'basic' or 'advanced'",
            "default": "basic",
            "enum": ["basic", "advanced"]
        },
        "include_raw_content": {
            "type": "boolean",
            "description": "Whether to include raw content from pages",
            "default": False
        },
        "max_results": {
            "type": "integer",
            "description": "Number of results to return (default: 5)",
            "default": 5
        }
    }

    async def execute(self, query: str, search_depth: str = "advanced", include_raw_content: bool = True, max_results: int = 10) -> ToolResult:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="TAVILY_API_KEY not found in environment variables."
            )
        
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": search_depth,
            "include_raw_content": include_raw_content,
            "include_images": False,
            "max_results": min(max_results, 15)
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        return ToolResult(
                            success=False,
                            error=f"Tavily Search API error: {response.status} - {await response.text()}"
                        )
                    
                    data = await response.json()
                    
                    results = []
                    for item in data.get("results", []):
                        result = {
                            "title": item.get("title"),
                            "url": item.get("url"),
                            "content": item.get("content"),
                            "score": item.get("score", 0)
                        }
                        if include_raw_content and item.get("raw_content"):
                            result["raw_content"] = item.get("raw_content")[:2000] # Truncate raw content
                        results.append(result)
                    
                    return ToolResult(
                        success=True,
                        data={"results": results, "answer": data.get("answer")},
                        tool_name=self.name
                    )

        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return ToolResult(success=False, error=str(e), tool_name=self.name)
