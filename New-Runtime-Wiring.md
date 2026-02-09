Here are the exact changes to align everything with **Agent Runtime V2** (native function calling, fully agentic, no manual approval gates).

## 1. `agent_runtime_v2.py` — Add Cancellation & Multimodal Support

**Location:** Inside the `AgentRuntimeV2` class, add these methods and modify `run_task`.

```python
# ADD after __init__ (around line 55):
        self._current_task: Optional[asyncio.Task] = None
        self._cancelled: bool = False
        self.tools: Dict[str, Callable] = tools or {}

    def set_tools(self, tools: Dict[str, Callable]):
        """Inject tools after initialization (called by API server on startup)."""
        self.tools = tools
        # Re-build schemas with new tools
        # (schemas are built on-demand in _build_tools_schema)

    async def cancel_current_task(self):
        """Cancel the currently running task."""
        self._cancelled = True
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
            await self.emit_event("task_cancelled", {
                "message": "Task cancelled by user",
                "timestamp": datetime.now().isoformat()
            })

# REPLACE run_task method (around line 75) with this version that supports attachments:
    async def run_task(self, user_input: str, attachments: Optional[List[Dict]] = None) -> None:
        """
        Execute task with native function calling.
        Supports multimodal inputs (images).
        """
        self._cancelled = False
        
        # Wrap the actual implementation so we can track the task
        async def _task_impl():
            try:
                await self._execute_task_with_attachments(user_input, attachments)
            except asyncio.CancelledError:
                await self.emit_event("state_changed", {
                    "old_state": self.state.value,
                    "new_state": AgentState.IDLE.value
                })
                raise
        
        self._current_task = asyncio.create_task(_task_impl())
        try:
            await self._current_task
        except asyncio.CancelledError:
            # Ensure we end in IDLE state
            await self.transition_to(AgentState.IDLE)

    async def _execute_task_with_attachments(self, user_input: str, attachments: Optional[List[Dict]]):
        """Internal task execution with attachment handling."""
        try:
            logger.info(f"Starting task: {user_input[:50]}...")
            
            # Build multimodal message if attachments present
            if attachments:
                content = []
                if user_input:
                    content.append({"type": "text", "text": user_input})
                
                for att in attachments:
                    mime_type = att.get("mimeType", att.get("mime_type", "application/octet-stream"))
                    if mime_type.startswith("image/"):
                        # Handle base64 encoded images from frontend
                        image_url = att.get("url")
                        if not image_url and att.get("path"):
                            # Read and encode file
                            import base64
                            from pathlib import Path
                            path = Path(att["path"])
                            if path.exists():
                                with open(path, "rb") as f:
                                    b64 = base64.b64encode(f.read()).decode()
                                image_url = f"data:{mime_type};base64,{b64}"
                        
                        if image_url:
                            content.append({
                                "type": "image_url",
                                "image_url": {"url": image_url}
                            })
                
                self.conversation_history.append({"role": "user", "content": content})
            else:
                self.conversation_history.append({
                    "role": "user",
                    "content": user_input
                })
            
            # Build tools schema for LLM
            tools_schema = self._build_tools_schema()
            
            # Start thinking
            await self.transition_to(AgentState.THINKING)
            await self.emit_event("thinking_start", {
                "message": "Analyzing request..."
            })
            
            # Check cancellation
            if self._cancelled:
                raise asyncio.CancelledError()
            
            # Call LLM with tools
            response = await self._call_llm_with_tools(
                messages=self.conversation_history,
                tools=tools_schema
            )
            
            # Check if LLM wants to use tools
            if response.get("tool_calls"):
                # Execute tools
                await self._execute_tool_calls(response["tool_calls"])
                
                # Check cancellation again
                if self._cancelled:
                    raise asyncio.CancelledError()
                
                # Get final response with tool results
                await self.transition_to(AgentState.RESPONDING)
                await self._stream_final_response()
            else:
                # Direct response - stream it
                await self.transition_to(AgentState.RESPONDING)
                await self._stream_response_content(response.get("content", ""))
                
            await self.transition_to(AgentState.IDLE)
            
        except asyncio.CancelledError:
            logger.info("Task was cancelled")
            await self.transition_to(AgentState.IDLE)
            raise
        except Exception as e:
            logger.exception("Task failed")
            await self.emit_event("error", {"message": str(e)})
            await self.transition_to(AgentState.IDLE)
```

## 2. `agent_websocket.py` — Align to V2 (Remove Approval Gates, Add Tool Registry)

**REMOVE lines 14-15:**
```python
from .agent_runtime import AetherRuntime, AgentState
```

**ADD at line 14:**
```python
from .agent_runtime_v2 import AgentRuntimeV2, AgentState
```

**REMOVE lines 28-31** (the pending_approvals and approval_results dicts):
```python
        self.pending_approvals: Dict[str, asyncio.Event] = {}
        self.approval_results: Dict[str, bool] = {}
```

