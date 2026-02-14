
import os
from typing import Dict, Any, Optional
from .registry import Tool, ToolResult, ToolPermission
from fabric_a2a import AsyncFabricClient

class FabricTool(Tool):
    """
    Adapter that exposes a Fabric MCP tool as a native Aether tool.
    Delegate execution to the remote Fabric server.
    """
    
    def __init__(
        self, 
        tool_def: Dict[str, Any], 
        client: Optional[AsyncFabricClient] = None
    ):
        self.name = tool_def.get("id", "")
        self.description = tool_def.get("description", "")
        self.permission = ToolPermission.SEMI # Default to semi-auto for external tools
        self.parameters = tool_def.get("parameters", {})
        self._client = client
        
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool via Fabric Client"""
        client = self._client
        should_close = False
        
        if not client:
            client = AsyncFabricClient(
                base_url=os.getenv("FABRIC_BASE_URL", "https://fabric.perceptor.us"),
                token=os.getenv("FABRIC_AUTH_TOKEN", "dev-shared-secret")
            )
            should_close = True
            
        try:
            if should_close:
                await client.__aenter__()
                
            result = await client.call(
                tool_name=self.name,
                arguments=kwargs
            )
            
            data = getattr(result, 'data', result)
            
            return ToolResult(
                success=True,
                data=data,
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
                await client.close()
