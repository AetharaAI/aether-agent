
from typing import Dict, Any, Optional
from .registry import Tool, ToolResult, ToolPermission
from ..fabric_client import FabricClient, FabricError

class FabricTool(Tool):
    """
    Adapter that exposes a Fabric MCP tool as a native Aether tool.
    Delegate execution to the remote Fabric server.
    """
    
    def __init__(
        self, 
        tool_def: Dict[str, Any], 
        client: Optional[FabricClient] = None
    ):
        self.name = tool_def.get("id", "")
        self.description = tool_def.get("description", "")
        self.permission = ToolPermission.SEMI # Default to semi-auto for external tools
        self.parameters = tool_def.get("parameters", {})
        self._capability = tool_def.get("capabilities", ["execute"])[0]
        self._client = client
        
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool via Fabric Client"""
        # Create a fresh client if one wasn't provided (transient usage)
        client = self._client
        should_close = False
        
        if not client:
            client = FabricClient()
            should_close = True
            
        try:
            if should_close:
                await client.__aenter__()
                
            result_data = await client.call_tool(
                tool_id=self.name,
                capability=self._capability,
                parameters=kwargs
            )
            
            return ToolResult(
                success=True,
                data=result_data,
                tool_name=self.name
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                tool_name=self.name
            )
        finally:
            if should_close and client:
                await client.__aexit__(None, None, None)
