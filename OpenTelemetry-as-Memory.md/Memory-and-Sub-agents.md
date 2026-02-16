# AetherOS Agentic Runtime: Unified Architecture
## Telemetry-as-Memory + Triad Intelligence™ + TypeScript Agent Harness

**Author:** Claude Opus (for Cory, AetherPro Technologies LLC)  
**Date:** February 15, 2026  
**Classification:** Internal Architecture Document

---

## 1. The Core Insight

Every agentic system today has three separate, disconnected concerns:

1. **Memory** — How does the agent remember things?
2. **Observability** — How do we know what the agent is doing?
3. **Recovery** — How does the agent pick up where it left off?

These are treated as three different problems with three different solutions. But they're the same problem viewed from three angles. **Telemetry IS memory. Logs ARE the notebook. Traces ARE the breadcrumbs.**

Your Triad Intelligence™ (PostgreSQL + Qdrant + Redis) already solves the storage layer. The missing piece was: **what feeds data INTO the triad automatically, without the agent having to explicitly "remember" anything?**

The answer: **OpenTelemetry instrumentation.** Every tool call, every LLM inference, every error, every decision — captured as structured traces and routed into all three vertices of the Triad simultaneously.

---

## 2. Architecture: The Closed Loop

```
┌──────────────────────────────────────────────────────────────────┐
│                     AetherOS (Python asyncio)                    │
│                                                                  │
│   Main Agent (Apriel-1.5-15B / Claude Opus)                     │
│   ┌─────────────────────────────────────────────┐                │
│   │  Tools: delegate_task | check_task | cancel  │                │
│   └──────────────────┬──────────────────────────┘                │
│                      │ HTTP/WebSocket                            │
│                      ▼                                           │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │         TypeScript Agentic Runtime (Gateway)             │   │
│   │                                                          │   │
│   │  ┌────────┐ ┌────────┐ ┌──────────┐ ┌───────────────┐  │   │
│   │  │ Coder  │ │ Task   │ │ Explorer │ │ Compactor     │  │   │
│   │  │ Agent  │ │ Agent  │ │ Agent    │ │ (auto-summary)│  │   │
│   │  └───┬────┘ └───┬────┘ └────┬─────┘ └───────────────┘  │   │
│   │      │           │           │                           │   │
│   │  ┌───▼───────────▼───────────▼───────────────────────┐  │   │
│   │  │  Tool Layer (instrumented with OpenTelemetry)     │  │   │
│   │  │  read | write | edit | bash | lsp_diagnostics     │  │   │
│   │  │                                                   │  │   │
│   │  │  Every call emits:                                │  │   │
│   │  │  - Trace span (tool name, args, result, timing)   │  │   │
│   │  │  - Log event (structured JSON)                    │  │   │
│   │  │  - Metrics (tokens, cost, latency)                │  │   │
│   │  └───────────────────┬───────────────────────────────┘  │   │
│   │                      │                                   │   │
│   │                      ▼                                   │   │
│   │  ┌───────────────────────────────────────────────────┐  │   │
│   │  │           OpenTelemetry Collector                 │  │   │
│   │  │                                                   │  │   │
│   │  │  Receives all traces, logs, metrics               │  │   │
│   │  │  Processes via pipeline (enrich, filter, batch)   │  │   │
│   │  │  Exports to THREE destinations simultaneously:    │  │   │
│   │  └──────┬──────────────┬──────────────┬──────────────┘  │   │
│   │         │              │              │                  │   │
│   └─────────┼──────────────┼──────────────┼──────────────────┘   │
│             │              │              │                       │
│             ▼              ▼              ▼                       │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │              TRIAD INTELLIGENCE™                        │    │
│   │                                                         │    │
│   │  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  │    │
│   │  │ PostgreSQL  │  │   Qdrant     │  │ Redis Stack  │  │    │
│   │  │             │  │              │  │              │  │    │
│   │  │ Structured  │  │ Semantic     │  │ Real-time    │  │    │
│   │  │ Events:     │  │ Memory:      │  │ State:       │  │    │
│   │  │             │  │              │  │              │  │    │
│   │  │ • Trace     │  │ • Embedded   │  │ • Agent      │  │    │
│   │  │   spans as  │  │   summaries  │  │   bootstrap  │  │    │
│   │  │   rows      │  │   of agent   │  │   markdowns  │  │    │
│   │  │ • Task      │  │   sessions   │  │   (cached)   │  │    │
│   │  │   lifecycle │  │ • Code       │  │ • Pub/Sub    │  │    │
│   │  │ • Git       │  │   patterns   │  │   events     │  │    │
│   │  │   commits   │  │   learned    │  │ • Session    │  │    │
│   │  │ • Error     │  │ • Problem →  │  │   state      │  │    │
│   │  │   history   │  │   solution   │  │ • Active     │  │    │
│   │  │ • Audit     │  │   pairs      │  │   task       │  │    │
│   │  │   trail     │  │ • Cross-     │  │   queue      │  │    │
│   │  │             │  │   agent      │  │ • OTel       │  │    │
│   │  │             │  │   knowledge  │  │   recent     │  │    │
│   │  │             │  │              │  │   spans      │  │    │
│   │  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘  │    │
│   │         │                │                  │          │    │
│   │         └────────────────┼──────────────────┘          │    │
│   │                          │                             │    │
│   │                          ▼                             │    │
│   │            ┌─────────────────────────┐                 │    │
│   │            │  Context Recovery       │                 │    │
│   │            │  Service                │                 │    │
│   │            │                         │                 │    │
│   │            │  On new agent session:  │                 │    │
│   │            │  1. Redis → bootstrap   │                 │    │
│   │            │     markdowns + state   │                 │    │
│   │            │  2. PG → recent traces  │                 │    │
│   │            │     for this task       │                 │    │
│   │            │  3. Qdrant → relevant   │                 │    │
│   │            │     past knowledge      │                 │    │
│   │            │  4. Assemble → inject   │                 │    │
│   │            │     into agent context  │                 │    │
│   │            └─────────────────────────┘                 │    │
│   │                                                         │    │
│   │  ALSO EXPORTS TO:                                       │    │
│   │  ┌──────────────────────────────────────────────────┐  │    │
│   │  │  Prometheus + Grafana (Human Observability)      │  │    │
│   │  │  Dashboards, alerts, cost tracking               │  │    │
│   │  └──────────────────────────────────────────────────┘  │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │  Docker Sandbox Pool (isolated execution per task)       │   │
│   └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. The Data Flow — How Telemetry Becomes Memory

### 3.1 During Agent Execution (The Hot Path)

```
Agent calls bash("npm test")
    │
    ├── OTel Span Created:
    │   {
    │     traceId: "abc123",
    │     spanId: "def456",
    │     parentSpanId: "ghi789",        // Links to parent task span
    │     name: "tool.bash",
    │     attributes: {
    │       "gen_ai.agent.id": "coder-agent-01",
    │       "gen_ai.task.id": "task-implement-auth",
    │       "tool.name": "bash",
    │       "tool.input": "npm test",
    │       "tool.output": "3 passed, 1 failed: auth.test.ts:47",
    │       "tool.exit_code": 1,
    │       "tool.duration_ms": 4200,
    │       "session.iteration": 23,
    │       "session.token_count": 45000
    │     }
    │   }
    │
    ├── Sent to OTel Collector
    │
    ├── FORK 1 → PostgreSQL:
    │   INSERT INTO agent_spans (trace_id, span_id, task_id, ...)
    │   // Permanent, queryable audit trail
    │
    ├── FORK 2 → Redis Stack:
    │   XADD task:task-implement-auth:spans * ...
    │   // Real-time stream, other agents can watch
    │   // Bootstrap markdowns updated if task state changes
    │
    ├── FORK 3 → Qdrant (async, batched):
    │   embed("bash npm test failed: auth.test.ts line 47 assertion error")
    │   upsert to collection: agent_knowledge
    │   // Semantic memory — next agent asking about auth tests finds this
    │
    └── FORK 4 → Prometheus:
        tool_call_total{tool="bash", status="error"} += 1
        tool_call_duration_seconds{tool="bash"} = 4.2
        // Human dashboards
