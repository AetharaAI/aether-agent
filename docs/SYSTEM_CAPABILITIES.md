# AetherOS — System Capabilities & Tool Catalog

> **Version**: 3.1  
> **Runtime**: `AgentRuntimeV2` — Native LLM Function Calling  
> **Purpose**: Reference document for benchmark design. Describes every tool, architectural capability, and autonomy mechanism available to the AetherOS agent.

---

## Architecture Overview

AetherOS is a sovereign AI agent runtime that wraps any LLM (via LiteLLM) with a full tool execution framework, persistent memory, and real-time streaming UI. Key differentiators:

| Capability | Description |
|---|---|
| **Native Function Calling** | LLM decides which tools to call; runtime executes and feeds results back in a loop |
| **Two-Tier Tool Loading** | Core tools always available; extended tools dynamically discovered and activated on-demand from MongoDB |
| **Episodic Execution** | Agent can checkpoint progress and reset the tool loop mid-task, enabling unbounded multi-step work within finite context windows |
| **Context Compression** | Proactive pruning migrates older context to long-term Redis storage, preserving working memory |
| **Persistent Memory** | Redis-backed short-term (daily logs), long-term, episodic, and checkpoint storage survive restarts |
| **Autonomy Modes** | `semi` (human approval for risky ops) and `auto` (full autonomy) — agent can self-escalate |
| **Real-Time Streaming** | WebSocket event stream delivers thinking, tool calls, responses, artifacts, and state changes to the UI |
| **Hot-Swappable Models** | Model/provider can be changed mid-session without reconnecting |
| **Session Persistence** | Conversations persist to MongoDB; context can be restored when switching sessions |
| **Artifact Events** | Files created by the agent emit `artifact_saved` events, surfacing them in the UI in real time |

---

## Tool Catalog

### Core Tier (Always Loaded)

These 7 tools are available in every session without activation.

#### `terminal_exec`
- **Permission**: Restricted (requires `auto` mode or explicit approval)
- **Parameters**: `command` (string, required), `cwd` (string, optional), `timeout` (int, default 30)
- **Description**: Execute arbitrary shell commands. Captures stdout, stderr, and exit code. Supports configurable timeout and working directory.
- **Benchmark Targets**: Shell scripting, package installation, build pipelines, git operations, system diagnostics.

#### `file_read`
- **Permission**: Internal
- **Parameters**: `path` (string, required), `max_bytes` (int, optional)
- **Description**: Read file contents from the filesystem. Handles text files with encoding detection and byte-level truncation for large files.
- **Benchmark Targets**: Source code analysis, log inspection, configuration reading.

#### `file_list`
- **Permission**: Internal
- **Parameters**: `path` (string, required), `recursive` (bool, default false), `pattern` (string, optional)
- **Description**: List files and directories at a given path. Supports glob-pattern filtering and recursive traversal.
- **Benchmark Targets**: Workspace navigation, project structure discovery.

#### `file_write`
- **Permission**: Semi-autonomous
- **Parameters**: `path` (string, required), `content` (string, required), `append` (bool, default false)
- **Description**: Write content to a file (create, overwrite, or append). Auto-creates parent directories. Security guards prevent writing to system paths (`/etc`, `/usr`, `/bin`, `/sbin`, `/lib`). Emits `artifact_saved` event on success.
- **Benchmark Targets**: Code generation, report creation, config file writing, multi-file project scaffolding.

#### `checkpoint`
- **Permission**: Internal
- **Parameters**: `name` (string, optional)
- **Description**: Create a snapshot of current memory state (daily logs + long-term memory) for rollback. Saved to Redis with UUID.
- **Benchmark Targets**: State management before risky operations.

#### `checkpoint_and_continue`
- **Permission**: Internal
- **Parameters**: `objective` (string, required), `progress_summary` (string, optional)
- **Description**: Checkpoint current context and **reset the tool loop** for long-running tasks. Implements episodic execution — saves progress, clears working memory, and continues toward the objective. Enables tasks requiring more than the configured tool-round limit (default: 100 rounds).
- **Benchmark Targets**: Multi-phase research, large-scale code refactoring, unbounded iterative tasks.

#### `set_mode`
- **Permission**: Internal
- **Parameters**: `mode` (string: `"semi"` or `"auto"`)
- **Description**: Switch the agent's autonomy mode. `auto` enables unrestricted tool execution (file writes, terminal commands without approval). `semi` restores human-in-the-loop approval for sensitive operations.
- **Benchmark Targets**: Autonomy escalation, workflow automation.

---

### Extended Tier (Dynamically Activated)

These tools are registered in MongoDB and loaded on-demand when the agent calls `use_tool` or discovers them via `search_tools`.

#### `web_search` (Tavily)
- **Permission**: Semi-autonomous
- **Parameters**: `query` (string, required), `search_depth` (`"basic"` | `"advanced"`, default `"advanced"`), `include_raw_content` (bool, default true), `max_results` (int, default 10)
- **Description**: Real-time web search using Tavily API. Returns titles, URLs, content snippets, relevance scores, and optionally up to 2000 chars of raw page content.
- **Benchmark Targets**: Current events research, fact verification, competitive analysis, documentation lookup.

