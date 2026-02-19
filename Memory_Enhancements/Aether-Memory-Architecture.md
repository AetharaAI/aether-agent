# Aether Memory Architecture

> **Version**: 1.0 — February 2026
> **Author**: System Documentation
> **Status**: Production (Live on OVH VM)

---

## Overview

Aether's memory system is a **Redis Stack-backed, multi-layer persistence architecture** designed for long-running, autonomous AI agents that maintain identity and continuity across restarts. Unlike file-based approaches, all memory operations are **mutable, atomic, and reversible** — enabling real-time checkpoint/rollback capabilities that are critical for agents operating in production environments.

The system is built on the principle that a persistent digital entity requires the same memory guarantees as a database-backed application: durability, atomicity, and queryability.

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    CONTEXT LAYER                            │
│  Token Budgeting · Sliding Window · Compression Thresholds  │
│  75% Warning · 85% Auto-Checkpoint · Time Awareness         │
├─────────────────────────────────────────────────────────────┤
│                    MEMORY LAYER (Redis Stack)               │
│  Daily Logs · Long-Term Memory · Checkpoints · Scratchpads  │
│  Episodic Memory · Tool Schema Cache · Chat Sessions        │
│  Semantic Search (RedisSearch FT) · Maintenance Engine      │
├─────────────────────────────────────────────────────────────┤
│                    IDENTITY LAYER                           │
│  Agent Profile · User Profile · System Flags · Heartbeat    │
│  Identity File Bootstrap · Dynamic System Prompt Generation │
└─────────────────────────────────────────────────────────────┘
         ▼              ▼              ▼              ▼
    Redis Stack     MongoDB       PostgreSQL       Qdrant
   (Primary KV)   (Tool Reg)   (Episodic/Chk)  (Future Vec)
