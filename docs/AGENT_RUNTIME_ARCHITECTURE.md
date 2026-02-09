# Aether Agent Runtime Architecture

## Overview

The Agent Runtime is an event-driven state machine that transforms Aether from a simple chatbot into a true autonomous agent capable of multi-step reasoning, tool execution, and human-in-the-loop approval gates.

## Architecture Shift

### Before: Simple Chat
```
User Message → LLM → Response
```

### After: Event-Driven Agent Runtime
```
User Message → PLANNING → THINKING → TOOL_CALLING → OBSERVING → COMPILING → Response
                      ↑                          ↓
                      └──── PAUSED (approval) ───┘
```

## Core Components

### 1. AetherRuntime (State Machine)

**File:** `aether/agent_runtime.py`

The runtime orchestrates the entire agent lifecycle:

```python
class AgentState(Enum):
    IDLE = "idle"           # Waiting for input
    PLANNING = "planning"   # Breaking down task into steps
    THINKING = "thinking"   # Reasoning about current step
    TOOL_CALLING = "tool_calling"  # Executing tools
    OBSERVING = "observing" # Analyzing tool results
    COMPILING = "compiling" # Synthesizing final response
    PAUSED = "paused"       # Waiting for user approval
```

**Key Methods:**
- `run_task()` - Main entry point, async generator that yields events
- `_create_plan()` - Breaks task into steps
- `_think()` - Generates reasoning for each step
- `_execute_tool()` - Runs tools with live output streaming
- `_observe()` - Analyzes tool results
- `_compile_response()` - Synthesizes final answer

### 2. AgentSessionManager (WebSocket Handler)

**File:** `aether/agent_websocket.py`

Manages WebSocket connections and bridges the runtime to clients:

```python
class AgentSessionManager:
    active_runtimes: Dict[str, AetherRuntime]
    connections: Dict[str, WebSocket]
    pending_approvals: Dict[str, asyncio.Event]
```

**Responsibilities:**
- Accept WebSocket connections at `/ws/agent/{session_id}`
- Create/maintain AetherRuntime instances per session
- Forward runtime events to WebSocket clients
- Handle approval gates with timeout
- Cleanup on disconnect

### 3. UI Components

**Files:** `ui/client/src/components/`

| Component | Purpose |
|-----------|---------|
| `AetherPanel.tsx` | Main workbench layout |
| `PlanSteps.tsx` | Visual plan with progress |
| `ThinkingStream.tsx` | Live reasoning display |
| `ToolExecutionCard.tsx` | Tool execution with logs/screenshots |
| `ApprovalGate.tsx` | User approval modal |
| `ChatBubble.tsx` | Message display |
| `AetherInput.tsx` | Input with file attachments |

### 4. Frontend Hook

**File:** `ui/client/src/hooks/useAgentRuntime.ts`

```typescript
const {
  state,           // Current agent state
  messages,        // Chat messages
  toolExecutions,  // Tool execution history
  pendingApproval, // Current approval request
  sendMessage,     // Send user input
  approveOperation // Approve/reject operations
} = useAgentRuntime(sessionId);
```

## Event Types

The runtime streams these events to the frontend:

| Event | Payload | When |
|-------|---------|------|
| `state_change` | `{old_state, new_state}` | State machine transition |
| `plan_created` | `{steps: [...]}` | Plan generated |
| `thinking_start` | `{step: {...}}` | Reasoning begins |
| `thinking_chunk` | `{chunk: "..."}` | Streaming reasoning token |
| `thinking_complete` | `{thinking: "..."}` | Reasoning finished |
| `tool_call_start` | `{tool_id, tool, params}` | Tool execution begins |
| `tool_call_chunk` | `{tool_id, chunk}` | Live tool output (logs) |
| `tool_call_complete` | `{tool_id, result}` | Tool execution finished |
| `tool_call_failed` | `{tool_id, error}` | Tool execution error |
| `approval_required` | `{id, tool, params, risk_level}` | Pause for approval |
| `approval_received` | `{id, approved}` | User approved/denied |
| `step_complete` | `{step_index}` | Plan step finished |
| `response_chunk` | `{chunk}` | Streaming response |
| `response_complete` | `{response}` | Task finished |
| `error` | `{message}` | Runtime error |

## Lifecycle Flow