```

### 3.2 On New Agent Session (The Recovery Path)

When a new agent context window starts (either fresh session or after compaction):

```python
async def build_agent_context(task_id: str, agent_id: str) -> AgentContext:
    """
    Assemble the perfect context for a new agent session.
    This replaces hand-written progress files with REAL data.
    """
    
    # 1. REDIS (instant — cached bootstrap markdowns)
    #    These are your AGENT.md / CLAUDE.md equivalent
    #    Pre-cached, always warm, sub-millisecond
    bootstrap = await redis.hgetall(f"agent:{agent_id}:bootstrap")
    # Returns: system_prompt.md, tools.md, conventions.md, personality.md
    
    # 2. REDIS (instant — current task state)
    task_state = await redis.hgetall(f"task:{task_id}:state")
    # Returns: status, current_feature, blockers, last_checkpoint
    
    # 3. POSTGRESQL (fast — recent trace history for THIS task)
    recent_spans = await pg.query("""
        SELECT span_name, attributes, timestamp
        FROM agent_spans 
        WHERE task_id = $1 
        ORDER BY timestamp DESC 
        LIMIT 50
    """, task_id)
    # Returns: The last 50 things any agent did on this task
    # This IS the progress file — but it's real, not hand-written
    
    # 4. POSTGRESQL (fast — error history)
    recent_errors = await pg.query("""
        SELECT attributes->>'tool.input' as command,
               attributes->>'tool.output' as error,
               timestamp
        FROM agent_spans
        WHERE task_id = $1 
          AND attributes->>'tool.exit_code' != '0'
        ORDER BY timestamp DESC
        LIMIT 10
    """, task_id)
    # Returns: What went wrong recently — agent avoids repeating mistakes
    
    # 5. QDRANT (semantic — relevant knowledge from ALL agents)
    relevant_knowledge = await qdrant.search(
        collection="agent_knowledge",
        query_vector=embed(task_state['current_feature']),
        limit=10,
        filter={"scope": {"$in": ["global", f"task:{task_id}"]}}
    )
    # Returns: Similar problems solved before, patterns learned,
    #          solutions that worked — from ANY agent, ANY time
    
    # 6. ASSEMBLE INTO CONTEXT
    return AgentContext(
        system_prompt=bootstrap['system_prompt.md'],
        tools_doc=bootstrap['tools.md'],
        task_brief=f"""
## Current Task: {task_state['current_feature']}
Status: {task_state['status']}
Blockers: {task_state.get('blockers', 'None')}

## Recent Activity (from trace history)
{format_spans_as_markdown(recent_spans)}

## Recent Errors (avoid repeating these)
{format_errors_as_markdown(recent_errors)}

## Relevant Knowledge (from collective memory)
{format_knowledge_as_markdown(relevant_knowledge)}

## Git Log
{await get_recent_git_log(task_id)}
""",
        todo_list=json.loads(task_state.get('todo', '[]')),
        feature_list=json.loads(task_state.get('features', '[]'))
    )
