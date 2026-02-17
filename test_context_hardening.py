import asyncio
import logging
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append("/home/cory/Documents/AGENT_HARNESSES/aether_project")

from aether.agent_runtime_v2 import AgentRuntimeV2, AgentState

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_context")

class TestContextHardening(unittest.IsolatedAsyncioTestCase):
    async def test_warning_and_checkpoint(self):
        # Setup Runtime with small context limit
        runtime = AgentRuntimeV2(session_id="test_session")
        runtime._max_context_tokens = 1000  # Small limit for testing
        
        # Mock LLM and Checkpoint Engine
        runtime.llm = MagicMock()
        runtime._checkpoint_engine = MagicMock()
        runtime._checkpoint_engine.agent.distill_checkpoint = AsyncMock(return_value={
            "objective": "Test", "progress_items": [], "current_state": {}, "next_actions": []
        })
        runtime._checkpoint_engine.episodic_memory.save_checkpoint = AsyncMock(return_value={
            "id": "chk_1"
        })
        # Mock internal methods to avoid actual compression logic dependencies
        runtime._compress_context_simple = AsyncMock()
        runtime.checkpoint = AsyncMock(return_value=True)

        # 1. Test Warning (75%)
        print("\n--- Testing 75% Warning ---")
        runtime._tokens_used = 750 # 75%
        await runtime._check_and_compress_context()
        
        # Verify warning in history
        last_msg = runtime.conversation_history[-1]
        print(f"Last Message Role: {last_msg['role']}")
        print(f"Last Message Content: {last_msg['content'][:50]}...")
        
        self.assertEqual(last_msg['role'], "system")
        self.assertIn("SYSTEM WARNING", last_msg['content'])
        self.assertTrue(runtime._context_warning_sent)

        # 2. Test Auto-Checkpoint (85%)
        print("\n--- Testing 85% Auto-Checkpoint ---")
        runtime._tokens_used = 850 # 85%
        await runtime._check_and_compress_context()
        
        # Verify checkpoint called
        runtime.checkpoint.assert_called_with(objective="Auto-save: critical_threshold_reached")
        print("Auto-checkpoint triggered successfully")
        
        # Verify compression called
        runtime._compress_context_simple.assert_called_with(reason="critical_threshold")
        print("Compression triggered successfully")
        
        # Verify warning reset
        self.assertFalse(runtime._context_warning_sent)

if __name__ == "__main__":
    unittest.main()