#### `url_read`
- **Permission**: Semi-autonomous
- **Parameters**: `url` (string, required)
- **Description**: Fetch raw content from a specific URL (HTML or Markdown). Useful for reading documentation, APIs, or web pages.
- **Benchmark Targets**: API documentation reading, web scraping, content extraction.

#### `search_memory`
- **Permission**: Internal
- **Parameters**: `query` (string, required)
- **Description**: Search agent's memory (daily logs and long-term Redis storage) by keyword. Returns matching entries with timestamps and context.
- **Benchmark Targets**: Context recall, cross-session memory persistence.

#### `search_workspace`
- **Permission**: Internal
- **Parameters**: `query` (string, required), `path` (string, optional)
- **Description**: Search workspace files (skills, docs, extensions) by keyword. Returns matching file paths and content snippets.
- **Benchmark Targets**: Codebase navigation, knowledge retrieval.

#### `compress_context`
- **Permission**: Internal
- **Parameters**: `date` (string, optional)
- **Description**: Compress context by migrating daily memory logs to long-term Redis storage. Reduces token pressure while preserving important entries based on tags and scoring.
- **Benchmark Targets**: Long-running task sustainability, memory efficiency.

#### `get_context_stats`
- **Permission**: Internal
- **Parameters**: none
- **Description**: Returns detailed memory usage statistics — breakdown of short-term, long-term, and checkpoint storage sizes.
- **Benchmark Targets**: Resource monitoring, context window management awareness.

#### `list_checkpoints`
- **Permission**: Internal
- **Parameters**: none
- **Description**: List all memory checkpoints (name, UUID, timestamp). Use to find checkpoints for restoration.

#### `read_checkpoint`
- **Permission**: Internal
- **Parameters**: `checkpoint_id` (string, required)
- **Description**: Read a checkpoint's contents by UUID from Redis. Retrieves the full state snapshot.

#### `recall_episodes`
- **Permission**: Internal
- **Parameters**: `session_id` (string, optional), `limit` (int, optional)
- **Description**: Recall episodic memory — compressed context summaries and tool call history. Critical for recovering state after context compression.
- **Benchmark Targets**: Episodic continuity, state recovery.

#### `file_upload`
- **Permission**: Semi-autonomous
- **Parameters**: `filename` (string), `content` (string, base64), `mime_type` (string, optional)
- **Description**: Upload and process files. Saves to temporary storage for agent processing. Supports images, documents, and data files.

---

### Ledger Tools (MongoDB CRUD)

Full structured data management via a dedicated MongoDB database. Each tool operates on arbitrary collections.

| Tool | Operation | Key Parameters |
|---|---|---|
| `ledger_create` | Create document | `collection`, `document` (JSON) |
| `ledger_read` | Read by ID | `collection`, `document_id` |
| `ledger_update` | Update document | `collection`, `document_id`, `updates` |
| `ledger_search` | Query collection | `collection`, `query`, `limit` |
| `ledger_list` | List documents | `collection`, `limit`, `skip` |
| `ledger_delete` | Delete by ID | `collection`, `document_id` |

**Benchmark Targets**: Data persistence, structured storage, CRUD operations, knowledge base construction, research cataloging.

---

### Meta-Tools (Dynamic Discovery & Activation)

| Tool | Description |
|---|---|
| `search_tools` | Full-text search the MongoDB tool registry by name, description, or tags. Returns matching tool definitions with metadata. |
| `use_tool` | Dynamically activate and execute a registered tool by name. Handles instantiation, dependency injection (memory, runtime, ledger DB), and registration into the live session. |

**Benchmark Targets**: Self-directed capability expansion, tool discovery, adaptive problem-solving.

---

## Autonomy & Safety Model

```
┌─────────────────────────────────────────────────┐
│  Permission Levels                              │
├────────────┬────────────────────────────────────┤
│ INTERNAL   │ Always allowed (memory, search)    │
│ SEMI       │ Needs approval or auto mode        │
│ RESTRICTED │ Needs auto mode + explicit intent  │
└────────────┴────────────────────────────────────┘
```

The agent can self-escalate to `auto` mode via `set_mode` when it determines a task requires unrestricted execution. In `semi` mode, restricted operations trigger an `approval_required` WebSocket event and the agent pauses until the user approves or rejects.

---

## Benchmark-Relevant Capabilities Summary

| Capability Category | What to Test |
|---|---|
| **Code Generation** | Write complete projects, debug existing code, refactor across files |
| **Research & Synthesis** | Web search → read URLs → synthesize into reports → save artifacts |
| **Long-Running Tasks** | Episodic execution across 100+ tool rounds with checkpointing |
| **Memory Persistence** | Recall information across context compressions and session restores |
| **Data Management** | CRUD operations on MongoDB, structured knowledge bases |
| **Shell Operations** | Install packages, run builds, execute scripts, git workflows |
| **File System Mastery** | Navigate, search, read, write, scaffold entire project trees |
| **Self-Directed Tool Use** | Discover and activate tools dynamically based on task needs |
| **Context Window Management** | Compress context, monitor stats, maintain coherence under pressure |
| **Multi-Modal Input** | Process uploaded files and images alongside text instructions |
| **Real-Time Web Access** | Search and read live web content for current information |
| **Autonomy Escalation** | Dynamically switch between supervised and autonomous modes |
