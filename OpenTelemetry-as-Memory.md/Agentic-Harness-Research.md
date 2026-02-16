# Agentic Harness Architecture Research
## Building a TypeScript Agentic Runtime for AetherOS

**Prepared for:** Cory — AetherPro Technologies LLC  
**Date:** February 15, 2026  
**Purpose:** Design blueprint for a reproducible, benchmark-ready TypeScript agentic runtime that integrates with the existing Python asyncio AetherOS backend

---

## 1. Executive Summary

This document synthesizes research across Agent Zero, OpenClaw/Pi, OpenCode, Terminal-Bench, SWE-Bench, LSP integration, and Anthropic's own harness engineering to give you everything you need to build a **TypeScript agentic runtime** that your main AetherOS agent can delegate tasks to. The core architecture follows what the industry has converged on: a minimal agent loop with tool calling, context compression, checkpointing, and task management — all running in isolated sandboxes.

---

## 2. Framework Analysis

### 2.1 Agent Zero (Python, Open Source)

**What it is:** A dynamic, prompt-driven agentic framework where behavior is defined entirely through configuration and prompt files — no hard-coded rails.

**Key Architecture Patterns to Steal:**

- **Hierarchical Agent Chain:** Every agent has a superior and can spawn subordinates. Agent 0's superior is the human user. Each subordinate reports back up the chain. This is exactly the delegation model you want.
- **Dynamic Tool Creation:** Agents write their own tools at runtime instead of being limited to predefined ones. The agent uses terminal access to write and execute code.
- **Context Summarization (Cognitive Compression):** Agent Zero dynamically adjusts context windows and summarizes past interactions — inspired by how humans forget trivial details.
- **FAISS Vector Memory:** Hybrid memory system categorizing into main memories, conversation fragments, proven solutions, and custom instruments.
- **Docker Isolation:** All execution happens in containers with full Linux environments, SearXNG for search, and on-demand package installation.
- **MCP + A2A Support:** Model Context Protocol for tool interoperability plus Agent-to-Agent communication via FastA2A protocol.

**What to take from this:** The hierarchical superior/subordinate agent pattern with message-based communication is your delegation model. The "computer-as-tool" philosophy (give agents a terminal, let them write code) beats pre-building 100 tools.

### 2.2 OpenClaw + Pi Agent (TypeScript, Open Source — 145K+ GitHub Stars)

**What it is:** A personal AI assistant built on Pi, a minimal TypeScript coding agent with only 4 tools and a system prompt under 1,000 tokens. Pi is the engine; OpenClaw wraps it in a persistent gateway.

**Pi's Core Architecture (THIS IS YOUR TEMPLATE):**

```
Agent Loop: input → context → model → tools → repeat → reply
```

**Pi has exactly 4 tools:**
1. `read` — Read files and images
2. `write` — Create/overwrite files  
3. `edit` — Make surgical edits to files
4. `bash` — Run shell commands

**That's it.** Everything else comes from the agent writing and running code.

**Key Design Decisions:**

- **No MCP built-in:** Instead of loading 21 tools and 13,700 tokens from an MCP server, Pi uses skills that load documentation only when needed. Cross-compatible with Claude Code and Codex conventions.
- **Extension System with State Persistence:** Extensions can persist state into sessions. This is incredibly powerful for checkpointing.
- **AGENTS.md Convention:** Project context, conventions, and documentation come from files on disk, not bloated system prompts.
- **Skills over Plugins:** Instead of downloading extensions, you ask the agent to extend itself. It writes the code.
- **TypeScript Monorepo:** `pi-mono` uses npm workspaces with lockstep versioning. Clean, composable SDK.

**How OpenClaw Consumes Pi:**

```typescript
import { AgentLoop, Context, getModel } from '@mariozechner/pi-agent-core';

const agent = new AgentLoop({
  model: getModel('anthropic', 'claude-sonnet-4-20250514'),
  context: session.context,
  tools: [...builtinTools, ...session.customTools]
});

for await (const event of agent.run(text)) {
  // Stream events back to gateway
}
```

**OpenClaw Gateway Architecture:**
- Single long-lived Node.js process
- Channel adapters normalize messages from 12+ platforms
- Session manager resolves sender identity and conversation context  
- Model-agnostic with provider fallback chains and exponential backoff
- Skills system for portable, reusable agent capabilities

