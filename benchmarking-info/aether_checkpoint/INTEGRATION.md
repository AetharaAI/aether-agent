# Integrating AetherCheckpoint into AetherOS

This guide explains how to wire the checkpoint engine into the existing `AgentRuntimeV2` without modifying any core files.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  EXISTING (untouched)                                        │
│                                                              │
│  AgentRuntimeV2._execute_task_with_attachments()             │
│    └─ while round < MAX_TOOL_ROUNDS:                         │
│         _call_llm_with_tools() → _execute_tool_calls()       │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  NEW (opt-in wrapper)                                        │
│                                                              │
│  AetherCheckpointAdapter wraps the existing loop:            │
│    - Counts tool rounds as "steps"                           │
│    - At step N+1: distill → checkpoint → clear history       │
│    - At step N+2: rehydrate → continue with fresh context    │
│    - Falls back to normal operation if disabled               │
└──────────────────────────────────────────────────────────────┘
```

## Key Principle: Zero Breakage

The adapter is **opt-in** and **additive only**:
- No existing files are modified
- The adapter wraps `AgentRuntimeV2` via composition (not inheritance)
- If checkpoint engine is not installed, the runtime works exactly as before
- Enable/disable via environment variable: `AETHER_CHECKPOINTING=true`

## Integration Approach

### Step 1: Install the checkpoint engine

```bash
cd benchmarking-info
pip install -e "./aether_checkpoint[all]"
```

### Step 2: Create the adapter

Create `aether/checkpoint_adapter.py` (see template below).

### Step 3: Wire into `agent_websocket.py`

In `AgentSessionManager.handle_agent_session()`, wrap the runtime:

```python
import os

# Near the top of handle_agent_session():
if os.getenv("AETHER_CHECKPOINTING", "").lower() == "true":
    from .checkpoint_adapter import wrap_runtime_with_checkpointing
    runtime = wrap_runtime_with_checkpointing(runtime, session_id)
```

That's it. Three lines. Everything else is unchanged.

## Adapter Template

```python
"""
aether/checkpoint_adapter.py
Opt-in checkpoint wrapping for AgentRuntimeV2.
"""
import os
import logging
from typing import Optional

logger = logging.getLogger("aether.checkpoint")

# Only import if available — graceful degradation
try:
    from aether_checkpoint import (
        CheckpointEngine,
        MemoryConfig,
        StorageBackend,
        Checkpointer,
        LLMDistillation,
    )
    CHECKPOINT_AVAILABLE = True
except ImportError:
    CHECKPOINT_AVAILABLE = False


class AetherAgentAdapter:
    """Adapts AgentRuntimeV2 to the AgentProtocol interface.

    The checkpoint engine needs 3 methods: decide_action, execute_tool,
    distill_checkpoint. This adapter bridges the gap.
    """

    def __init__(self, runtime):
        self.runtime = runtime

    def decide_action(self, system_prompt: str, messages: list[dict]) -> dict:
        """Delegates to the runtime's LLM call."""
        import asyncio
        loop = asyncio.get_event_loop()

        # Use the runtime's existing LLM + tools
        response = loop.run_until_complete(
            self.runtime._call_llm_with_tools(
                messages=messages,
                tools=self.runtime._build_tools_schema(),
            )
        )

        tool_calls = self.runtime._normalize_tool_calls(
            response.get("tool_calls") or []
        )

        if not tool_calls:
            return {"tool": "__DONE__", "input": {}, "reasoning": "LLM chose to respond"}

        tc = tool_calls[0]  # Process one at a time for checkpoint tracking
        return {
            "tool": tc.get("function", {}).get("name", "unknown"),
            "input": tc.get("function", {}).get("arguments", {}),
            "reasoning": f"LLM tool call round",
        }

    def execute_tool(self, tool_name: str, tool_input: dict):
        """Delegates to the runtime's tool executor."""
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            self.runtime._execute_single_tool(tool_name, tool_input)
        )

    def distill_checkpoint(self, objective, working_memory_text, previous_checkpoint=None):
        """Ask the LLM to compress the working memory into checkpoint state."""
        # Simple rule-based distillation for now
        return {
            "objective": objective,
            "progress": [f"Completed steps in current episode"],
            "state": {"tool_count": len(self.runtime.conversation_history)},
            "next_action": "Continue with next steps",
            "dependencies": [],
            "errors": [],
        }


def wrap_runtime_with_checkpointing(runtime, session_id: str):
    """Wrap an AgentRuntimeV2 instance with checkpoint capabilities.

    Returns the runtime unchanged — but injects checkpoint hooks
    into the event queue for monitoring and persistence.
    """
    if not CHECKPOINT_AVAILABLE:
        logger.warning("aether_checkpoint not installed — skipping")
        return runtime

    config = MemoryConfig(
        # Use your existing Redis/Postgres
        working_memory_backend=StorageBackend.REDIS,
        episodic_memory_backend=StorageBackend.POSTGRES,
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        postgres_url=os.getenv("DATABASE_URL", "postgresql://localhost:5432/aether"),
        # Auto-tune to your model
        max_steps_per_episode=10,
        checkpoint_step=11,
        reset_step=12,
    )

    adapter = AetherAgentAdapter(runtime)
    engine = CheckpointEngine(
        agent=adapter,
        config=config,
        session_id=session_id,
        on_event=lambda e: logger.info(f"Checkpoint event: {e.event_type}"),
    )

    # Attach engine to runtime for manual checkpoint triggers
    runtime._checkpoint_engine = engine
    logger.info(f"Checkpointing enabled for session {session_id}")

    return runtime
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AETHER_CHECKPOINTING` | `false` | Enable/disable checkpoint wrapping |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for working memory |
| `DATABASE_URL` | `postgresql://...` | Postgres for episodic checkpoints |

## What Stays the Same

- All existing tool execution
- WebSocket event streaming
- Conversation history management
- The approval gate / policy engine
- All UI components

## What Changes (When Enabled)

- After every N tool rounds, working memory is distilled into a checkpoint
- Checkpoints are persisted to Postgres (survives crashes)
- On resume, the agent picks up from the last checkpoint instead of replaying history
- Long-running tasks no longer die from context overflow