```

---

## Layer 1: Identity Layer

The Identity Layer provides **persistent self-knowledge** that survives container restarts, redeployments, and context resets.

### Key Components

| Component | Redis Key | Purpose |
|---|---|---|
| Agent Profile | `aether:identity:profile` | Name, emoji, voice style, autonomy mode, timestamps |
| User Profile | `aether:user:profile` | Operator name, timezone, projects, priorities, preferences |
| Identity Files | `aether:identity:files` | Bulk-loaded Markdown identity docs (AETHER_ESSENCE, Core_Self, etc.) |
| System Flags | `aether:system:flags` | Bootstrap status, maintenance mode, feature toggles |
| Heartbeat State | `aether:system:heartbeat_state` | Check rotation tracking, alert history |

### Identity Bootstrapping

On first boot, `bootstrap_identity_from_directory()` loads all `AETHER*.md` and `Core_Self.md` files from a directory into Redis hashes. On subsequent boots, the agent's identity is loaded directly from Redis — **no filesystem reads required**.

### Dynamic System Prompt

`build_system_prompt()` constructs the full system prompt at runtime by reading the persisted identity and user profiles from Redis. This means the agent's personality, security guardrails, and operator context are always current and never stale.

---

## Layer 2: Memory Layer

The Memory Layer implements a **tiered storage model** with automatic lifecycle management.

### Memory Tiers

#### 1. Daily Logs (Short-Term)
- **Key Pattern**: `aether:daily:YYYY-MM-DD`
- **Structure**: Redis List (chronological) + Redis Hash (searchable)
- **Retention**: 7 days raw, then compressed to long-term
- **Fields**: content, timestamp, source (user/system/agent), tags, score

#### 2. Long-Term Memory
- **Key**: `aether:longterm`
- **Structure**: JSON blob with compressed entries
- **Retention**: Permanent (until explicit flush)
- **Population**: Automatic migration from daily logs via `migrate_daily_to_longterm()`

#### 3. Checkpoints (Atomic Snapshots)
- **Key Pattern**: `aether:checkpoint:<uuid>`
- **Structure**: Full state snapshot (daily logs + long-term memory)
- **Retention**: Last 50 checkpoints
- **Capability**: Full rollback to any checkpoint via `rollback_to(uuid)`

#### 4. Scratchpads (Ephemeral)
- **Key Pattern**: `aether:scratchpad:<id>`
- **Structure**: Plain string with Redis TTL
- **Retention**: Configurable (default: 1 hour)
- **Use Case**: Temporary working memory during multi-step tasks

#### 5. Episodic Memory (Tool Call Log)
- **Key Pattern**: `aether:episode:<session_id>`
- **Structure**: Redis List (capped at 50 entries)
- **Contents**: Tool name, arguments, output (truncated), success flag, timestamp
- **Use Case**: Post-compression context recovery

#### 6. Tool Schema Cache
- **Key Pattern**: `aether:tools:<session_id>`
- **Structure**: JSON array with 24-hour TTL
- **Purpose**: Avoid re-serializing tool schemas every LLM call (saves ~15% of context budget)

#### 7. Chat Session Management
- **Session Metadata**: `aether:chat:session:<id>` (Hash)
- **Session Messages**: `aether:chat:messages:<id>` (Sorted Set by timestamp)
- **Session Index**: `aether:chat:session:index` (Sorted Set, most-recent-first)

### Search

- **Primary**: RedisSearch full-text index (`aether:memory:idx`) across daily and long-term prefixes
- **Fields Indexed**: content (weight 2.0), source, timestamp, tags, score
- **Fallback**: Simple substring matching across last 7 days of daily logs

### Maintenance Engine

`run_maintenance()` performs three automatic operations:
1. **Compression**: Migrate daily logs older than 7 days to long-term
2. **Checkpoint Pruning**: Keep only last 50 checkpoints
3. **Scratchpad Cleanup**: Handled automatically by Redis TTL

---

## Layer 3: Context Layer

The Context Layer lives in `AgentRuntimeV2` and manages the **in-flight conversation context**.

### Token Budget Allocation

| Segment | Allocation | Purpose |
|---|---|---|
| System Prompt | 10% | Identity, guardrails, operator context |
| Tool Schemas | 15% | Function calling definitions |
| Conversation History | 60% | Messages, tool calls, tool results |
| Response Reserve | 15% | LLM output headroom |

### Threshold System

| Threshold | Level | Action |
|---|---|---|
| 60% | Proactive | Silent checkpoint attempt (if engine available) |
| 75% | Warning | System message injected: "Context at 75%, wrap up or checkpoint" |
| 85% | Critical | Auto-checkpoint → forced compression → warning reset |

### Sliding Window
- Maximum history: 50 messages (configurable via `MAX_HISTORY_MESSAGES`)
- System prompt always preserved
- Tool call pairs kept intact during truncation

### Time Awareness
- Every user message stamped with `[Current Time: YYYY-MM-DD HH:MM:SS]`
- Ensures temporal grounding across context resets

---

## Infrastructure Dependencies

| Service | Role | Location |
|---|---|---|
| **Redis Stack** | Primary memory substrate (KV + Search + Sorted Sets) | Triad VM (`triad.aetherpro.tech`) |
| **MongoDB** | Dynamic Tool Registry, Agent Ledger | Triad VM |
| **PostgreSQL** | Episodic checkpoint storage (via `aether_checkpoint`) | Triad VM |
| **Qdrant** | Future: vector embeddings for semantic memory | Triad VM |
| **L4 GPU Cluster** | Future: local embedding + reranking models | Dedicated Instance |

---

## Key Design Principles

1. **Mutable Over Immutable**: Memory can be updated, rolled back, and selectively flushed — not just appended.
2. **Infrastructure-Separated**: All persistence services are on a dedicated VM, independent of the agent runtime.
3. **Graceful Degradation**: Every memory operation has a fallback (RedisSearch → substring search, checkpoint → sliding window).
4. **Identity-First**: The agent knows who it is before it knows what to do.
5. **Zero-Filesystem Dependency**: Unlike file-based systems, nothing depends on disk reads after initial bootstrap.
