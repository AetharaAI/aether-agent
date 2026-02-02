'''# tests/test_aether_memory.py

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aether.aether_memory import AetherMemory, MemoryEntry, SearchResult

@pytest.fixture
def mock_redis():
    with patch("redis.asyncio.from_url", new_callable=AsyncMock) as mock_from_url:
        mock_redis_instance = AsyncMock()
        mock_from_url.return_value = mock_redis_instance
        yield mock_redis_instance

@pytest.mark.asyncio
async def test_aether_memory_initialization(mock_redis):
    """Test AetherMemory initialization and connection"""
    async with AetherMemory() as memory:
        assert memory.redis is not None
        mock_redis.ft.assert_called_with("aether:memory:search:index")

@pytest.mark.asyncio
async def test_aether_memory_log_daily(mock_redis):
    """Test logging a daily memory entry"""
    async with AetherMemory() as memory:
        await memory.log_daily("Test entry", tags=["test"])

        # Check if hset and rpush were called
        assert mock_redis.hset.call_count == 1
        assert mock_redis.rpush.call_count == 1

        hset_args = mock_redis.hset.call_args[1]
        assert hset_args['mapping']['content'] == "Test entry"
        assert "test" in hset_args['mapping']['tags']

@pytest.mark.asyncio
async def test_aether_memory_checkpoint_and_rollback(mock_redis):
    """Test memory checkpoint and rollback"""
    async with AetherMemory() as memory:
        # Mock data for checkpoint
        mock_redis.get.return_value = '''
        {
            "uuid": "test-uuid",
            "name": "test-checkpoint",
            "timestamp": "2026-01-31T12:00:00",
            "daily": {
                "2026-01-31": [{"content": "daily entry"}]
            },
            "longterm": {"key": "value"}
        }
        '''

        # Create a checkpoint
        checkpoint_id = await memory.checkpoint_snapshot("test_checkpoint")
        assert mock_redis.set.call_count == 1
        assert mock_redis.rpush.call_count == 1

        # Rollback to checkpoint
        success = await memory.rollback_to("test-uuid")
        assert success

        # Check if memory was restored
        assert mock_redis.set.call_count == 2 # Once for checkpoint, once for longterm restore
        assert mock_redis.delete.call_count == 1 # To clear old daily log
        assert mock_redis.rpush.call_count == 2 # Once for checkpoint list, once for daily restore

@pytest.mark.asyncio
async def test_aether_memory_semantic_search(mock_redis):
    """Test semantic search"""
    async with AetherMemory() as memory:
        # Mock search results
        mock_search_result = MagicMock()
        mock_search_result.docs = [
            MagicMock(id="doc1", content="Result 1", score=0.9, source="user", timestamp="now")
        ]
        mock_redis.ft.return_value.search.return_value = mock_search_result

        results = await memory.search_semantic("query")

        assert len(results) == 1
        assert isinstance(results[0], SearchResult)
        assert results[0].content == "Result 1"

@pytest.mark.asyncio
async def test_aether_memory_scratchpad(mock_redis):
    """Test scratchpad functionality"""
    async with AetherMemory() as memory:
        # Create a scratchpad entry
        await memory.scratchpad_new("test_pad", "scratch content", expire_h=1)
        mock_redis.set.assert_called_once_with(
            "aether:memory:scratchpad:test_pad",
            "scratch content",
            ex=3600
        )

        # Get scratchpad content
        mock_redis.get.return_value = "scratch content"
        content = await memory.scratchpad_get("test_pad")
        assert content == "scratch content"
'''
