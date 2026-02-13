
import os
import aiohttp
from typing import Any, Dict, List, Optional
from .registry import Tool, ToolPermission, ToolResult

class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web for real-time information using Brave Search."
    permission = ToolPermission.SEMI
    parameters = {
        "query": {
            "type": "string",
            "description": "The search query to execute",
            "required": True
        },
        "count": {
            "type": "integer",
            "description": "Number of results to return (default: 5)",
            "default": 5
        }
    }

    async def execute(self, query: str, count: int = 5) -> ToolResult:
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="BRAVE_SEARCH_API_KEY not found in environment variables."
            )
        
        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": api_key
        }
        params = {"q": query, "count": min(count, 10)}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        return ToolResult(
                            success=False,
                            error=f"Brave Search API error: {response.status} - {await response.text()}"
                        )
                    
                    data = await response.json()
                    
                    results = []
                    if "web" in data and "results" in data["web"]:
                        for item in data["web"]["results"]:
                            results.append({
                                "title": item.get("title"),
                                "url": item.get("url"),
                                "description": item.get("description"),
                                "age": item.get("age", "")
                            })
                    
                    return ToolResult(
                        success=True,
                        data={"results": results},
                        tool_name=self.name
                    )

        except Exception as e:
            return ToolResult(success=False, error=str(e), tool_name=self.name)