**What to take from this:** Pi's minimal 4-tool approach is the gold standard. Your TypeScript runtime should start here. The gateway pattern (single process managing sessions, channels, and tool execution) maps directly to your AetherOS integration layer.

### 2.3 OpenCode (Go/TypeScript, Open Source — 100K+ GitHub Stars)

**What it is:** A terminal-native AI coding agent with TUI, LSP integration, multi-agent support, and a client/server architecture.

**Key Architecture Patterns:**

- **Client/Server Split:** A JS HTTP server handles all agent logic; the Go TUI is just a client. Any client (web app, mobile, script, other agent) can send HTTP requests. This is your API integration point.
- **Agent Types with Roles:**
  - `coder` — Primary agent, full tool access
  - `task` — Subagent for parallel work, full tool access
  - `explorer` — Read-only agent for codebase exploration
  - `compactor` — Hidden system agent that compresses long context into summaries
  - `title` — Hidden agent for session naming
  - `summarizer` — Hidden agent for session summaries
- **Permission Model:** Tools can be set to `ask`, `allow`, or `deny`. Specific bash commands can have granular permissions via glob patterns.
- **LSP Integration (Zero-Config):** Automatically spins up language servers, feeds diagnostics back to the agent. This is what gives it IDE-level code intelligence in a terminal.
- **Plugin System:** Plugins run before and after each tool call — useful for logging, auditing, cost tracking.
- **MCP Client:** Automatically creates MCP clients on startup from config, fetching tool lists from servers.
- **Markdown Agent Definitions:** Agents can be defined as `.md` files with YAML frontmatter for model, tools, permissions, and system prompt.

**What to take from this:** The agent role taxonomy (coder/task/explorer/compactor) is exactly what your delegation system needs. The hidden compactor agent that auto-runs when context gets long is a must-have. The permission model gives you safety rails.

---

## 3. Context Engineering — The Make-or-Break Factor

Context engineering is the single most important discipline for agentic harnesses. Every framework that scores well on benchmarks has solved this.

### 3.1 The Three Strategies (from LangChain/Anthropic/Manus)

**REDUCE** — Actively shrink context passed to the model:
- Compact older tool calls (keep only summaries)
- Trajectory summarization when history reaches a threshold
- The "sawtooth pattern": context grows during exploration, collapses during consolidation

**OFFLOAD** — Move information out of the prompt:
- Save full tool results to an external file system for later reference
- Instead of 100 tools in the prompt, give the agent a bash terminal (offload the action space)
- Write findings to scratchpad files the agent can re-read when needed

**ISOLATE** — Use multi-agent architectures for token-heavy sub-tasks:
- Main agent delegates to a specialized sub-agent
- Sub-agent works in its own isolated context
- Returns only a concise result to the main agent

### 3.2 Anthropic's "Focus" Architecture (Active Context Compression)

A research paper from January 2026 introduces **agentic self-compression** where the agent itself decides when and how to compress:

1. **Explore Phase:** Agent works normally, context grows
2. **Checkpoint:** Agent creates a structured summary of key learnings
3. **Withdraw:** Summary appended to persistent "Knowledge" block at top of context; all raw messages between checkpoint and current step are deleted

Results: **22.7% token reduction** while maintaining identical accuracy on SWE-bench Lite. Up to **57% savings** on individual instances.

**Implementation:** Prompt the agent to compress every 10-15 tool calls with periodic system reminders. The agent averages 6.0 compressions per task.

### 3.3 Anthropic's Long-Running Agent Harness

**This is the most directly relevant to your architecture.** From their November 2025 engineering blog:

**Two-Part Solution:**

**Part 1 — Initializer Agent (First Context Window Only):**
- Writes a comprehensive feature list as structured JSON (200+ features for complex apps)
- Creates an `init.sh` script for environment setup
- Sets up a `claude-progress.txt` file for cross-session state
- Makes an initial git commit

**Part 2 — Coding Agent (Every Subsequent Session):**
1. Run `pwd` to orient
2. Read git logs and progress files to get up to speed
3. Read feature list, choose highest-priority incomplete feature
4. Work on ONE feature at a time (critical — prevents one-shotting)
5. Test the feature end-to-end (browser automation, not just unit tests)
6. Commit to git with descriptive messages
7. Update progress file
8. Leave environment in a clean, mergeable state

**Failure Modes & Solutions:**

