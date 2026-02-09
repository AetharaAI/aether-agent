"""
Tests for Fabric MCP Integration

Tests both FabricClient (HTTP tool calls) and FabricMessaging (Redis A2A).
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
import aiohttp

# Import modules to test
import sys
sys.path.insert(0, "..")

from aether.fabric_client import FabricClient, FabricConfig, FabricError
from aether.fabric_messaging import FabricMessaging


class TestFabricConfig:
    """Test FabricConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = FabricConfig()
        assert config.base_url == "https://fabric.perceptor.us"
        assert config.auth_token == "dev-shared-secret"
        assert config.timeout_ms == 60000
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = FabricConfig(
            base_url="http://localhost:8080",
            auth_token="custom-token",
            timeout_ms=30000
        )
        assert config.base_url == "http://localhost:8080"
        assert config.auth_token == "custom-token"
        assert config.timeout_ms == 30000
    
    @patch.dict("os.environ", {
        "FABRIC_BASE_URL": "http://env-url.com",
        "FABRIC_AUTH_TOKEN": "env-token",
        "FABRIC_TIMEOUT_MS": "45000"
    })
    def test_from_env(self):
        """Test loading from environment variables."""
        config = FabricConfig.from_env()
        assert config.base_url == "http://env-url.com"
        assert config.auth_token == "env-token"
        assert config.timeout_ms == 45000


class TestFabricClient:
    """Test FabricClient HTTP calls."""
    
    @pytest.fixture
    async def client(self):
        """Create client fixture."""
        config = FabricConfig(
            base_url="http://test.fabric.local",
            auth_token="test-token"
        )
        client = FabricClient(config)
        await client.__aenter__()
        yield client
        await client.__aexit__(None, None, None)
    
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health check endpoint."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"status": "healthy"}
        
        with patch.object(client._session, "get", return_value=mock_response) as mock_get:
            result = await client.health_check()
            assert result["status"] == "healthy"
            mock_get.assert_called_once_with("http://test.fabric.local/health")
    
    @pytest.mark.asyncio
    async def test_call_tool_success(self, client):
        """Test successful tool call."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"results": [{"title": "Test"}]}
        }
        
        with patch.object(client._session, "post", return_value=mock_response) as mock_post:
            result = await client.call_tool(
                "web.brave_search",
                "search",
                {"query": "test", "max_results": 5}
            )
            
            assert result["results"][0]["title"] == "Test"
            
            # Verify call structure
            call_args = mock_post.call_args
            assert call_args[0][0] == "http://test.fabric.local/mcp/call"
            
            payload = call_args[1]["json"]
            assert payload["name"] == "fabric.tool.call"
            assert payload["arguments"]["tool_id"] == "web.brave_search"
            assert payload["arguments"]["capability"] == "search"
    
    @pytest.mark.asyncio
    async def test_call_tool_error(self, client):
        """Test tool call error handling."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": False,
            "error": {"code": "EXECUTION_ERROR", "message": "Tool failed"}
        }
        
        with patch.object(client._session, "post", return_value=mock_response):
            with pytest.raises(FabricError) as exc_info:
                await client.call_tool("io.read_file", "read", {"path": "/bad/path"})
            
            assert exc_info.value.code == "EXECUTION_ERROR"
            assert "Tool failed" in exc_info.value.message
    
    @pytest.mark.asyncio
    async def test_search_web_convenience(self, client):
        """Test search_web convenience method."""
        with patch.object(client, "call_tool", return_value={"results": []}) as mock_call:
            await client.search_web("quantum computing", max_results=10)
            
            mock_call.assert_called_once_with(
                "web.brave_search",
                "search",
                {"query": "quantum computing", "max_results": 10, "recency_days": 7}
            )
    
    @pytest.mark.asyncio
    async def test_read_file_convenience(self, client):
        """Test read_file convenience method."""
        with patch.object(client, "call_tool", return_value={"content": "file contents"}) as mock_call:
            content = await client.read_file("/path/to/file.txt", max_lines=100)
            
            assert content == "file contents"
            mock_call.assert_called_once_with(
                "io.read_file",
                "read",
                {"path": "/path/to/file.txt", "max_lines": 100}
            )
    
    @pytest.mark.asyncio
    async def test_calculate_convenience(self, client):
        """Test calculate convenience method."""
        with patch.object(client, "call_tool", return_value={"result": 20.0}) as mock_call:
            result = await client.calculate("(2 + 3) * 4")
            
            assert result == 20.0
            mock_call.assert_called_once_with(
                "math.calculate",
                "eval",
                {"expression": "(2 + 3) * 4"}
            )


