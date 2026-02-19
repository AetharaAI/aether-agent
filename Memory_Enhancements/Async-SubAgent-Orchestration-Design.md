# Async Sub-Agent Orchestration: Design Document

> **Version**: 0.1 — February 2026
> **Status**: Design Phase
> **Author**: Cory / Aether Collaborative

---

## Problem Statement

Current agentic systems (including this IDE's browser agent) use **synchronous delegation** — the primary agent blocks while a sub-agent executes. This creates two critical UX problems:

1. **Operator lockout**: The user cannot communicate with the primary agent while the sub-agent runs
2. **No steering**: If the sub-agent goes wrong (wrong page, wrong click, wrong reasoning), the only option is to cancel and restart

## Proposed Architecture

### Non-Blocking Delegation

The primary agent (Aether) dispatches tasks to sub-agents **asynchronously** via a message bus. The primary remains available for conversation throughout. The operator can:

- Ask questions while sub-agents work
- Send corrections mid-task ("the browser agent is going to the wrong page")
- Monitor sub-agent progress in real-time
- Cancel or redirect sub-agents

### System Diagram

```
┌───────────────────────────────────────────────────────────────────┐
│                     OPERATOR (User / Cory)                       │
│                  Always talks to Primary Agent                   │
└──────────────────────────┬────────────────────────────────────────┘
                           │ WebSocket / Chat
                           ▼
┌───────────────────────────────────────────────────────────────────┐
│                  PRIMARY AGENT (Aether)                          │
│  Model: qwen3-next-instruct (L40S-180)                          │
│  Role: Conversation · Orchestration · Operator Interface         │
│  Always available — never blocks on sub-agent work              │
├──────────┬──────────┬──────────┬──────────────────────────────────┤
│          │ Orchestrator Layer                                    │
│          │  • Task dispatch (with model/provider selection)      │
│          │  • Progress monitoring                                │
│          │  • Operator steering relay                            │
│          │  • Result aggregation                                 │
│          │  • Error handling / retry                             │
├──────────┴──────────┬──────────┴──────────────────────────────────┤
│                     │ Redis Streams (Task Queue)                 │
│                     │ aether:tasks:{agent_type}:pending          │
│                     │ aether:tasks:{task_id}:status              │
│                     │ aether:tasks:{task_id}:result              │
├──────────┬──────────┴──────────┬──────────────────────────────────┤
│ Browser  │  Vision Agent       │  Reasoning Agent                │
│ Agent    │  (minicpm-v-4.5)    │  (nanbeige4-3b)                 │
│ (any)    │  L40S-90            │  L40S-90                        │
│          │                     │                                 │
│ Web nav  │  OCR, screenshot    │  Deep analysis                  │
│ Form fill│  analysis, form     │  Long CoT                       │
│ Scraping │  field reading      │  Multi-step reasoning           │
└──────────┴─────────────────────┴──────────────────────────────────┘
     ▲              ▲                     ▲
     └──────────────┴─────────────────────┘
         All via LiteLLM Provider Routing
         Hot-swap model/provider per task
```

### Communication Flow

```
OPERATOR: "Go to example.com and fill in the contact form"
    │
    ▼
PRIMARY AGENT:
    1. Creates task: {type: "browser", model: "qwen3-next-instruct",
                      instruction: "Navigate to example.com, fill contact form"}
    2. Publishes to Redis Stream: aether:tasks:browser:pending
    3. Responds to operator: "Dispatched to browser agent. I'm still here."
    │
    ▼
BROWSER SUB-AGENT (separate process/coroutine):
    1. Pulls task from stream
    2. Begins browser automation loop
    3. Posts status updates: "Navigating to example.com..."
    4. Posts status updates: "Found contact form, filling fields..."
    │
    ├──── Meanwhile, OPERATOR talks to PRIMARY:
    │     OPERATOR: "Actually use my work email, not personal"
    │     PRIMARY: Sends correction to sub-agent via Redis:
    │              aether:tasks:{task_id}:steering
    │
    5. Sub-agent reads steering message, adjusts behavior
    6. Posts result: "Form submitted successfully"
    │
    ▼
PRIMARY AGENT:
    1. Reads result from Redis Stream
    2. Reports to operator: "Browser agent completed the form submission"
```

### Key Infrastructure Advantages (Already Built)

| Component | How It Enables This | Status |
|---|---|---|
| **LiteLLM Provider Routing** | Any sub-agent can use any model from any provider | ✅ Production |
| **Hot-Swap** | Change model mid-run without restart | ✅ Production |
| **Redis Stack** | Task queue (Streams), shared memory, status tracking | ✅ Production |
| **GPU Partitioning** | Each model gets dedicated hardware, no contention | ✅ Running |
| **Provider Registry** | Runtime knows all available models + endpoints | ✅ Production |

### Model-Task Mapping (Current Fleet)

| Model | Hardware | Best For | Provider |
|---|---|---|---|
| `qwen3-next-instruct` | L40S-180 (2×48GB) | Primary reasoning, orchestration | litellm-2 |
| `minicpm-v-4.5` | L40S-90 (1×48GB) | Vision/OCR, screenshots, form reading | litellm-2 |
| `nanbeige4-3b-thinking` | L40S-90 (1×48GB) | Long CoT, deep analysis, planning | litellm-2 |
| *L4-360 (4×24GB)* | *Not yet assigned* | *Embeddings, rerankers, additional models* | *TBD* |
| External APIs | N/A | Fallback, specialized tasks | litellm (primary) |

### Components To Build

#### 1. Task Queue (Redis Streams)
- Uses Redis Streams (already have Redis Stack)
- Persistent, ordered, with consumer groups
- Key patterns: `aether:tasks:{type}:pending`, `aether:tasks:{id}:status`, `aether:tasks:{id}:result`, `aether:tasks:{id}:steering`

#### 2. Sub-Agent Runtime
- Lighter version of `AgentRuntimeV2`
- Takes: task description + model assignment + tool subset
- Runs its own tool loop (browser, vision, file operations)
- Reports status back via Redis Streams
- Reads steering messages mid-execution
- Returns structured result on completion

#### 3. Orchestrator Layer (in Primary Agent)
- `dispatch_task(type, instruction, model, tools)` — creates task, selects model
- `check_task_status(task_id)` — polls Redis for updates
- `steer_task(task_id, correction)` — sends mid-execution correction
- `cancel_task(task_id)` — terminates sub-agent
- `get_task_result(task_id)` — retrieves final output

### Why This Is Unique

1. **Model diversity per task** — Pick the right brain for each job
2. **Non-blocking** — Operator never loses the primary agent
3. **Hot-swap** — If a model performs poorly, switch it without restart
4. **Shared memory** — Sub-agents share context through Redis
5. **Operator steering** — Correct sub-agents mid-task via the primary
6. **Provider agnostic** — Self-hosted, OpenAI, Anthropic, Google — all through one routing layer

---

## Implementation Priority

This feature is **Phase 2** — after the Memory Convergence features are completed. The convergence features (vector embeddings, temporal decay, MMR, agentic flush) directly improve the shared memory substrate that sub-agents will depend on.

### Estimated Timeline
- **Phase 1**: Memory Convergence (current)
- **Phase 2**: Single sub-agent vertical slice (vision agent with minicpm-v-4.5)
- **Phase 3**: Multi-agent orchestration with N agents