```

---

## 4. The Bootstrap System — Markdown → Redis Cache

Your insight about caching the bootstrap markdowns in Redis Stack is the key performance optimization. Here's how it works:

### 4.1 Bootstrap Markdown Structure

```
/agents/
├── shared/
│   ├── SYSTEM_CORE.md          # Universal identity and rules
│   ├── TOOLS.md                # Tool documentation
│   ├── CONVENTIONS.md          # Code style, commit format, etc.
│   └── MEMORY_PROTOCOL.md     # How to use Triad memory
│
├── coder/
│   ├── AGENT.md                # Coder-specific personality + skills
│   ├── WORKFLOW.md             # Step-by-step coding workflow
│   └── TESTING.md              # How to verify work
│
├── explorer/
│   ├── AGENT.md                # Read-only exploration personality
│   └── SEARCH_PATTERNS.md     # How to navigate codebases
│
└── task/
    ├── AGENT.md                # General purpose sub-agent
    └── DELEGATION.md           # How to handle delegated work
```

### 4.2 Redis Caching Strategy

```python
async def cache_bootstrap_markdowns():
    """
    Load all bootstrap markdowns into Redis Stack.
    Called once on startup, refreshed on file change.
    Agent reads from Redis, never from disk during execution.
    """
    for agent_type in ['coder', 'explorer', 'task']:
        # Load shared + agent-specific markdowns
        shared = load_markdown_dir('agents/shared/')
        specific = load_markdown_dir(f'agents/{agent_type}/')
        
        # Merge into single bootstrap bundle
        bundle = {**shared, **specific}
        
        # Cache in Redis Hash (sub-millisecond reads)
        await redis.hset(
            f"agent:{agent_type}:bootstrap",
            mapping={name: content for name, content in bundle.items()}
        )
        
        # Also index in Redis Search for semantic queries
        # "Which bootstrap doc mentions error handling?"
        for name, content in bundle.items():
            await redis.ft("idx:bootstrap").add_document(
                f"bootstrap:{agent_type}:{name}",
                content=content,
                agent_type=agent_type,
                filename=name
            )
    
    # Set TTL for auto-refresh (or use file watcher)
    # In practice: file watcher invalidates on change