```
1. User sends message via WebSocket
   └─> sendMessage("Analyze this codebase")

2. Runtime enters PLANNING state
   └─> _create_plan() generates steps
   └─> Emit: state_change (IDLE→PLANNING)
   └─> Emit: plan_created

3. For each plan step:
   
   a. Enter THINKING state
      └─> _think() generates reasoning
      └─> Emit: state_change (PLANNING→THINKING)
      └─> Emit: thinking_start
      └─> Emit: thinking_chunk (streamed)
      └─> Emit: thinking_complete
   
   b. Enter TOOL_CALLING state
      └─> Check if approval required
      └─> If yes: Emit: approval_required
                 └─> Wait for user response
                 └─> Emit: approval_received
      └─> _execute_tool()
      └─> Emit: state_change (THINKING→TOOL_CALLING)
      └─> Emit: tool_call_start
      └─> Emit: tool_call_chunk (live logs)
      └─> Emit: tool_call_complete
   
   c. Enter OBSERVING state
      └─> _observe() analyzes results
      └─> Emit: state_change (TOOL_CALLING→OBSERVING)
   
   d. Step complete
      └─> Emit: step_complete

4. Enter COMPILING state
   └─> _compile_response()
   └─> Emit: state_change (OBSERVING→COMPILING)
   └─> Emit: response_chunk (streamed)
   └─> Emit: response_complete

5. Return to IDLE state
   └─> Emit: state_change (COMPILING→IDLE)
```

## Approval Gates (Semi-Autonomous Mode)

High-risk operations require user approval:

```python
def _requires_approval(self, tool_spec: Dict) -> bool:
    high_risk_tools = [
        "execute_code",   # Arbitrary code execution
        "write_file",     # File modification
        "shell_command",  # Shell access
        "delete_file"     # Destructive operation
    ]
    return tool_spec["tool"] in high_risk_tools
```

**Risk Levels:**
- `low` - Read-only operations (web_search, read_file)
- `medium` - Write operations (write_file)
- `high` - Destructive operations (shell_command, delete_file)

**Trust Duration:**
Users can approve "just this time" or for a duration (5min, 30min, 1hr, 5hr).

## Memory Model

**Redis (Long-term):**
- Facts, identity, user preferences
- Persistent across sessions
- Accessed via `self.memory`

**Working Memory (Ephemeral):**
- Current task context
- Tool execution results
- Current plan state
- Stored in `self.working_memory: Dict`

## Workbench UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Status Bar: 🔵 Thinking...              [Stop] [Clear]      │
├─────────────────────────────────┬───────────────────────────┤
│                                 │  Plan:                   │
│  User: Hello!                   │  1. ✓ Analyze req        │
│                                 │  2. ⏳ Write code        │
│  Agent: I've completed...       │  3. ○ Test               │
│                                 │  ━━━━━━━━━━━ (67%)       │
│  [Thinking...]                  │                          │
│  • Live reasoning here          │  Tool Executions:        │
│                                 │  ┌────────────────────┐  │
│  [Running: execute_code]        │  │ execute_code ▼     │  │
│  • Logs streaming...            │  │ Parameters: {...}  │  │
│                                 │  │ Output: Success    │  │
│                                 │  └────────────────────┘  │
│                                 │                          │
│                                 │  Active Capabilities:    │
│                                 │  [Code] [Web] [Files]    │
├─────────────────────────────────┼───────────────────────────┤
│  [Input with attachments]      │  Session: abc-123...     │
└─────────────────────────────────┴───────────────────────────┘
```

## WebSocket Endpoints

### `/ws/agent/{session_id}` (New)
Event-driven agent runtime with full lifecycle streaming.

**Message Types:**
```json
// Client → Server
{"type": "user_input", "message": "...", "attachments": []}
{"type": "approval_response", "request_id": "...", "approved": true}
{"type": "cancel_task"}

// Server → Client
{"event_type": "state_change", "timestamp": "...", "payload": {...}}
{"event_type": "plan_created", "timestamp": "...", "payload": {"steps": [...]}}
// ... (see Event Types table)
```

### `/ws/chat` (Legacy)
Simple request/response chat (maintained for backward compatibility).

## Future Enhancements

1. **Parallel Tool Execution** - Run independent tools concurrently
2. **Self-Correction Loop** - Agent can retry failed steps
3. **Long-Running Tasks** - Persist state for tasks spanning hours/days
4. **Multi-Agent Collaboration** - Delegate subtasks to Percy/fabric agents
5. **Tool Learning** - Agent learns new tools from demonstrations

## Configuration

```yaml
# config/agent-runtime.yaml
autonomy:
  default_mode: "semi"  # semi | auto
  
approval_gates:
  enabled: true
  trust_duration_options: [0, 300, 1800, 3600, 18000]  # seconds
  
risk_levels:
  high: ["shell_command", "delete_file", "system_modify"]
  medium: ["write_file", "execute_code"]
  low: ["read_file", "web_search", "browser_navigate"]

sandbox:
  enabled: true
  network_isolation: true
  memory_limit: "512m"
  cpu_limit: "1.0"
```