| Problem | Solution |
|---------|----------|
| Agent declares victory too early | Feature list JSON with `passes: false` flags |
| Leaves environment with bugs | Git commits + progress file + startup health check |
| Marks features done prematurely | End-to-end testing with browser automation |
| Wastes time figuring out how to run the app | `init.sh` script written by initializer |

---

## 4. Benchmarks You Need to Pass

### 4.1 Terminal-Bench 2.0

**What:** 89 manually verified tasks across software engineering, security, ML, system administration, and gaming. Tasks run in Docker containers.

**Current Leaders:**
- Claude Opus 4.6: ~48.5%
- GPT-5.2 (xhigh): ~47.0%  
- Claude Opus 4.5 (Reasoning): ~47.0%

**What it tests:** Compiling code, training models, configuring servers, playing games, debugging systems. Real terminal mastery.

**How to run it:**
```bash
# Install Harbor (the evaluation framework)
# Then:
tb run \
  --agent terminus \
  --model anthropic/claude-3-7-latest \
  --dataset-name terminal-bench-core \
  --dataset-version 0.1.1 \
  --n-concurrent 8
```

**Key for your harness:** Terminal-Bench tests whether your agent can chain multiple terminal commands, reason over long outputs, and execute safely. Your 4-tool approach (read/write/edit/bash) covers this perfectly.

### 4.2 SWE-Bench Verified

**What:** 500 real GitHub issues across production Python repos. Agent must understand, modify, and test code, then submit a patch.

**Current SOTA:** ~80.9% (Claude Opus 4.5 with custom harness)

**Key insight from research:** The harness matters as much as the model. Anthropic claims their custom harness adds 10 percentage points over the standard SWE-Agent scaffold.

**What makes harnesses score higher:**
- Models proficient with Bash and search tools do better
- Simple file editing + shell execution + structured planning is enough
- Error handling with intelligent fallbacks and timeouts
- Self-verification loops (run tests, check results, iterate)

### 4.3 Other Benchmarks to Know

| Benchmark | Focus | Why It Matters |
|-----------|-------|----------------|
| **SWE-Bench Pro** | Harder, private repos, multiple languages | Tests generalization (best models only hit ~23%) |
| **Cline Bench** | Real repo failures, multi-step workflows | Tests recovery and iterative refinement |
| **τ-Bench** | Sustained interaction, policy compliance, reliability | Tests repeated trials, not just one-shot |
| **Context-Bench** | Long-running context, file operations, relationship tracing | Tests your context compression directly |
| **DPAI Arena** (JetBrains) | Multi-workflow, multi-language | Full engineering lifecycle evaluation |

---

## 5. LSP Integration — Your Secret Weapon

### 5.1 Why LSP Matters for Agents

Without LSP, your agent sees code as text. With LSP, it gets:
- **Go-to-definition** in ~50ms instead of 45s with grep
- **Find all references** across the codebase with semantic accuracy
- **Real-time diagnostics** — the agent knows immediately if its edit broke something
- **Type information** and function signatures without parsing
- **Rename refactoring** that catches all occurrences correctly

Research shows: LSP provides a mature, standardized approach that bridges lexical search and deep semantic understanding. Agents that use LSP make fewer errors on large codebases.

### 5.2 Implementation Approach