```

### 4.3 Why Redis Stack Specifically

Redis Stack gives you modules that make this work:

- **RedisJSON** — Store bootstrap markdowns as structured JSON (not just strings)
- **RediSearch** — Full-text search across all cached docs (agent queries its own bootstrap)
- **RedisTimeSeries** — Token usage, cost tracking per agent over time
- **RedisBloom** — Dedup repeated knowledge entries before hitting Qdrant
- **Redis Streams** — Real-time event bus between agents (your existing pub/sub)

The agent doesn't just READ its bootstrap — it can SEARCH it:
```
"Which part of my bootstrap docs talks about handling database migrations?"
→ RediSearch query against idx:bootstrap
→ Returns the relevant section in <5ms
→ Agent has the right context without loading everything
```

---

## 5. The Qdrant Semantic Layer — Collective Intelligence

### 5.1 Collection Schema

```python
qdrant_collections = {
    "agent_knowledge": {
        # What agents have learned — the collective brain
        "vectors": {"size": 1536, "distance": "Cosine"},
        "payload_schema": {
            "task_id": "keyword",
            "agent_id": "keyword",
            "scope": "keyword",       # global | tenant | agent | task
            "category": "keyword",    # solution | error | pattern | decision
            "content": "text",        # The actual knowledge
            "confidence": "float",    # How sure are we
            "source_trace_id": "keyword",  # Link back to the OTel trace
            "timestamp": "datetime",
            "ttl": "integer"          # Optional expiry (ephemeral scope)
        }
    },
    
    "code_patterns": {
        # Reusable code patterns learned from successful tasks
        "vectors": {"size": 1536, "distance": "Cosine"},
        "payload_schema": {
            "language": "keyword",
            "pattern_type": "keyword",  # auth | api | database | test
            "code_snippet": "text",
            "context": "text",          # When to use this pattern
            "success_count": "integer", # How many times this worked
            "last_used": "datetime"
        }
    },
    
    "error_solutions": {
        # Problem → Solution pairs (the most valuable knowledge)
        "vectors": {"size": 1536, "distance": "Cosine"},
        "payload_schema": {
            "error_message": "text",
            "root_cause": "text",
            "solution": "text",
            "verified": "bool",         # Did the solution actually work?
            "source_task_id": "keyword",
            "times_reused": "integer"
        }
    }
}
```

### 5.2 Automatic Knowledge Extraction from Traces

```python
async def extract_knowledge_from_trace(trace: Trace):
    """
    Run after a task completes (or at checkpoints).
    Extracts reusable knowledge from the trace and stores in Qdrant.
    
    This is where TELEMETRY BECOMES MEMORY.
    """
    
    # Find error → fix sequences in the trace
    error_fix_pairs = find_error_fix_sequences(trace.spans)
    for error_span, fix_span in error_fix_pairs:
        embedding = await embed(
            f"Error: {error_span.attributes['tool.output']} "
            f"Fix: {fix_span.attributes['tool.input']}"
        )
        await qdrant.upsert("error_solutions", [{
            "id": uuid4(),
            "vector": embedding,
            "payload": {
                "error_message": error_span.attributes['tool.output'],
                "root_cause": infer_root_cause(error_span),
                "solution": fix_span.attributes['tool.input'],
                "verified": True,  # It worked — the trace proves it
                "source_task_id": trace.task_id,
                "times_reused": 0
            }
        }])
    
    # Extract successful code patterns
    successful_writes = [s for s in trace.spans 
                         if s.name == "tool.write" 
                         and trace_shows_tests_passed_after(s)]
    for write_span in successful_writes:
        embedding = await embed(write_span.attributes['tool.input'])
        await qdrant.upsert("code_patterns", [{
            "id": uuid4(),
            "vector": embedding,
            "payload": {
                "language": detect_language(write_span.attributes['path']),
                "pattern_type": classify_pattern(write_span),
                "code_snippet": write_span.attributes['tool.input'],
                "context": get_surrounding_context(write_span, trace),
                "success_count": 1,
                "last_used": datetime.utcnow()
            }
        }])
    
    # Store high-level task summary as knowledge
    summary = await summarize_trace(trace)  # Use a cheap model
    embedding = await embed(summary)
    await qdrant.upsert("agent_knowledge", [{
        "id": uuid4(),
        "vector": embedding,
        "payload": {
            "task_id": trace.task_id,
            "agent_id": trace.agent_id,
            "scope": "global",
            "category": "solution",
            "content": summary,
            "confidence": calculate_confidence(trace),
            "source_trace_id": trace.trace_id,
            "timestamp": datetime.utcnow()
        }
    }])