class TestFabricMessaging:
    """Test FabricMessaging Redis operations."""
    
    @pytest.fixture
    async def messaging(self):
        """Create messaging fixture with mocked Redis."""
        with patch("aether.fabric_messaging.redis.from_url") as mock_redis:
            mock_instance = AsyncMock()
            mock_redis.return_value = mock_instance
            
            messaging = FabricMessaging(agent_id="aether")
            messaging.redis = mock_instance
            yield messaging
    
    @pytest.mark.asyncio
    async def test_send_task(self, messaging):
        """Test sending task to another agent."""
        messaging.redis.xadd.return_value = "12345-0"
        messaging.redis.publish.return_value = 1
        
        result = await messaging.send_task(
            to_agent="percy",
            task_type="analyze",
            payload={"data": [1, 2, 3]},
            priority="high"
        )
        
        assert result["status"] == "queued"
        assert "message_id" in result
        assert "stream_id" in result
        
        # Verify Redis calls
        messaging.redis.xadd.assert_called_once()
        call_args = messaging.redis.xadd.call_args
        assert call_args[0][0] == "agent:percy:inbox"
        assert call_args[1]["maxlen"] == 10000
        
        messaging.redis.publish.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_response(self, messaging):
        """Test sending response."""
        messaging.redis.xadd.return_value = "12345-1"
        messaging.redis.publish.return_value = 1
        
        result = await messaging.send_response(
            to_agent="percy",
            reply_to_id="msg:abc123",
            payload={"result": "analysis complete"}
        )
        
        assert result["status"] == "sent"
        
        # Verify message structure
        call_args = messaging.redis.xadd.call_args
        data = json.loads(call_args[0][1]["data"])
        assert data["message_type"] == "response"
        assert data["reply_to"] == "msg:abc123"
    
    @pytest.mark.asyncio
    async def test_receive_messages(self, messaging):
        """Test receiving messages."""
        test_message = {
            "id": "msg:test123",
            "from_agent": "percy",
            "message_type": "task",
            "payload": {"task_type": "ping"}
        }
        
        messaging.redis.xread.return_value = [
            ("agent:aether:inbox", [("12345-0", {"data": json.dumps(test_message)})])
        ]
        
        messages = await messaging.receive_messages(count=10, block_ms=5000)
        
        assert len(messages) == 1
        assert messages[0]["from_agent"] == "percy"
        assert messages[0]["_stream_id"] == "12345-0"
    
    @pytest.mark.asyncio
    async def test_acknowledge(self, messaging):
        """Test message acknowledgment."""
        messaging.redis.xdel.return_value = 1
        
        result = await messaging.acknowledge("12345-0")
        
        assert result is True
        messaging.redis.xdel.assert_called_once_with("agent:aether:inbox", "12345-0")
    
    @pytest.mark.asyncio
    async def test_broadcast_event(self, messaging):
        """Test broadcasting event."""
        messaging.redis.publish.return_value = 3
        
        result = await messaging.broadcast_event(
            "analytics.insights",
            {"metric": "cpu_usage", "value": 85}
        )
        
        assert result == 3
        messaging.redis.publish.assert_called_once()
        
        # Verify message structure
        call_args = messaging.redis.publish.call_args
        topic = call_args[0][0]
        data = json.loads(call_args[0][1])
        assert topic == "analytics.insights"
        assert data["from_agent"] == "aether"
        assert data["topic"] == "analytics.insights"
    
    def test_on_decorator(self, messaging):
        """Test message handler decorator."""
        @messaging.on("task")
        async def task_handler(message):
            pass
        
        @messaging.on("custom_event")
        async def custom_handler(message):
            pass
        
        assert "task" in messaging._handlers
        assert "custom_event" in messaging._handlers
        assert messaging._handlers["task"] == task_handler


class TestIntegrationScenario:
    """Integration test scenarios."""
    
    @pytest.mark.asyncio
    async def test_aether_delegates_to_percy(self):
        """Test full flow: Aether delegates task to Percy."""
        # This would require actual Redis and Fabric server
        # For now, just verify the structure
        
        with patch("aether.fabric_messaging.redis.from_url"):
            messaging = FabricMessaging(agent_id="aether")
            
            received_messages = []
            
            @messaging.on("response")
            async def handle_response(message):
                received_messages.append(message)
            
            # Verify handler registered
            assert "response" in messaging._handlers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
