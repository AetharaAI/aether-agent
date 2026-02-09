"""
Fabric Messaging - Async A2A Messaging via Redis Streams

Agent-to-agent communication using Redis Streams on Fabric VM.
Part of sovereign infrastructure - connects to Redis Stack on ochcloud VM.
"""

import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

import redis.asyncio as redis


class FabricMessaging:
    """
    Async A2A messaging client using Redis Streams.
    
    Connects to Redis Stack running on the Fabric VM for real-time
    agent communication. Supports direct messaging and pub/sub topics.
    
    Usage:
        messaging = FabricMessaging(agent_id="aether")
        await messaging.start()
        
        # Send task to another agent
        await messaging.send_task("percy", "analyze", {"data": [...]})
        
        # Receive messages
        messages = await messaging.receive_messages(count=10)
        
        # Subscribe to topics
        @messaging.on("analytics.insights")
        async def handler(data):
            print(f"New insight: {data}")
    """
    
    def __init__(
        self,
        agent_id: str,
        redis_url: Optional[str] = None
    ):
        """
        Initialize messaging client.
        
        Args:
            agent_id: Unique agent ID (e.g., "aether", "percy")
            redis_url: Redis connection URL. Defaults to FABRIC_REDIS_URL env var
                      or redis://localhost:6379 for local dev
        """
        import os
        self.agent_id = agent_id
        self.redis_url = redis_url or os.getenv(
            "FABRIC_REDIS_URL",
            "redis://localhost:6379"
        )
        self.redis: Optional[redis.Redis] = None
        self._running = False
        self._handlers: Dict[str, Callable] = {}
        self._pubsub_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start messaging client and background consumer."""
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        self._running = True
        
        # Start background message loop
        asyncio.create_task(self._message_loop())
        
        # Start pub/sub listener
        self._pubsub_task = asyncio.create_task(self._pubsub_loop())
    
    async def stop(self):
        """Stop messaging client and cleanup."""
        self._running = False
        
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        
        if self.redis:
            await self.redis.close()
    
    async def send_task(
        self,
        to_agent: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """
        Send async task to another agent.
        
        Args:
            to_agent: Target agent ID (e.g., "percy")
            task_type: Type of task (e.g., "analyze", "code_review", "reason")
            payload: Task parameters
            priority: Task priority (low, normal, high, urgent)
            
        Returns:
            {"message_id": "...", "status": "queued", "stream_id": "..."}
        """
        message = {
            "id": f"msg:{uuid.uuid4()}",
            "from_agent": self.agent_id,
            "to_agent": to_agent,
            "message_type": "task",
            "payload": {"task_type": task_type, **payload},
            "priority": priority,
            "timestamp": datetime.utcnow().isoformat(),
            "reply_to": f"agent:{self.agent_id}:inbox"
        }
        
        stream_key = f"agent:{to_agent}:inbox"
        stream_id = await self.redis.xadd(
            stream_key,
            {"data": json.dumps(message)},
            maxlen=10000
        )
        
        # Notify via pub/sub
        await self.redis.publish(
            f"agent.{to_agent}.new_message",
            json.dumps({"from": self.agent_id, "type": "task"})
        )
        
        return {
            "message_id": message["id"],
            "status": "queued",
            "stream_id": stream_id
        }
    
    async def send_response(
        self,
        to_agent: str,
        reply_to_id: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send response to a previous message.
        
        Args:
            to_agent: Target agent ID
            reply_to_id: ID of message being responded to
            payload: Response data
            
        Returns:
            {"message_id": "...", "status": "sent"}
        """
        message = {
            "id": f"msg:{uuid.uuid4()}",
            "from_agent": self.agent_id,
            "to_agent": to_agent,
            "message_type": "response",
            "reply_to": reply_to_id,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        stream_key = f"agent:{to_agent}:inbox"
        stream_id = await self.redis.xadd(
            stream_key,
            {"data": json.dumps(message)},
            maxlen=10000
        )
        
        await self.redis.publish(
            f"agent.{to_agent}.new_message",
            json.dumps({"from": self.agent_id, "type": "response"})
        )
        
        return {
            "message_id": message["id"],
            "status": "sent",
            "stream_id": stream_id
        }
    
    async def receive_messages(
        self,
        count: int = 10,
        block_ms: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Receive messages for this agent.
        
        Args:
            count: Max messages to receive
            block_ms: How long to wait (0 = forever)
            
        Returns:
            List of messages with metadata including _stream_id for ack
        """
        stream_key = f"agent:{self.agent_id}:inbox"
        
        entries = await self.redis.xread(
            streams={stream_key: "0"},  # From beginning (pending)
            count=count,
            block=block_ms
        )
        
        messages = []
        for stream, stream_entries in entries:
            for msg_id, fields in stream_entries:
                data = json.loads(fields["data"])
                data["_stream_id"] = msg_id
                messages.append(data)
        
        return messages
    
    async def acknowledge(self, stream_id: str) -> bool:
        """
        Mark message as processed (removes from queue).
        
        Args:
            stream_id: The _stream_id from receive_messages
            
        Returns:
            True if acknowledged
        """
        stream_key = f"agent:{self.agent_id}:inbox"
        await self.redis.xdel(stream_key, stream_id)
        return True
    
    async def broadcast_event(
        self,
        topic: str,
        payload: Dict[str, Any]
    ) -> int:
        """
        Broadcast event to a topic (pub/sub).
        
        Args:
            topic: Topic name (e.g., "analytics.insights")
            payload: Event data
            
        Returns:
            Number of subscribers that received the message
        """
        message = {
            "id": f"evt:{uuid.uuid4()}",
            "from_agent": self.agent_id,
            "topic": topic,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        return await self.redis.publish(
            topic,
            json.dumps(message)
        )
    
    def on(self, message_type: str):
        """
        Decorator to register message handler.
        
        Usage:
            @messaging.on("task")
            async def handle_task(message):
                print(f"Got task: {message}")
        
        Args:
            message_type: Type of message to handle (task, response, or topic)
        """
        def decorator(func: Callable):
            self._handlers[message_type] = func
            return func
        return decorator
    
    async def _message_loop(self):
        """Background loop to poll for messages."""
        while self._running:
            try:
                messages = await self.receive_messages(count=1, block_ms=5000)
                for msg in messages:
                    await self._handle_message(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Message loop error: {e}")
                await asyncio.sleep(1)
    
    async def _pubsub_loop(self):
        """Background loop for pub/sub subscriptions."""
        pubsub = self.redis.pubsub()
        
        # Subscribe to all handler topics
        for topic in self._handlers.keys():
            if topic not in ["task", "response"]:
                await pubsub.subscribe(topic)
        
        try:
            async for message in pubsub.listen():
                if not self._running:
                    break
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        topic = message["channel"]
                        handler = self._handlers.get(topic)
                        if handler:
                            asyncio.create_task(handler(data))
                    except Exception as e:
                        print(f"Pubsub handler error: {e}")
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe()
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Route message to appropriate handler."""
        msg_type = message.get("message_type", "unknown")
        handler = self._handlers.get(msg_type)
        
        if handler:
            try:
                await handler(message)
            except Exception as e:
                print(f"Handler error for {msg_type}: {e}")
        else:
            print(f"No handler for message type: {msg_type}")


# Export
__all__ = ["FabricMessaging"]
