"""
Aether Agent Runtime - Event-driven State Machine

================================================================================
CORE ARCHITECTURE
================================================================================
The AgentRuntime orchestrates the plan→act→observe loop with granular 
event streaming to the frontend. It's designed for observability and control.

State Machine:
    IDLE → PLANNING → THINKING → TOOL_CALLING → OBSERVING → THINKING → IDLE
              ↑                                          ↓
              └──────────────── PAUSED (approval gates) ─┘

CANONICAL LOOP:
    UI → AetherRuntime →
       (A) No tools needed → call LiteLLM → return model response
       (B) Tools needed → stream events to UI →
           run tools →
           send results to LiteLLM →
           return model response

RULE: The runtime NEVER writes user-facing text. Only the model does.

Event Types:
    - state_change:     State machine transitions
    - plan_created:     Multi-step plan generated
    - thinking_start:   Agent begins reasoning
    - thinking_chunk:   Streaming reasoning tokens
    - thinking_complete: Reasoning finished
    - tool_call_start:  Tool execution begins
    - tool_call_chunk:  Live output from tool (logs, progress)
    - tool_result:      Tool execution completed
    - tool_call_failed: Tool execution error
    - approval_required: Pause for user approval
    - approval_received: User approved/denied
    - step_complete:    Plan step finished
    - response_chunk:   Final response streaming from LLM
    - response_complete: Task finished
    - error:            Runtime error

================================================================================
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, AsyncGenerator, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent runtime states"""
    IDLE = "idle"
    PLANNING = "planning"
    THINKING = "thinking"
    TOOL_CALLING = "tool_calling"
    OBSERVING = "observing"
    PAUSED = "paused"


@dataclass
class PlanStep:
    """A single step in the agent's plan"""
    description: str
    tool_types: List[str] = field(default_factory=list)
    expected_output: Optional[str] = None
    step_number: int = 0


@dataclass
class ToolExecution:
    """Record of a tool execution"""
    id: str
    tool: str
    params: Dict[str, Any]
    status: str = "pending"
    output: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    screenshot: Optional[str] = None
    files_modified: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    requires_approval: bool = False


@dataclass  
class ApprovalRequest:
    """Request for user approval"""
    id: str
    tool: str
    params: Dict[str, Any]
    operation_description: str
    risk_level: str = "medium"
    requester_info: Optional[Dict[str, Any]] = None


