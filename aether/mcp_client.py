
import asyncio
import aiohttp
import json
import logging
from typing import Dict, Any, List, Optional, Callable
import uuid

logger = logging.getLogger(__name__)

class StandardMCPClient:
    """
    A generic MCP client supporting HTTP + SSE transport.
    Follows the official Model Context Protocol (MCP) specification.
    """
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None
        self._sse_url: Optional[str] = None
        self._post_url: Optional[str] = None
        self._connected = False
        self._id_counter = 0
        
    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
            
    async def connect(self):
        """Establish SSE connection and discover message endpoint."""
        logger.info(f"Connecting to MCP server at {self.base_url}")
        
        headers = {
            "Accept": "text/event-stream"
        }
        
        try:
            # The initial GET request initiates the SSE session
            # We don't need to keep it open here if we just want to find the post URL,
            # but for a full client we would.
            # Many implementations send the 'endpoint' as an event.
            
            async with self._session.get(self.base_url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"Failed to connect: {response.status}")
                
                # In SSE MCP, the server should send an 'endpoint' event
                async for line_bytes in response.content:
                    line = line_bytes.decode('utf-8', errors='replace').strip()
                    if line.startswith("data:"):
                        uri = line[5:].strip()
                        if uri.startswith("/") or uri.startswith("http"):
                            if uri.startswith("/"):
                                # Handle relative path
                                from urllib.parse import urljoin
                                self._post_url = urljoin(self.base_url, uri)
                            else:
                                self._post_url = uri
                            logger.info(f"Discovered MCP message endpoint: {self._post_url}")
                            # Once we have the endpoint, we can stop reading the initial SSE stream
                            # for this simple tool-discovery client.
                            break
                    if "endpoint" in line: # Some variants might not use 'data:' prefix correctly
                        pass
            
            if not self._post_url:
                # If no endpoint discovered, try common defaults or fallback to base
                self._post_url = self.base_url
            
            self._connected = True
        except Exception as e:
            logger.error(f"MCP connection failed: {e}")
            raise

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request to the MCP server."""
        self._id_counter += 1
        request_id = self._id_counter
        
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        async with self._session.post(self._post_url, json=payload) as response:
            if response.status != 202 and response.status != 200:
                 # Standard MCP says 202 Accepted for SSE post
                 pass
            
            # For Tavily/standard HTTP MCP, we might get the response immediately 
            # or it might come back through the SSE stream.
            # If it's a synchronous HTTP bridge, it might be in the POST response.
            if response.status == 200:
                return await response.json()
            else:
                return {"ok": True, "status": "accepted"}

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools via standard MCP method."""
        result = await self._send_request("tools/list", {})
        # Note: In true SSE, this result might be empty if the answer comes via SSE.
        # But many bridges return it directly.
        if "result" in result and "tools" in result["result"]:
            return result["result"]["tools"]
        return []

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool via standard MCP method."""
        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        if "result" in result:
            return result["result"]
        return result
