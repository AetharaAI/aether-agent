
from typing import Any, Dict, Optional
from .registry import Tool, ToolPermission, ToolResult
from ..mcp_client import StandardMCPClient

class StandardMCPTool(Tool):
    """
    Adapter that exposes a standard MCP tool as an Aether tool.
    """
    def __init__(
        self, 
        tool_def: Dict[str, Any], 
        client: StandardMCPClient
    ):
        self.name = tool_def.get("name")
        self.description = tool_def.get("description", "")
        self.permission = ToolPermission.SEMI
        # MCP uses JSON Schema for parameters
        self.parameters = tool_def.get("inputSchema", {}).get("properties", {})
        self._client = client
        
    async def execute(self, **kwargs) -> ToolResult:
        try:
            result = await self._client.call_tool(self.name, kwargs)
            
            # Standard MCP returns { content: [ { type: "text", text: "..." } ] }
            content_list = result.get("content", [])
            output_text = ""
            for item in content_list:
                if item.get("type") == "text":
                    output_text += item.get("text", "")
            
            # Handle non-standard or direct results
            if not output_text and isinstance(result, dict):
                output_text = json.dumps(result)
                
            return ToolResult(
                success=True,
                data=result,
                output=output_text,
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                tool_name=self.name
            )

import json
