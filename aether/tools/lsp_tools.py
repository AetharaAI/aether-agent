
import os
import logging
from typing import Any, Dict, Optional
from aether.tools.registry import Tool, ToolResult, ToolPermission, Capability
from aether.tools.lsp.manager import LSPManager

logger = logging.getLogger("aether.lsp")

class LSPBaseTool(Tool):
    """Base class for LSP tools implementing the required interface."""
    
    def __init__(self, name: str, description: str, handler: Any, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.permission = ToolPermission.SEMI
        self.parameters = parameters
        self._handler = handler

    async def execute(self, **kwargs) -> ToolResult:
        try:
            res = await self._handler(**kwargs)
            if isinstance(res, dict) and "error" in res:
                return ToolResult(success=False, error=res["error"], tool_name=self.name)
            return ToolResult(success=True, data=res, tool_name=self.name)
        except Exception as e:
            logger.error(f"LSP Tool {self.name} failed: {e}")
            return ToolResult(success=False, error=str(e), tool_name=self.name)

class LSPToolIntegration:
    """Exposes LSP capabilities as agent tools."""
    
    def __init__(self, manager: LSPManager):
        self.manager = manager
        
    def register_tools(self, registry):
        """Register all LSP tools."""
        try:
            tools = [
                LSPBaseTool(
                    name="lsp.open_file",
                    description="Open a file in LSP session (Required before other tools)",
                    handler=self.open_file,
                    parameters={"path": {"type": "string", "description": "Absolute path"}}
                ),
                LSPBaseTool(
                    name="lsp.get_definition",
                    description="Go to definition",
                    handler=self.get_definition,
                    parameters={
                        "path": {"type": "string"},
                        "line": {"type": "integer"},
                        "character": {"type": "integer"}
                    }
                ),
                LSPBaseTool(
                    name="lsp.get_references",
                    description="Find references",
                    handler=self.get_references,
                    parameters={
                        "path": {"type": "string"},
                        "line": {"type": "integer"},
                        "character": {"type": "integer"}
                    }
                ),
                LSPBaseTool(
                    name="lsp.get_hover",
                    description="Get hover info",
                    handler=self.get_hover,
                    parameters={
                        "path": {"type": "string"},
                        "line": {"type": "integer"},
                        "character": {"type": "integer"}
                    }
                ),
                LSPBaseTool(
                    name="lsp.document_symbols",
                    description="List symbols in file",
                    handler=self.document_symbols,
                    parameters={"path": {"type": "string"}}
                )
            ]
            
            for t in tools:
                registry.register(t)
                
        except Exception as e:
            logger.error(f"Failed to register LSP tools: {e}")
            raise e

    async def open_file(self, path: str):
        ext = os.path.splitext(path)[1]
        client = self.manager.get_client(ext)
        if not client:
            return {"error": f"LSP not available for {ext}"}
        try:
            with open(path, 'r') as f:
                content = f.read()
            client.open_file(path, content)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}

    async def get_definition(self, path: str, line: int, character: int):
        client = self.manager.get_client(os.path.splitext(path)[1])
        if not client: return {"error": "LSP not available"}
        return client.get_definition(path, line, character)

    async def get_references(self, path: str, line: int, character: int):
        client = self.manager.get_client(os.path.splitext(path)[1])
        if not client: return {"error": "LSP not available"}
        return client.get_references(path, line, character)

    async def get_hover(self, path: str, line: int, character: int):
        client = self.manager.get_client(os.path.splitext(path)[1])
        if not client: return {"error": "LSP not available"}
        return client.get_hover(path, line, character)

    async def document_symbols(self, path: str):
        client = self.manager.get_client(os.path.splitext(path)[1])
        if not client: return {"error": "LSP not available"}
        return client.get_document_symbols(path)
