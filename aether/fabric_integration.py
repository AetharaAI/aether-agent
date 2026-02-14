
import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
from fabric_a2a import AsyncFabricClient, AsyncMessagingClient

logger = logging.getLogger(__name__)

class FabricIntegration:
    """
    Combined manager for Fabric Client (Tools) and Fabric Messaging (A2A).
    
    This provides a simplified interface for the Aether Agent to interact
    with the sovereign Fabric infrastructure using the official fabric-a2a package.
    """
    
    def __init__(self, agent_id: str = "aether"):
        self.agent_id = agent_id
        # Initialize client with environment variables
        self.client = AsyncFabricClient(
            base_url=os.getenv("FABRIC_BASE_URL", "https://fabric.perceptor.us"),
            token=os.getenv("FABRIC_AUTH_TOKEN", "dev-shared-secret"),
            timeout=float(os.getenv("FABRIC_TIMEOUT_MS", "60000")) / 1000
        )
        # Initialize messaging with agent_id and optional redis_url
        self.messaging = AsyncMessagingClient(
            agent_id=agent_id,
            redis_url=os.getenv("FABRIC_REDIS_URL", "redis://localhost:6379")
        )
        self._is_started = False
        
    async def start(self):
        """Start the messaging loop and prepare the client."""
        if self._is_started:
            return
            
        logger.info(f"Starting Fabric Integration for agent '{self.agent_id}'")
        # connect and start_listening are the official way to start messaging
        await self.messaging.connect()
        self.messaging.start_listening()
        
        # Verify connectivity
        try:
            health_status = await self.client.health()
            # HealthStatus object usually has a 'status' attribute
            status = getattr(health_status, 'status', 'unknown')
            logger.info(f"Fabric Health Check: {status}")
        except Exception as e:
            logger.warning(f"Fabric initialization health check failed: {e}")
            
        self._is_started = True
        
    async def stop(self):
        """Stop messaging and cleanup."""
        if not self._is_started:
            return
            
        logger.info("Stopping Fabric Integration")
        await self.messaging.close()
        await self.client.close()
        self._is_started = False

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    def on_message(self, message_type: str):
        """Decorator for registering message handlers."""
        return self.messaging.on(message_type)

    async def send_task(self, to_agent: str, task_type: str, payload: Dict[str, Any]):
        """Send a task to another agent via Fabric."""
        return await self.messaging.send_task(to_agent, task_type, payload)

    async def discover_tools(self) -> List[Dict[str, Any]]:
        """Fetch available tools from the Fabric MCP server."""
        try:
            # list_tools usually returns a list of ToolInfo objects or dicts
            tools = await self.client.list_tools()
            # Ensure it returns a list of dictionaries for compatibility
            results = []
            for t in (tools or []):
                if hasattr(t, 'to_dict'):
                    results.append(t.to_dict())
                elif isinstance(t, dict):
                    results.append(t)
                else:
                    # Fallback for unexpected types
                    results.append(vars(t) if hasattr(t, '__dict__') else str(t))
            return results
        except Exception as e:
            logger.error(f"Failed to discover Fabric tools: {e}")
            return []