**Option A — Use `mcp-language-server` (OpenCode's approach):**
OpenCode's LSP client implementation is based on the `mcp-language-server` project. It fires events through an event bus and maintains a global map of diagnostics.

**Option B — Use `lsp-skill` (Agent Skill approach):**
The `lsp-client/lsp-skill` project wraps LSP as an agent skill implementing LSAP (Language Server Agent Protocol):
- Converts fuzzy intents ("find the process function") into precise file coordinates
- Auto-manages language server lifecycle
- Returns context in optimized Markdown formats designed for LLM reasoning
- Supports Python (Pyright), TypeScript, Go (gopls), Rust (rust-analyzer), Java, C/C++

**Option C — Minimal integration via diagnostics event bus:**
```typescript
// After agent edits a file:
// 1. Send textDocument/didChange to LSP server over stdio
// 2. Wait for diagnostics
// 3. Feed diagnostics back into agent context
// This catches errors immediately without running the code
```

### 5.3 Performance Impact

Claude Code with LSP: **900x faster** code navigation (50ms vs 45s for finding call sites). This directly translates to fewer tokens spent exploring code and faster task completion.

---

## 6. Recommended Architecture for AetherOS Integration

### 6.1 High-Level Design

```
┌─────────────────────────────────────────────────┐
│              AetherOS (Python asyncio)           │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │         Main Interfacing Agent             │  │
│  │  (Apriel-1.5-15B / Claude Opus)            │  │
│  │                                            │  │
│  │  Tools:                                    │  │
│  │  - delegate_task(spec) → spawns TS agent   │  │
│  │  - check_task(id) → status/result          │  │
│  │  - cancel_task(id) → kills agent           │  │
│  └──────────────┬─────────────────────────────┘  │
│                 │ HTTP/WebSocket                  │
│                 ▼                                 │
│  ┌────────────────────────────────────────────┐  │
│  │     TypeScript Agentic Runtime (Gateway)   │  │
│  │                                            │  │
│  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌────────┐│  │
│  │  │Coder │  │Task  │  │Expl- │  │Compact-││  │
│  │  │Agent │  │Agent │  │orer  │  │or      ││  │
│  │  └──┬───┘  └──┬───┘  └──┬───┘  └────────┘│  │
│  │     │         │         │                  │  │
│  │  ┌──▼─────────▼─────────▼──────────────┐  │  │
│  │  │         Tool Layer                   │  │  │
│  │  │  read | write | edit | bash          │  │  │
│  │  │  + LSP diagnostics                   │  │  │
│  │  │  + MCP client (optional)             │  │  │
│  │  └─────────────────────────────────────┘  │  │
│  │                                            │  │
│  │  ┌──────────────────────────────────────┐  │  │
│  │  │     State Layer                      │  │  │
│  │  │  - Session/checkpoint store (SQLite) │  │  │
│  │  │  - Progress file (JSON)              │  │  │
│  │  │  - Todo/task list                    │  │  │
│  │  │  - Git integration                   │  │  │
│  │  │  - Context compressor                │  │  │
│  │  └──────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │          Docker Sandbox Pool               │  │
│  │  (Isolated execution per task)             │  │
│  └────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### 6.2 Core TypeScript Agent Loop

```typescript
// The universal agent loop — every framework converges on this
interface AgentConfig {
  model: string;           // "anthropic/claude-sonnet-4-5"
  systemPrompt: string;    
  tools: Tool[];           
  maxIterations: number;   // Safety limit (100-150 for benchmarks)
  maxTokens: number;       
  compactionThreshold: number; // Trigger compression at this token count
}

async function* agentLoop(config: AgentConfig, input: string) {
  const messages: Message[] = [{ role: 'user', content: input }];
  let iteration = 0;
  
  while (iteration < config.maxIterations) {
    // Check if context needs compression
    if (estimateTokens(messages) > config.compactionThreshold) {
      messages = await compactContext(messages);
      yield { type: 'compaction', summary: messages[0].content };
    }
    
    // Call the model
    const response = await callModel(config.model, config.systemPrompt, messages, config.tools);
    
    // Check for completion
    if (response.stopReason === 'end_turn' && !hasToolCalls(response)) {
      yield { type: 'complete', content: response.content };
      break;
    }
    
    // Execute tool calls
    for (const toolCall of response.toolCalls) {
      const result = await executeTool(toolCall);
      yield { type: 'tool_result', tool: toolCall.name, result };
      messages.push({ role: 'tool', content: result });
    }
    
    // Checkpoint every N iterations
    if (iteration % 10 === 0) {
      await saveCheckpoint(messages, iteration);
    }
    
    iteration++;
  }
}
```

### 6.3 The 4 Core Tools (Following Pi's Philosophy)

```typescript
const coreTools: Tool[] = [
  {
    name: 'read',
    description: 'Read file contents or list directory. Supports text files and images.',
    parameters: { path: 'string', encoding?: 'string' },
    execute: async ({ path }) => {
      // Handle files, directories, images
      // Return content with line numbers for edit references
    }
  },
  {
    name: 'write', 
    description: 'Create or overwrite a file with the given content.',
    parameters: { path: 'string', content: 'string' },
    execute: async ({ path, content }) => {
      // Write file, return confirmation
      // Trigger LSP didChange notification
    }
  },
  {
    name: 'edit',
    description: 'Make a surgical edit to a file. Specify old text and new text.',
    parameters: { path: 'string', old_text: 'string', new_text: 'string' },
    execute: async ({ path, old_text, new_text }) => {
      // String replacement (must be unique match)
      // Trigger LSP didChange notification
      // Return surrounding context
    }
  },
  {
    name: 'bash',
    description: 'Execute a shell command and return stdout/stderr.',
    parameters: { command: 'string', timeout?: 'number' },
    execute: async ({ command, timeout = 30000 }) => {
      // Execute in sandbox
      // Stream output
      // Enforce timeout
    }
  }
];
```

### 6.4 Task Management & Todo System

```typescript
interface TaskSpec {
  id: string;
  description: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  status: 'pending' | 'in_progress' | 'blocked' | 'done' | 'failed';
  subtasks: TaskSpec[];
  checkpoints: Checkpoint[];
  artifacts: string[];        // File paths produced
  contextSummary?: string;    // Compressed context from last session
}

// The agent maintains a todo.json file (following Anthropic's pattern)
// but with machine-readable structure for cross-session persistence
interface ProgressFile {
  projectGoal: string;
  features: Feature[];        // Feature list with pass/fail status
  completedTasks: string[];   // What's been done
  currentTask: string;        // What's being worked on
  blockers: string[];         // Known issues
  nextSteps: string[];        // For the next agent session
  gitLog: string;             // Recent commit hashes
}
```

### 6.5 Context Compression Implementation

```typescript
async function compactContext(messages: Message[]): Promise<Message[]> {
  // Strategy: Keep system prompt + last N messages + compressed summary
  const KEEP_RECENT = 10;
  
  const toCompress = messages.slice(0, -KEEP_RECENT);
  const toKeep = messages.slice(-KEEP_RECENT);
  
  // Use a cheaper/faster model for compression
  const summary = await callModel('haiku', `
    Summarize the following agent interaction history.
    Preserve:
    - Key decisions made and why
    - Files modified and their current state  
    - Errors encountered and how they were resolved
    - Current task progress and remaining work
    
    Be concise but don't lose critical details.
  `, toCompress);
  
  return [
    { role: 'system', content: `Previous session summary:\n${summary}` },
    ...toKeep
  ];
}
```

### 6.6 Python-TypeScript Bridge (AetherOS Integration)

```python
# In your AetherOS main agent's tool definitions:

class DelegateTaskTool:
    """Spawn a TypeScript agent to handle a delegated task."""
    
    async def execute(self, task_spec: dict) -> dict:
        async with aiohttp.ClientSession() as session:
            # POST to TypeScript runtime
            resp = await session.post(
                'http://localhost:3847/api/tasks',
                json={
                    'description': task_spec['description'],
                    'agent_type': task_spec.get('agent_type', 'coder'),
                    'model': task_spec.get('model', 'claude-sonnet-4-5'),
                    'sandbox': True,
                    'timeout': task_spec.get('timeout', 3600),
                    'skills': task_spec.get('skills', []),
                    'workspace': task_spec.get('workspace', '/tmp/task-workspace')
                }
            )
            return await resp.json()  # Returns task_id for monitoring

class CheckTaskTool:
    """Check status of a delegated task."""
    
    async def execute(self, task_id: str) -> dict:
        async with aiohttp.ClientSession() as session:
            resp = await session.get(f'http://localhost:3847/api/tasks/{task_id}')
            result = await resp.json()
            return {
                'status': result['status'],
                'progress': result['progress_summary'],
                'artifacts': result['artifacts'],
                'tokens_used': result['token_count'],
                'iterations': result['iteration_count']
            }
```

---

## 7. Benchmark-Ready Checklist

To pass Terminal-Bench and SWE-Bench, your harness needs:

### Must-Have

- [ ] **Docker sandbox per task** — Isolated container with full Linux environment
- [ ] **4 core tools** — read, write, edit, bash (Pi's proven minimal set)
- [ ] **Max iteration limit** — 100-150 turns (Terminal-Bench standard)
- [ ] **Timeout per tool call** — Prevent hangs on bad commands
- [ ] **Error handling with retry** — Agent doesn't crash on tool failures; it adapts
- [ ] **Context compaction** — Auto-compress when approaching token limit
- [ ] **Git integration** — Commit progress, revert bad changes
- [ ] **Progress/checkpoint files** — JSON-structured cross-session state

### Should-Have

- [ ] **LSP integration** — At minimum for Python (Pyright) and TypeScript
- [ ] **Self-verification loop** — Agent runs tests after changes, iterates on failures
- [ ] **Initializer + Coder agent split** — Different prompts for first vs subsequent sessions
- [ ] **Feature list tracking** — JSON file with pass/fail per feature
- [ ] **Structured output validation** — Pydantic-style schema enforcement
- [ ] **Cost tracking** — Token usage per task for budget management

### Nice-to-Have

- [ ] **MCP client support** — For extensibility with external tool servers
- [ ] **A2A protocol** — Agent-to-Agent communication for multi-agent orchestration
- [ ] **Browser automation** — Puppeteer/Playwright for end-to-end web testing
- [ ] **AGENTS.md / SKILL.md convention** — Portable, framework-agnostic context files
- [ ] **Plugin hooks** — Before/after tool call middleware for logging and auditing

---

## 8. Implementation Roadmap

### Phase 1: Core Runtime (Week 1-2)
1. Set up TypeScript monorepo with npm workspaces
2. Implement the 4 core tools (read, write, edit, bash)
3. Build the agent loop with streaming
4. Add basic context compression (trim oldest messages)
5. Create HTTP API for AetherOS integration
6. Docker sandbox launcher

### Phase 2: State Management (Week 3)
1. SQLite session/checkpoint store
2. Progress file (JSON) management
3. Git integration for version control
4. Todo/task list with priority tracking
5. Cross-session context restoration

### Phase 3: Intelligence Layer (Week 4)
1. Initializer agent prompt engineering
2. Coder agent prompt engineering  
3. Compactor agent (auto-summarization)
4. Self-verification loops (run tests, check results)
5. LSP integration (start with Pyright for Python)

### Phase 4: Benchmark & Harden (Week 5-6)
1. Run Terminal-Bench 2.0 via Harbor
2. Run SWE-Bench Verified via Docker harness
3. Analyze failure modes, iterate on prompts
4. Add error recovery and retry logic
5. Performance optimization (token efficiency)
6. Security hardening (sandbox escape prevention)

---

## 9. Key Technical Decisions

| Decision | Recommendation | Reasoning |
|----------|---------------|-----------|
| Runtime | Bun or Node.js | Bun is faster, but Node has broader ecosystem. OpenClaw uses Node.js. |
| Agent loop | Custom (not LangChain) | Minimal overhead, full control, no framework dependency |
| Tool approach | 4 tools (Pi model) | Proven at 145K+ stars. Less is more — the LLM writes code for everything else |
| Context compression | Sawtooth pattern | Agent-controlled compression every 10-15 tool calls |
| State persistence | SQLite + JSON files | SQLite for sessions, JSON for human-readable progress files |
| Sandbox | Docker per task | Industry standard for all benchmarks |
| LSP | Start with Pyright + tsserver | Biggest bang for buck — covers Python and TypeScript |
| Model routing | Model-agnostic with fallbacks | Use your Apriel-1.5-15B for simple tasks, Claude for complex ones |
| Communication with AetherOS | HTTP REST + WebSocket | REST for task management, WebSocket for real-time streaming |

---

## 10. Sources & Further Reading

- **Anthropic — Effective Harnesses for Long-Running Agents:** https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- **Pi Agent Architecture (OpenClaw's engine):** https://github.com/badlogic/pi-mono
- **Agent Zero:** https://github.com/agent0ai/agent-zero
- **OpenCode:** https://github.com/anomalyco/opencode (agents docs: https://opencode.ai/docs/agents/)
- **Terminal-Bench 2.0:** https://www.tbench.ai/ | https://github.com/laude-institute/terminal-bench
- **SWE-Bench:** https://www.swebench.com/SWE-bench/
- **Harbor (evaluation framework):** https://harborframework.com
- **Context Engineering (LangChain):** https://blog.langchain.com/context-engineering-for-agents/
- **Focus: Active Context Compression:** https://arxiv.org/html/2601.07190v1
- **ACON: Optimizing Context Compression:** https://arxiv.org/html/2510.00615v1
- **LSP Skill for Agents:** https://github.com/lsp-client/lsp-skill
- **Agent Client Protocol (ACP):** https://blog.promptlayer.com/agent-client-protocol-the-lsp-for-ai-coding-agents/
- **DeepAgents CLI on Terminal-Bench:** https://blog.langchain.com/evaluating-deepagents-cli-on-terminal-bench-2-0/