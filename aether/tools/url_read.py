
import aiohttp
import logging
from typing import Any, Dict, Optional
from .registry import Tool, ToolPermission, ToolResult

logger = logging.getLogger(__name__)

class URLReadTool(Tool):
    name = "url_read"
    description = "Fetch the raw content of a specific URL (HTML or Markdown)."
    permission = ToolPermission.SEMI
    parameters = {
        "url": {
            "type": "string",
            "description": "The URL to fetch content from",
            "required": True
        }
    }

    async def execute(self, url: str) -> ToolResult:
        logger.info(f"Fetching URL: {url}")
        
        try:
            headers = {
                "User-Agent": "AetherAgent/1.0 (Mozilla/5.0; autonomous AI agent)"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status != 200:
                        return ToolResult(
                            success=False,
                            error=f"Failed to fetch URL: {response.status} - {response.reason}"
                        )
                    
                    content_type = response.headers.get("Content-Type", "")
                    text = await response.text()
                    
                    # Truncate very large responses
                    if len(text) > 20000:
                        text = text[:20000] + "\n\n[Content truncated - too large]"
                    
                    return ToolResult(
                        success=True,
                        data={
                            "url": url,
                            "content_type": content_type,
                            "content": text
                        },
                        tool_name=self.name
                    )

        except Exception as e:
            logger.error(f"URL fetch error: {e}")
            return ToolResult(success=False, error=str(e), tool_name=self.name)