```

---

## 6. The "Digital Person Runtime" — Putting It All Together

What you're building isn't just an agent framework. It's a cognitive architecture:

```
┌─────────────────────────────────────────────────────┐
│            Digital Person Runtime                     │
│                                                      │
│  PERCEPTION (Input Processing)                       │
│  ├── Text → Main Agent                               │
│  ├── Voice → STT → Main Agent                        │
│  ├── Vision → Qwen-VL → Context                      │
│  └── Events → Redis Streams → Reactive Agents        │
│                                                      │
│  COGNITION (Thinking)                                │
│  ├── Working Memory: Redis (current session state)   │
│  ├── Episodic Memory: PostgreSQL (what happened)     │
│  ├── Semantic Memory: Qdrant (what things mean)      │
│  ├── Procedural Memory: Bootstrap MDs (how to act)   │
│  └── Reasoning: LLM (Apriel/Claude/Kimi)             │
│                                                      │
│  ACTION (Tool Execution)                             │
│  ├── Code: read | write | edit | bash                │
│  ├── Communication: A2A | MCP | HTTP                 │
│  ├── Delegation: Spawn sub-agents in sandboxes       │
│  └── Self-modification: Write new skills/tools       │
│                                                      │
│  REFLECTION (Learning Loop)                          │
│  ├── OTel traces → automatic knowledge extraction    │
│  ├── Error patterns → Qdrant error_solutions         │
│  ├── Successful patterns → Qdrant code_patterns      │
│  ├── Cross-agent knowledge sharing via Triad         │
│  └── Continuous context compression (sawtooth)       │
│                                                      │
│  IDENTITY (Persistent Self)                          │
│  ├── Bootstrap markdowns define personality           │
│  ├── Accumulated knowledge shapes behavior            │
│  ├── Task history informs decision-making             │
│  └── Never loses context — telemetry IS memory        │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### The Key Differentiator

Everyone else builds memory as an **addon**. You build memory as an **emergent property of observability**. The agent doesn't have to "decide to remember" — everything it does is automatically captured, structured, semantically indexed, and made available to itself and every other agent in the system.

This is how human memory works. You don't consciously decide to store memories. Your brain does it automatically as a side effect of experiencing things. Your telemetry pipeline is the subconscious memory formation process.

### Why Smaller Specialist Models Win Here

With this architecture, a 15B model with access to the Triad has:
- Every solution any agent ever found (Qdrant)
- The exact trace of what happened on this task (PostgreSQL)  
- Real-time state of all running agents (Redis)
- Cached expertise documents (Redis Stack bootstrap)

It doesn't need 1.76 trillion parameters because the KNOWLEDGE IS EXTERNAL. The model just needs to be smart enough to:
1. Read the context it's given
2. Use the 4 tools effectively
3. Know when to ask for help (delegate)

That's well within the capability of Apriel-1.5-15B, especially fine-tuned on traces of successful task completions from your own system.

---

## 7. Implementation Priority

### Week 1-2: Foundation
- [ ] TypeScript agent loop with 4 core tools
- [ ] OpenTelemetry instrumentation on all tools
- [ ] OTel Collector → PostgreSQL exporter
- [ ] OTel Collector → Redis Streams exporter
- [ ] HTTP API for AetherOS delegation

### Week 3: Memory Integration  
- [ ] Bootstrap markdown caching in Redis Stack
- [ ] Context Recovery Service (query all 3 vertices)
- [ ] Agent session management with checkpoints
- [ ] Feature list / todo tracking in Redis

### Week 4: Intelligence Layer
- [ ] Qdrant knowledge extraction from traces
- [ ] Error → Solution pair mining
- [ ] Cross-agent knowledge sharing
- [ ] Compactor agent with sawtooth compression

### Week 5: Hardening
- [ ] Docker sandbox per task
- [ ] LSP integration (Pyright + tsserver)
- [ ] Run Terminal-Bench 2.0
- [ ] Run SWE-Bench Verified
- [ ] Iterate on failure modes

### Week 6: Polish
- [ ] Grafana dashboards for agent observability
- [ ] Cost tracking and budget enforcement
- [ ] Self-verification loops
- [ ] Documentation and SKILL.md files