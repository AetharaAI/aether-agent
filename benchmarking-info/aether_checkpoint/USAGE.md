# AetherCheckpoint — Usage Guide

## Installation

```bash
cd benchmarking-info
pip install -e ./aether_checkpoint

# With production backends:
pip install -e "./aether_checkpoint[all]"
```

## Quick Start (File-Based, No Dependencies)

```python
from aether_checkpoint import CheckpointEngine, MemoryConfig

class MyAgent:
    """Implement these 3 methods to plug into the engine."""

    def decide_action(self, system_prompt: str, messages: list[dict]) -> dict:
        # Your LLM call goes here. Return shape:
        return {
            "tool": "shell_exec",       # or "__DONE__" when finished
            "input": {"cmd": "ls -la"},
            "reasoning": "Checking directory contents",
            "tokens_used": 150,
        }

    def execute_tool(self, tool_name: str, tool_input: dict):
        # Route to your actual tool implementations
        if tool_name == "shell_exec":
            import subprocess
            return subprocess.run(tool_input["cmd"], shell=True, capture_output=True, text=True).stdout
        return f"Unknown tool: {tool_name}"

    def distill_checkpoint(self, objective: str, working_memory_text: str, previous_checkpoint=None) -> dict:
        # Compress working memory into structured state
        # This can be an LLM call or rule-based extraction
        return {
            "objective": objective,
            "progress": ["Listed directory contents"],
            "state": {"files_found": 42},
            "next_action": "Process the files",
            "dependencies": [],
            "errors": [],
        }


# Run with defaults (file-based storage, 10+1+1 pattern)
config = MemoryConfig()
engine = CheckpointEngine(agent=MyAgent(), config=config)
result = engine.run("Deploy the Docker stack")

print(f"Completed in {result.episode_number} episodes, {result.total_tool_calls} tool calls")
```

## Auto-Configure by Model

```python
# Automatically calculates optimal episode length from context window
config = MemoryConfig.for_model("kimi-k2")          # 128K → ~97 steps/episode
config = MemoryConfig.for_model("mistral-7b")        # 32K  → ~24 steps/episode
config = MemoryConfig.for_model("claude-sonnet-4-5")       # 200K → 50 steps/episode (capped)
```

## Production Backends

```python
from aether_checkpoint import MemoryConfig, StorageBackend

config = MemoryConfig(
    working_memory_backend=StorageBackend.REDIS,
    episodic_memory_backend=StorageBackend.POSTGRES,
    semantic_memory_backend=StorageBackend.WEAVIATE,
    redis_url="redis://localhost:6379/0",
    postgres_url="postgresql://localhost:5432/aether_checkpoints",
    weaviate_url="http://localhost:8080",
)
```

## Crash Recovery

```python
# Resume from the latest checkpoint
engine.resume()

# Resume from a specific checkpoint
engine.resume(checkpoint_id="chkpt_abc123")
```

## LLM-Powered Distillation

Instead of rule-based checkpoints, use the LLM to summarize:

```python
from aether_checkpoint import Checkpointer, LLMDistillation

async def my_llm(prompt: str) -> str:
    # Your LLM call
    response = await client.chat.completions.create(
        model="kimi-k2",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

distiller = LLMDistillation(llm_callable=my_llm)
checkpointer = Checkpointer(
    episodic_memory=engine.episodic_memory,
    strategy=distiller,
)
```

## Event Monitoring

```python
def on_event(event):
    print(f"[Episode {event.episode}] {event.event_type}: {event.data}")

engine = CheckpointEngine(
    agent=MyAgent(),
    config=config,
    on_event=on_event,
)
```

## File Structure

```
aether_checkpoint/
├── __init__.py          # Public API (16 exports)
├── config.py            # MemoryConfig, StorageBackend, CheckpointTrigger
├── checkpoint.py        # Checkpoint data model + CheckpointManager
├── checkpointer.py      # Advanced: LLM/Rule distillation strategies
├── memory.py            # 3-layer memory (Working, Episodic, Semantic)
├── backends.py          # Production adapters (Redis, Postgres, Weaviate)
├── loop.py              # ExecutionLoop + AgentProtocol interface
├── engine.py            # CheckpointEngine orchestrator
├── prompts.py           # Distillation prompt templates
├── pyproject.toml       # Package metadata
├── README.md            # Architecture overview
├── USAGE.md             # This file
├── INTEGRATION.md       # AetherOS integration guide
└── examples/
    ├── example_usage.py           # Simulated agent demo
    ├── integration_template.py    # Real LLM agent template
    └── integration_patterns.py    # Additional patterns
```
