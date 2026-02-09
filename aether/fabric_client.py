"""
Fabric MCP Client - HTTP Client for Tool Calls

Connects to Fabric MCP Server for synchronous tool execution.
Part of sovereign infrastructure - no external dependencies.
"""

import os
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class FabricConfig:
    """Configuration for Fabric MCP connection."""
    base_url: str = "https://fabric.perceptor.us"
    auth_token: str = "dev-shared-secret"
    timeout_ms: int = 60000
    
    @classmethod
    def from_env(cls) -> "FabricConfig":
        """Load configuration from environment variables."""
        return cls(
            base_url=os.getenv("FABRIC_BASE_URL", "https://fabric.perceptor.us"),
            auth_token=os.getenv("FABRIC_AUTH_TOKEN", "dev-shared-secret"),
            timeout_ms=int(os.getenv("FABRIC_TIMEOUT_MS", "60000")),
        )


class FabricError(Exception):
    """Error from Fabric MCP server."""
    
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class FabricClient:
    """
    MCP client for Fabric - Synchronous Tool Calls
    
    Usage:
        async with FabricClient() as client:
            # Call tools
            results = await client.search_web("quantum computing")
            
            # File operations
            content = await client.read_file("/path/to/file.txt")
            await client.write_file("/path/to/output.txt", "content")
            
            # Math
            result = await client.calculate("(2 + 3) * 4")
            
            # List available tools
            tools = await client.list_tools()
    """
    
    def __init__(self, config: Optional[FabricConfig] = None):
        self.config = config or FabricConfig.from_env()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
    
    async def call_tool(
        self,
        tool_id: str,
        capability: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call any Fabric tool synchronously.
        
        Args:
            tool_id: e.g., "web.brave_search", "io.read_file"
            capability: e.g., "search", "read"
            parameters: Tool-specific args
            
        Returns:
            The result.data field on success
            
        Raises:
            FabricError: On execution error
        """
        url = f"{self.config.base_url}/mcp/call"
        
        payload = {
            "name": "fabric.tool.call",
            "arguments": {
                "tool_id": tool_id,
                "capability": capability,
                "parameters": parameters
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.auth_token}"
        }
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_ms / 1000)
        
        async with self._session.post(
            url, json=payload, headers=headers, timeout=timeout
        ) as response:
            response.raise_for_status()
            result = await response.json()
            
            if not result.get("ok"):
                error = result.get("error", {})
                raise FabricError(error.get("code", "UNKNOWN"), error.get("message", "Unknown error"))
            
            return result.get("result", {})
    
    # === Convenience Methods ===
    
    async def search_web(
        self,
        query: str,
        max_results: int = 5,
        recency_days: int = 7
    ) -> Dict[str, Any]:
        """Search web via Brave."""
        return await self.call_tool(
            "web.brave_search",
            "search",
            {"query": query, "max_results": max_results, "recency_days": recency_days}
        )
    
    async def read_file(self, path: str, max_lines: Optional[int] = None) -> str:
        """Read file content."""
        result = await self.call_tool(
            "io.read_file",
            "read",
            {"path": path, "max_lines": max_lines}
        )
        return result.get("content", "")
    
    async def write_file(self, path: str, content: str, append: bool = False) -> Dict:
        """Write to file."""
        return await self.call_tool(
            "io.write_file",
            "write",
            {"path": path, "content": content, "append": append}
        )
    
    async def calculate(self, expression: str) -> float:
        """Evaluate math expression."""
        result = await self.call_tool(
            "math.calculate",
            "eval",
            {"expression": expression}
        )
        return result.get("result", 0.0)
    
    async def http_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict] = None,
        body: Optional[str] = None
    ) -> Dict[str, Any]:
        """Make HTTP request."""
        return await self.call_tool(
            "web.http_request",
            "request",
            {"url": url, "method": method, "headers": headers, "body": body}
        )
    
    async def list_tools(self) -> Dict[str, Any]:
        """List all available tools."""
        return await self.call_tool("fabric.tool.list", "list", {})
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Fabric health."""
        url = f"{self.config.base_url}/health"
        async with self._session.get(url) as response:
            return await response.json()


# Export
__all__ = ["FabricClient", "FabricConfig", "FabricError"]
