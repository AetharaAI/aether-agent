"""
aether/checkpoint_adapter.py
Opt-in checkpoint wrapping for AgentRuntimeV2.
"""
import os
import logging
import json
import asyncio
from typing import Optional, Dict, List, Any
import tiktoken

logger = logging.getLogger("aether.checkpoint")

# Only import if available — graceful degradation
try:
    from aether_checkpoint import (
        CheckpointEngine,
        MemoryConfig,
        StorageBackend,
        Checkpointer,
        LLMDistillation,
        InMemoryWorkingMemory,
        RedisWorkingMemory,
        FileEpisodicMemory,
        PostgresEpisodicMemory
    )
    CHECKPOINT_AVAILABLE = True
except ImportError:
    CHECKPOINT_AVAILABLE = False


class TokenCounter:
    """Helper to estimate token usage."""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except:
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def count_messages(self, messages: List[Dict[str, Any]]) -> int:
        count = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                # Multimodal content
                for item in content:
                    if item.get("type") == "text":
                        count += self.count(item.get("text", ""))
                    elif item.get("type") == "image_url":
                        count += 1000  # Conservative estimate for images
            else:
                count += self.count(str(content))
            
            # Count tool calls if present
            if "tool_calls" in msg:
                count += self.count(json.dumps(msg["tool_calls"]))
        return count


class AetherAgentAdapter:
    """Adapts AgentRuntimeV2 to the AgentProtocol interface."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.token_counter = TokenCounter()

    async def decide_action(self, system_prompt: str, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Delegates to the runtime's LLM call."""
        # Note: We assume the runtime has already been initialized with system prompt
        # but the loop might provide a new one or continuation prompt.
        
        response = await self.runtime._call_llm_with_tools(
            messages=messages,
            tools=self.runtime._build_tools_schema(),
        )

        tool_calls = self.runtime._normalize_tool_calls(
            response.get("tool_calls") or []
        )

        content = response.get("content", "")
        tokens = self.token_counter.count(content) if content else 0
        
        if not tool_calls:
            return {
                "tool": "__DONE__",
                "input": {},
                "reasoning": content,
                "tokens_used": tokens
            }

        # The engine expects one tool call at a time for fine-grained checkpointing
        tc = tool_calls[0]
        return {
            "tool": tc.name,
            "input": tc.arguments,
            "reasoning": content,
            "tokens_used": tokens + self.token_counter.count(json.dumps(tc.arguments))
        }

    async def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """Delegates to the runtime's tool executor."""
        # We need a ToolCall object to use the runtime's internal executor
        from .agent_runtime_v2 import ToolCall
        tc = ToolCall(id=f"chk_call_{os.urandom(4).hex()}", name=tool_name, arguments=tool_input)
        result_pkg = await self.runtime._execute_single_tool(tc)
        return result_pkg.get("output", "")

    async def distill_checkpoint(self, objective: str, working_memory_text: str, previous_checkpoint: Optional[str]) -> Dict[str, Any]:
        """Ask the LLM to compress the working memory into checkpoint state."""
        # Use aether.prompts logic
        from .prompts import DISTILLATION_SYSTEM_PROMPT, DISTILLATION_USER_TEMPLATE
        
        user_prompt = DISTILLATION_USER_TEMPLATE.format(
            objective=objective,
            previous_checkpoint=previous_checkpoint or "None",
            working_memory=working_memory_text
        )
        
        try:
            # Use runtime's LLM to distill
            raw_response = await self.runtime.llm.complete(
                messages=[
                    {"role": "system", "content": DISTILLATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                stream=False
            )
            content = getattr(raw_response, "content", str(raw_response))
            
            # Clean JSON from markdown fences
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            content = content.strip()
            
            data = json.loads(content)
            return data
        except Exception as e:
            logger.error(f"LLM Distillation failed: {e}. Falling back to rule-based.")
            return {
                "objective": objective,
                "progress": ["Distillation failed, continuing from last known state"],
                "state": {"error": str(e)},
                "next_action": "Retry previous steps or re-evaluate",
                "dependencies": [],
                "errors": [str(e)],
            }


def wrap_runtime_with_checkpointing(runtime, session_id: str):
    """Wrap an AgentRuntimeV2 instance with checkpoint capabilities."""
    if not CHECKPOINT_AVAILABLE:
        logger.warning("aether_checkpoint not installed — skipping")
        return runtime

    # Memory Backends
    try:
        redis_url = os.getenv("REDIS_URL") or f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/0"
        postgres_url = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
        
        working_memory = RedisWorkingMemory(redis_url, session_id)
        
        if postgres_url:
            episodic_memory = PostgresEpisodicMemory(postgres_url)
        else:
            episodic_memory = FileEpisodicMemory(storage_dir=f"./checkpoints/{session_id}")
            
        config = MemoryConfig(
            max_steps_per_episode=15,
            token_threshold=int(os.getenv("CHECKPOINT_TOKEN_THRESHOLD", "25000")), # ~80% of 32k
        )

        adapter = AetherAgentAdapter(runtime)
        engine = CheckpointEngine(
            agent=adapter,
            config=config,
            session_id=session_id,
            working_memory=working_memory,
            episodic_memory=episodic_memory,
            on_event=lambda e: logger.info(f"[Session {session_id}] Checkpoint event: {e.event_type}"),
        )

        runtime._checkpoint_engine = engine
        logger.info(f"Checkpointing enabled for session {session_id}")

    except Exception as e:
        logger.error(f"Failed to initialize checkpoint engine: {e}", exc_info=True)

    return runtime