**REPLACE lines 38-42** (runtime instantiation):
```python
        # Create or get runtime for this session
        if session_id not in self.active_runtimes:
            self.active_runtimes[session_id] = AgentRuntimeV2(
                session_id=session_id,
                llm_client=llm_client,
                tools=self.tool_registry.tools if self.tool_registry else {}
            )
```

**ADD after line 25** (inside __init__, add tool registry storage):
```python
        self.tool_registry = None
        
    def set_tool_registry(self, registry):
        """Inject tool registry from API server on startup."""
        self.tool_registry = registry
```

**REMOVE lines 99-102** (approval handling in message loop):
```python
                    elif msg_type == "approval_response":
                        await self._handle_approval_response(data, session_id)
```

**REMOVE lines 140-175** (the entire approval_required block inside _handle_user_input):
```python
                # Check if approval is needed
                if event.get("event_type") == "approval_required":
                    approval_id = event["payload"]["id"]
                    self.pending_approvals[approval_id] = asyncio.Event()
                    
                    # Send approval request
                    await self._send_event(websocket, event)
                    
                    # Wait for approval response (with timeout)
                    try:
                        await asyncio.wait_for(
                            self.pending_approvals[approval_id].wait(),
                            timeout=300  # 5 minute timeout
                        )
                        
                        # Get approval result
                        approved = self.approval_results.get(approval_id, False)
                        
                        # Resume runtime with approval result
                        await runtime.resume_with_approval(approval_id, approved)
                        
                        # Send approval received event
                        await self._send_event(websocket, {
                            "event_type": "approval_received",
                            "timestamp": datetime.now().isoformat(),
                            "payload": {
                                "id": approval_id,
                                "approved": approved
                            }
                        })
                        
                    except asyncio.TimeoutError:
                        await self._send_event(websocket, {
                            "event_type": "approval_timeout",
                            "timestamp": datetime.now().isoformat(),
                            "payload": {"id": approval_id}
                        })
                        await runtime.resume_with_approval(approval_id, False)
                    
                    # Cleanup
                    del self.pending_approvals[approval_id]
                    if approval_id in self.approval_results:
                        del self.approval_results[approval_id]
                else:
                    # Regular event - just forward it
                    await self._send_event(websocket, event)
```
**REPLACE with:**
```python
                # Forward all V2 events directly to client
                # V2 handles tool decisions natively - no approval gates
                await self._send_event(websocket, event)
```

**REPLACE line 118** (task creation with attachments):
```python
            # Start the task with attachments support
            logger.info("Creating V2 task execution")
            task = asyncio.create_task(runtime.run_task(user_input, attachments=attachments))
```

**REMOVE entire method** `_handle_approval_response` (lines 175-185):
```python
    async def _handle_approval_response(self, data: dict, session_id: str):
        """Handle user response to an approval request."""
        request_id = data.get("request_id")
        approved = data.get("approved", False)
        
        if request_id in self.pending_approvals:
            self.approval_results[request_id] = approved
            self.pending_approvals[request_id].set()
```

**REPLACE the `handle_approval` method** (lines 220-227) with a no-op for backward compatibility:
```python
    async def handle_approval(self, session_id: str, approved: bool):
        """Legacy method - V2 handles approvals natively via LLM."""
        # No-op: V2 runtime makes tool decisions autonomously
        pass
```

## 3. `api_server.py` — Remove Old Endpoint, Wire Tool Registry

**REMOVE the entire `/ws/chat` endpoint** (lines 339-444 approximately, the whole `websocket_chat` function). 

**KEEP only** `/ws/agent/{session_id}` (which is already there around line 500).

**ADD inside `startup_event`** (after line 108 where tool_registry is created):
```python
    # Wire tool registry into Agent Runtime V2
    from .agent_websocket import get_agent_manager
    agent_manager = get_agent_manager()
    agent_manager.set_tool_registry(tool_registry)
    print(f"  → Agent Runtime V2 wired with {len(tool_registry.list_tools())} tools")
```

**REMOVE lines 339-444** (the old `/ws/chat` function).

**If you need vision support** in the new endpoint, ensure the `agent_websocket.py` import at the top of `api_server.py` stays:
```python
from .agent_websocket import get_agent_manager
```

## Summary of Changes

| File | What To Do |
|------|-----------|
| `agent_runtime_v2.py` | Add `cancel_current_task()`, `set_tools()`, and modify `run_task()` to accept `attachments` and handle multimodal (vision) inputs |
| `agent_websocket.py` | Switch import to V2, remove all `pending_approvals` logic, remove `_handle_approval_response`, add `set_tool_registry()` method, pass attachments to runtime |
| `api_server.py` | **Delete** the entire `/ws/chat` endpoint function (the old direct streaming), and inject `tool_registry` into the agent manager during startup |

**Result:** 
- `/ws/agent/{session_id}` becomes your only WebSocket endpoint
- Fully native function calling (LLM decides tools, no human-in-the-loop approval gates)
- Supports multimodal inputs (images) via the V2 runtime
- Tools are injected from the registry on startup
- Tasks can be cancelled via the `cancel_task` message type