class AetherRuntime:
    """
    Core agent runtime implementing event-driven state machine.
    
    Responsibilities:
    - Manage state transitions
    - Orchestrate plan→act→observe cycles
    - Stream granular lifecycle events
    - Handle approval gates (semi-autonomous mode)
    - Manage working memory (ephemeral task context)
    
    CRITICAL RULE: The runtime NEVER generates user-facing text.
    Only the LLM generates responses. The runtime only orchestrates.
    
    Usage:
        runtime = AetherRuntime(session_id="abc-123", llm=nvidia_client)
        async for event in runtime.run_task("Analyze this codebase"):
            # Stream to WebSocket
            await websocket.send_json(event)
    """
    
    def __init__(
        self, 
        session_id: str,
        memory=None,
        llm=None,
        sandbox=None,
        fabric_client=None
    ):
        self.session_id = session_id
        self.memory = memory  # Long-term memory (Redis)
        self.llm = llm      # LLM client for completions
        self.sandbox = sandbox  # Sandbox for code execution
        self.fabric_client = fabric_client  # Fabric MCP client
        
        # State
        self.state = AgentState.IDLE
        self.working_memory: Dict[str, Any] = {}  # Ephemeral session state
        self.current_plan: List[PlanStep] = []
        self.current_step_index = 0
        self.tool_history: List[ToolExecution] = []
        self.current_task: Optional[asyncio.Task] = None
        
        # Approval handling
        self.pending_approval: Optional[ApprovalRequest] = None
        self.approval_event = asyncio.Event()
        
        # Event queue for streaming
        self.event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        
        # Conversation history for LLM context
        self.conversation_history: List[Dict[str, str]] = []
        
    # =========================================================================
    # State Management
    # =========================================================================
    
    async def transition_to(self, new_state: AgentState):
        """Transition to a new state and emit event."""
        old_state = self.state
        self.state = new_state
        
        logger.info(f"State transition: {old_state.value} -> {new_state.value}")
        
        await self.emit_event("state_changed", {
            "old_state": old_state.value,
            "new_state": new_state.value,
            "session_id": self.session_id
        })
        
        logger.debug(f"State transition: {old_state.value} → {new_state.value}")
    
    async def emit_event(self, event_type: str, payload: Dict[str, Any]):
        """Emit a lifecycle event."""
        event = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "payload": payload
        }
        await self.event_queue.put(event)
    
    # =========================================================================
    # Main Task Loop - Canonical Agent Loop
    # =========================================================================
    
    async def run_task(
        self, 
        user_input: str, 
        attachments: Optional[List[Dict]] = None
    ) -> None:
        """
        Execute a user task with full event streaming.
        
        CANONICAL LOOP:
        1. Decide if tools are needed
        2. If NO tools: Single LLM call → return model response
        3. If tools: Run tools with events → LLM call with results → return model response
        
        CRITICAL: The runtime NEVER generates user-facing text. Only the LLM does.
        """
        logger.info("ENTERING run_task method")
        try:
            logger.info(f"Starting task: {user_input[:50]}...")
            logger.info(f"Current state: {self.state.value}")
            
            # Store user input
            self.working_memory["user_input"] = user_input
            self.working_memory["attachments"] = attachments or []
            self.tool_history = []
            
            # Add user message to conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            
            # Step 1: Planning - decide if tools are needed
            await self.transition_to(AgentState.PLANNING)
            plan = await self._create_plan(user_input, attachments)
            self.current_plan = plan
            
            logger.info(f"Plan created: {len(plan)} steps, tools needed: {any(step.tool_types for step in plan)}")
            
            await self.emit_event("plan_created", {
                "steps": [
                    {
                        "description": step.description,
                        "tool_types": step.tool_types,
                        "expected_output": step.expected_output,
                        "step_number": step.step_number
                    }
                    for step in plan
                ],
                "tools_needed": len(plan) > 0 and any(
                    step.tool_types for step in plan
                )
            })
            
            # Determine if we need tools
            tools_needed = any(step.tool_types for step in plan)
            logger.info(f"Tools needed: {tools_needed}")
            
            if not tools_needed:
                # ============================================
                # PATH A: No tools needed - Direct LLM call
                # ============================================
                logger.info("Taking PATH A: Direct LLM call")
                await self.transition_to(AgentState.THINKING)
                
                # Call LLM directly with user input
                response_text = await self._call_llm_for_response(
                    messages=self.conversation_history,
                    stream=True
                )
                
                # Add assistant response to history
                self.conversation_history.append({"role": "assistant", "content": response_text})
                
                await self.transition_to(AgentState.IDLE)
                
            else:
                # ============================================
                # PATH B: Tools needed - Run tools then LLM
                # ============================================
                logger.info("Taking PATH B: Tools then LLM")
                tool_results = []
                
                for i, step in enumerate(plan):
                    self.current_step_index = i
                    
                    # Tool selection and execution
                    step_tools = self._determine_tools(step)
                    
                    for tool_spec in step_tools:
                        await self.transition_to(AgentState.TOOL_CALLING)
                        
                        # Check if approval needed
                        if self._requires_approval(tool_spec):
                            approval = await self._request_approval(tool_spec)
                            self.pending_approval = approval
                            
                            await self.emit_event("approval_required", {
                                "id": approval.id,
                                "tool": approval.tool,
                                "params": approval.params,
                                "operation_description": approval.operation_description,
                                "risk_level": approval.risk_level
                            })
                            
                            # Wait for approval
                            await self.approval_event.wait()
                            self.approval_event.clear()
                            
                            if not getattr(self, '_approval_result', False):
                                await self.emit_event("tool_call_cancelled", {
                                    "tool": tool_spec["tool"],
                                    "reason": "User denied approval"
                                })
                                continue
                        
                        # Execute tool
                        tool_exec = await self._execute_tool(tool_spec)
                        self.tool_history.append(tool_exec)
                        
                        # Observing
                        await self.transition_to(AgentState.OBSERVING)
                        observation = await self._observe(tool_exec)
                        
                        tool_results.append({
                            "tool": tool_exec.tool,
                            "output": tool_exec.output,
                            "observation": observation
                        })
                    
                    await self.emit_event("step_complete", {
                        "step_index": i,
                        "description": step.description
                    })
                
                # After all tools complete, call LLM with results
                await self.transition_to(AgentState.THINKING)
                
                # Build final prompt with tool results
                final_messages = self._build_final_prompt_with_results(
                    user_input=user_input,
                    tool_results=tool_results
                )
                
                # Call LLM with tool results
                response_text = await self._call_llm_for_response(
                    messages=final_messages,
                    stream=True
                )
                
                # Add to conversation history
                self.conversation_history.append({"role": "user", "content": user_input})
                self.conversation_history.append({"role": "assistant", "content": response_text})
                
                await self.transition_to(AgentState.IDLE)
        
        except Exception as e:
            logger.exception("Task execution error")
            await self.emit_event("error", {
                "message": str(e),
                "type": type(e).__name__
            })
            await self.transition_to(AgentState.IDLE)
        
        finally:
            # Clear working memory for this task
            self.current_plan = []
            self.current_step_index = 0
    
    async def _call_llm_for_response(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True
    ) -> str:
        """
        Call the LLM to generate a response.
        
        This is the ONLY place that generates user-facing text.
        All responses come from the model, never from the runtime.
        """
        if not self.llm:
            raise RuntimeError("LLM client not available")
        
        full_response = ""
        
        await self.emit_event("thinking_start", {
            "reason": "Calling LLM for final response"
        })
        
        try:
            if stream:
                # Stream response chunks
                async for chunk in self.llm.complete_stream(
                    messages=messages,
                    temperature=0.7
                ):
                    # Skip usage metadata chunks
                    if chunk.startswith("__USAGE__:"):
                        continue
                    
                    full_response += chunk
                    await self.emit_event("response_chunk", {"chunk": chunk})
            else:
                # Non-streaming response
                response = await self.llm.complete(
                    messages=messages,
                    temperature=0.7,
                    stream=False
                )
                full_response = response.content
                await self.emit_event("response_chunk", {"chunk": full_response})
        
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
        
        await self.emit_event("response_complete", {
            "response": full_response,
            "steps_executed": len(self.current_plan),
            "tools_used": len(self.tool_history)
        })
        
        return full_response
    
    def _build_final_prompt_with_results(
        self,
        user_input: str,
        tool_results: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Build the final prompt for the LLM including tool results.
        
        The LLM summarizes the tool results to answer the user's request.
        """
        # Build tool results text
        results_text = "\n\n".join([
            f"Tool: {r['tool']}\nOutput: {r['output']}\nObservation: {r['observation']}"
            for r in tool_results
        ])
        
        # System prompt
        system_prompt = """You are an AI assistant that helps users by using tools when needed.
You have just executed some tools to help answer the user's request.
Summarize the tool results clearly and answer the user's original question.
Be concise but complete."""
        
        # User prompt with tool results
        user_prompt = f"""The user asked: {user_input}

Here are the results from the tools I executed:

{results_text}

Please provide a helpful response based on these results."""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    async def _create_plan(
        self, 
        user_input: str, 
        attachments: Optional[List[Dict]]
    ) -> List[PlanStep]:
        """
        Create a multi-step plan for the task.
        
        Returns empty plan if no tools are needed (direct LLM response).
        """
        plan = []
        user_lower = user_input.lower()
        
        logger.info(f"Creating plan for input: {user_input[:50]}...")
        
        # Simple keyword-based planning
        # Check for web-related tasks first (most common)
        if any(kw in user_lower for kw in ["search", "web", "browser", "internet", "look up"]):
            logger.info("Detected web search task")
            plan.append(PlanStep(
                description="Search the web for information",
                tool_types=["web_search"],
                step_number=1
            ))
        
        # Check for code-related tasks
        elif any(kw in user_lower for kw in ["code", "write", "function", "script", "implement"]):
            logger.info("Detected code execution task")
            plan.append(PlanStep(
                description="Write and execute code",
                tool_types=["code_execution"],
                step_number=1
            ))
        
        # Check for file operations
        elif any(kw in user_lower for kw in ["file", "read file", "analyze document"]):
            logger.info("Detected file read task")
            plan.append(PlanStep(
                description="Read and analyze files",
                tool_types=["file_read"],
                step_number=1
            ))
        
        else:
            logger.info("No tools needed - direct LLM response")
        
        return plan
    
    def _determine_tools(self, step: PlanStep) -> List[Dict]:
        """Determine which tools to execute based on step."""
        tools = []
        
        for tool_type in step.tool_types:
            if tool_type == "code_execution":
                tools.append({
                    "tool": "execute_code",
                    "params": {"language": "python", "code": "# Code execution"},
                    "description": "Execute Python code"
                })
            elif tool_type == "file_read":
                tools.append({
                    "tool": "read_file",
                    "params": {"path": "/workspace/file.txt"},
                    "description": "Read file contents"
                })
            elif tool_type == "web_search":
                tools.append({
                    "tool": "web_search",
                    "params": {"query": self.working_memory.get("user_input", "")},
                    "description": "Search the web"
                })
            elif tool_type == "browser":
                tools.append({
                    "tool": "browser_navigate",
                    "params": {"url": "https://example.com"},
                    "description": "Navigate to website"
                })
        
        return tools
    
    def _requires_approval(self, tool_spec: Dict) -> bool:
        """Determine if a tool execution requires user approval."""
        high_risk_tools = ["execute_code", "write_file", "shell_command", "delete_file"]
        return tool_spec["tool"] in high_risk_tools
    
    async def _request_approval(self, tool_spec: Dict) -> ApprovalRequest:
        """Create an approval request for a tool."""
        tool = tool_spec["tool"]
        if tool in ["shell_command", "delete_file"]:
            risk_level = "high"
        elif tool in ["write_file"]:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        return ApprovalRequest(
            id=str(uuid.uuid4()),
            tool=tool,
            params=tool_spec["params"],
            operation_description=tool_spec["description"],
            risk_level=risk_level,
            requester_info={"session_id": self.session_id}
        )
    
    async def _execute_tool(self, tool_spec: Dict) -> ToolExecution:
        """Execute a tool and return the execution record."""
        tool_id = str(uuid.uuid4())
        
        tool_exec = ToolExecution(
            id=tool_id,
            tool=tool_spec["tool"],
            params=tool_spec["params"],
            status="running",
            started_at=datetime.now().isoformat()
        )
        
        await self.emit_event("tool_call_start", {
            "tool_id": tool_id,
            "tool": tool_spec["tool"],
            "params": tool_spec["params"],
            "requires_approval": False
        })
        
        try:
            # Simulate tool execution (in production, call actual tools)
            await asyncio.sleep(0.5)
            
            # Simulate logs
            logs = [f"Starting {tool_spec['tool']}...", "Processing...", "Complete."]
            for log in logs:
                await asyncio.sleep(0.1)
                tool_exec.logs.append(log)
                await self.emit_event("tool_call_chunk", {
                    "tool_id": tool_id,
                    "chunk": log
                })
            
            # Mock result
            tool_exec.output = f"Result from {tool_spec['tool']}"
            tool_exec.status = "completed"
            
        except Exception as e:
            tool_exec.status = "failed"
            tool_exec.output = str(e)
            await self.emit_event("tool_call_failed", {
                "tool_id": tool_id,
                "error": str(e)
            })
        
        tool_exec.ended_at = datetime.now().isoformat()
        
        await self.emit_event("tool_call_complete", {
            "tool_id": tool_id,
            "tool": tool_exec.tool,
            "result": tool_exec.output,
            "status": tool_exec.status,
            "logs": tool_exec.logs
        })
        
        return tool_exec
    
    async def _observe(self, tool_exec: ToolExecution) -> str:
        """Observe and analyze tool execution results."""
        return f"Observed: {tool_exec.output}"
    
    # =========================================================================
    # External Control
    # =========================================================================
    
    async def resume_with_approval(self, approval_id: str, approved: bool):
        """Resume execution after receiving user approval."""
        if self.pending_approval and self.pending_approval.id == approval_id:
            self._approval_result = approved
            self.pending_approval = None
            self.approval_event.set()
    
    async def cancel_current_task(self):
        """Cancel the currently running task."""
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            try:
                await self.current_task
            except asyncio.CancelledError:
                pass
    
    # =========================================================================
    # Event Streaming
    # =========================================================================
    
    def __aiter__(self):
        """Make runtime async iterable for event streaming."""
        return self
    
    async def __anext__(self) -> Dict[str, Any]:
        """Get next event from queue."""
        return await self.event_queue.get()
