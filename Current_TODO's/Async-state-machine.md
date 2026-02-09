You nailed the core problem: **most "AI agents" are just chatbots with extra steps**, while pro tools (Claude.ai, Cursor, my Agent mode) run an **event-driven state machine** that streams granular lifecycle events to the frontend. Here's how they actually work and how to fix Aether.

## 1. The Architecture Gap: Chatbot vs Agent

### The "Glorified Chatbot" Pattern (What Aether has now)
```
User → HTTP POST → LLM → Response → UI
```
Single request/response. State dies between messages. The UI is just a message renderer.

### The Pro Agent Pattern (What you need)
```
User → WebSocket → Agent Runtime (Stateful Process)
                        ↓
              ┌─────────┴─────────┐
         Event Bus (Redis/Stream)   Tool Sandbox
              ↓                         ↓
        UI Subscribers           Computer Environment
```

The **Agent Runtime** is a persistent async process (Python `asyncio` loop) that:
- Maintains state across turns (not just chat history, but execution context)
- Emits granular events: `thinking_start`, `tool_call`, `tool_result`, `browser_navigate`, `file_write`, `error`, `complete`
- Runs tools in an actual environment (Docker container, local subprocess, or sandboxed VM)
- Can be paused, resumed, or interrupted by the user

## 2. Backend Implementation for Aether

You need three new components. Tell Kimi Code to implement these:

### A. The Agent Runtime (Core Loop)

Replace your current "receive message → call LLM → return response" flow with this state machine:

```python
# aether/agent_runtime.py
from enum import Enum
from typing import AsyncGenerator, Dict, Any
import asyncio

class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"           # Breaking down user request
    THINKING = "thinking"           # LLM reasoning
    TOOL_CALLING = "tool_calling"   # Executing tools
    OBSERVING = "observing"         # Processing tool results
    COMPILING = "compiling"         # Synthesizing final response
    PAUSED = "paused"               # Waiting for user approval

class AetherRuntime:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = AgentState.IDLE
        self.context = {}  # Working memory
        self.tool_sandbox = DockerSandbox()  # or LocalSandbox
        self.event_queue = asyncio.Queue()
        
    async def run_task(self, user_input: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Main agent loop that yields events to the frontend"""
        
        # 1. Planning Phase
        await self.transition_to(AgentState.PLANNING)
        plan = await self.create_plan(user_input)
        yield self.event("plan_created", {"steps": plan})
        
        for step in plan:
            # 2. Thinking
            await self.transition_to(AgentState.THINKING)
            yield self.event("thinking_start", {"step": step})
            
            thought = await self.llm.think(step, self.context)
            yield self.event("thinking_chunk", {"content": thought})  # Stream tokens
            
            # 3. Tool Detection
            if self.needs_tool(thought):
                await self.transition_to(AgentState.TOOL_CALLING)
                tool_call = self.parse_tool(thought)
                yield self.event("tool_call_start", tool_call)
                
                # Actually execute (this is the "computer")
                result = await self.tool_sandbox.execute(tool_call)
                yield self.event("tool_result", {
                    "output": result.output,
                    "screenshot": result.screenshot,  # For browser tools
                    "logs": result.logs,
                    "exit_code": result.exit_code
                })
                
                # 4. Observation
                await self.transition_to(AgentState.OBSERVING)
                observation = await self.llm.observe(result)
                self.context[step.id] = observation
                
                # Check for user approval gates (semi-autonomous mode)
                if self.requires_approval(tool_call):
                    await self.transition_to(AgentState.PAUSED)
                    yield self.event("approval_required", tool_call)
                    await self.wait_for_approval()  # Blocks until user clicks "Continue"
        
        # 5. Final Compilation
        await self.transition_to(AgentState.COMPILING)
        response = await self.llm.synthesize(self.context)
        yield self.event("response_complete", {"content": response})
        await self.transition_to(AgentState.IDLE)
    
    def event(self, type_: str, payload: dict):
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": self.session_id,
            "state": self.state.value,
            "event_type": type_,
            "payload": payload
        }
```

### B. The Event Bus (Real-time Streaming)

Your WebSocket shouldn't just stream the final LLM response. It should stream **agent lifecycle events**:

```python
# aether/api_server.py (WebSocket handler)
from fastapi import WebSocket

@app.websocket("/ws/agent/{session_id}")
async def agent_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    
    # Subscribe to Redis pub/sub for this session
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"aether:session:{session_id}")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                event = json.loads(message["data"])
                await websocket.send_json(event)
                
                # Frontend receives:
                # {"event_type": "tool_call_start", "payload": {"tool": "browser", "url": "..."}}
                # {"event_type": "browser_navigate", "payload": {"url": "...", "screenshot": "base64..."}}
                # {"event_type": "thinking_chunk", "payload": {"content": "..."}}
                
    except Exception as e:
        await websocket.send_json({"event_type": "error", "payload": str(e)})
```

### C. The Tool Sandbox ("Computer")

This is what Claude's "Computer Use" actually is—a sandboxed environment the agent can see and control:

```python
# aether/sandbox.py
class ComputerSandbox:
    """Actual environment where tools run - not just function calls"""
    
    async def execute_browser(self, url: str):
        # Real browser automation with Playwright
        page = await self.browser.new_page()
        await page.goto(url)
        
        # Take screenshot for the UI
        screenshot = await page.screenshot()
        
        # Get DOM content for LLM context
        content = await page.content()
        
        return {
            "type": "browser_result",
            "url": page.url,
            "screenshot": base64.b64encode(screenshot).decode(),
            "text_content": self.extract_text(content),
            "actions_taken": ["navigate", "screenshot"]
        }
    
    async def execute_code(self, code: str, language: str):
        # Run in Docker container or restricted subprocess
        container = await self.docker.containers.create(
            image=f"aether-sandbox:{language}",
            command=f"python -c '{code}'",
            network_mode="none",  # Security
            mem_limit="512m"
        )
        await container.start()
        logs = await container.logs()
        
        return {
            "type": "code_execution",
            "stdout": logs.stdout,
            "stderr": logs.stderr,
            "files_modified": await self.get_file_changes(container)
        }
```

## 3. UI Patterns That Don't Suck

Based on your images, here's what to steal:

### A. The "Workbench" Layout (Not Chat)

```
┌─────────────────────────────────────────────────────────────┐
│ Sidebar │   Main Area                    │   Right Panel    │
│         │                                │   (Computer)     │
│ Threads │   User: Do research on X       ├──────────────────┤
│         │                                │ 🌐 Browser       │
│ History │   ┌─────────────────────────┐  │ [Live Preview]   │
│         │   │ 🤔 Thinking...          │  │ URL: google.com  │
│         │   │ Breaking down task...   │  │ [Screenshot]     │
│         │   └─────────────────────────┘  ├──────────────────┤
│         │                                │ 🔧 Tools Active  │
│         │   ┌─────────────────────────┐  │ • Search (done)  │
│         │   │ 🔍 Tool: web_search     │  │ • Compare (run)  │
│         │   │ Query: "X vs Y"         │  ├──────────────────┤
│         │   │ Status: Running...      │  │ 📄 Artifacts     │
│         │   └─────────────────────────┘  │ comparison.md    │
│         │                                │ [Edit] [Preview] │
└─────────┴────────────────────────────────┴──────────────────┘
```

**Implementation for Aether:**

Your existing left sidebar is fine. Make the **right sidebar dynamic**:

```typescript
// ui/client/src/components/Workbench.tsx
export function Workbench() {
  const { currentEvent, artifacts } = useAgentStream();
  
  return (
    <div className="w-96 border-l border-gray-800 bg-gray-900 flex flex-col">
      {/* Live Tool View */}
      <div className="flex-1 overflow-y-auto p-4">
        {currentEvent?.event_type === 'browser_navigate' && (
          <BrowserPreview 
            screenshot={currentEvent.payload.screenshot}
            url={currentEvent.payload.url}
          />
        )}
        
        {currentEvent?.event_type === 'tool_call_start' && (
          <ToolCard 
            tool={currentEvent.payload}
            logs={currentEvent.payload.logs}  // Real-time logs
            status="running"
          />
        )}
        
        {currentEvent?.event_type === 'code_execution' && (
          <CodeExecutionView 
            stdout={currentEvent.payload.stdout}
            files={currentEvent.payload.files_modified}
          />
        )}
      </div>
      
      {/* Artifacts Panel (Your existing right sidebar, but live) */}
      <div className="h-1/3 border-t border-gray-800">
        <ArtifactList artifacts={artifacts} />
      </div>
    </div>
  );
}
```

### B. Thinking Blocks That Stream

Don't wait for the LLM to finish thinking. Stream the reasoning tokens in real-time:

```typescript
// components/ThinkingStream.tsx
export function ThinkingStream({ eventStream }) {
  const [thinking, setThinking] = useState('');
  
  useEffect(() => {
    eventStream.on('thinking_chunk', (chunk) => {
      setThinking(prev => prev + chunk.content);
      // Auto-scroll to bottom
    });
  }, []);
  
  return (
    <div className="bg-gray-800 rounded-lg p-3 mb-2 border-l-4 border-yellow-500">
      <div className="flex items-center gap-2 text-yellow-500 text-sm font-medium mb-2">
        <BrainIcon size={16} />
        <span>Thinking...</span>
        <span className="animate-pulse">▋</span>
      </div>
      <div className="text-gray-300 text-sm font-mono whitespace-pre-wrap">
        {thinking}
      </div>
    </div>
  );
}
```

### C. Tool Execution Cards

When the agent uses a tool, show a card that expands with live results:

```typescript
// components/ToolExecutionCard.tsx
export function ToolExecutionCard({ event }) {
  const [expanded, setExpanded] = useState(true);
  
  return (
    <div className="border border-gray-700 rounded-lg mb-2 bg-gray-900">
      <div 
        className="flex items-center justify-between p-3 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          {event.status === 'running' ? (
            <Loader2 className="animate-spin text-blue-500" size={16} />
          ) : (
            <CheckCircle className="text-green-500" size={16} />
          )}
          <span className="font-medium">Using {event.payload.tool}</span>
        </div>
        <ChevronDown className={`transform transition-transform ${expanded ? 'rotate-180' : ''}`} />
      </div>
      
      {expanded && (
        <div className="px-3 pb-3 border-t border-gray-800">
          {/* Show actual parameters */}
          <div className="mt-2 text-xs text-gray-500 font-mono">
            {JSON.stringify(event.payload.parameters, null, 2)}
          </div>
          
          {/* Show live logs/output */}
          {event.payload.logs && (
            <div className="mt-2 bg-black rounded p-2 font-mono text-xs text-green-400 max-h-32 overflow-y-auto">
              {event.payload.logs.map((log, i) => (
                <div key={i}>{log}</div>
              ))}
            </div>
          )}
          
          {/* Show screenshots for browser tools */}
          {event.payload.screenshot && (
            <img 
              src={`data:image/png;base64,${event.payload.screenshot}`}
              className="mt-2 rounded border border-gray-700"
              alt="Browser view"
            />
          )}
        </div>
      )}
    </div>
  );
}
```

## 4. Specific Fixes for Aether Issues

### "Last prompt sent twice"
This is a React state bug or WebSocket echo. Fix:

```typescript
// hooks/useAetherWebSocket.ts
export function useAetherWebSocket() {
  const ws = useRef<WebSocket | null>(null);
  const pendingMessages = useRef<Set<string>>(new Set());
  
  const sendMessage = useCallback((content: string) => {
    const id = crypto.randomUUID();
    
    // Optimistic UI update (show immediately)
    addMessage({ id, content, role: 'user', pending: true });
    
    // Send via WS
    ws.current?.send(JSON.stringify({
      id,  // Dedup ID
      type: 'user_message',
      content,
      timestamp: Date.now()
    }));
    
    pendingMessages.current.add(id);
  }, []);
  
  // When receiving echo from server, check pendingMessages to avoid dupes
  useEffect(() => {
    if (!ws.current) return;
    
    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      // If this is an echo of our message, mark as confirmed
      if (data.event_type === 'message_echo' && pendingMessages.current.has(data.id)) {
        confirmMessage(data.id);
        pendingMessages.current.delete(data.id);
        return;
      }
    };
  }, []);
}
```

### "Past convos not saving right"
Your Redis memory works, but you need **conversation metadata** separate from message content:

```python
# Store conversation list separately from messages
class ConversationStore:
    def save_conversation(self, session_id: str, title: str):
        # ZADD for sorted by timestamp
        redis.zadd("aether:conversations", {
            session_id: datetime.utcnow().timestamp()
        })
        
        # HSET for metadata
        redis.hset(f"aether:conversation:{session_id}", mapping={
            "title": title or "New Chat",
            "updated_at": datetime.utcnow().isoformat(),
            "message_count": redis.llen(f"aether:session:{session_id}:messages"),
            "preview": self.get_first_user_message(session_id)[:100]
        })
    
    def list_conversations(self, user_id: str):
        # Get recent 50 conversations
        session_ids = redis.zrevrange("aether:conversations", 0, 50)
        pipe = redis.pipeline()
        for sid in session_ids:
            pipe.hgetall(f"aether:conversation:{sid}")
        return pipe.execute()
```

### Memory vs Agent State
Separate these two concepts:
- **Memory**: Long-term facts about the user (Redis persistence)
- **Agent State**: Current execution context (ephemeral, per-session)

```python
# memory.py - Long term
class AetherMemory:
    def store_fact(self, key: str, value: str):
        # Stores forever
        redis.set(f"memory:{key}", value)

# runtime.py - Session state  
class AgentRuntime:
    def __init__(self):
        self.working_memory = {}  # Lost when session ends
        self.tool_results = []    # Current task context only
```

## 5. Implementation Roadmap for Kimi Code

Give Kimi Code these specific tasks:

1. **Refactor WebSocket Protocol**: Change from streaming text to streaming JSON events with `event_type`, `payload`, `timestamp`
2. **Create AgentRuntime class**: Implement the state machine loop (IDLE → THINKING → TOOL_CALLING → etc.)
3. **Build Tool Sandbox**: Docker container or subprocess sandbox that can actually run code/browser commands and return screenshots
4. **Update React Components**:
   - Replace simple chat bubbles with `EventRenderer` that switches on `event_type`
   - Create `Workbench` component for right sidebar
   - Add `ThinkingBlock`, `ToolCard`, `BrowserPreview` components
5. **Fix Conversation Persistence**: Add conversation metadata store (ZSET for ordering, HASH for details)
6. **Add Approval Gates**: In `AgentRuntime`, check if tool is "risky" (write file, delete, external API) and emit `approval_required` event, pause loop until user clicks approve in UI

The key insight: **Stop thinking of it as "chat with AI" and start thinking of it as "distributed system observability."** The UI is a dashboard for a running process (the Agent Runtime), not a messaging app.

Want me to draft the specific implementation files for any of these components?