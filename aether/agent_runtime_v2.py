"""
Aether Agent Runtime V2 - Native Function Calling

This runtime uses native LLM function calling:
1. User sends message
2. LLM decides which tools to call (if any)
3. Runtime executes tools
4. Results are fed back to the LLM
5. LLM produces final response
"""

import asyncio
import base64
import inspect
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Safety limit: maximum number of LLM↔tool rounds before forcing a final response
# Note: Agent can call checkpoint_and_continue to reset this counter for long tasks
MAX_TOOL_ROUNDS = 30


class AgentState(Enum):
    """Agent runtime states."""

    IDLE = "idle"
    THINKING = "thinking"
    TOOL_CALLING = "tool_calling"
    OBSERVING = "observing"
    RESPONDING = "responding"
    PAUSED = "paused"


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""

    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class ToolExecution:
    """Record of tool execution for UI."""

    id: str
    tool: str
    params: Dict[str, Any]
    status: str = "pending"
    output: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class AgentRuntimeV2:
    """
    Agent runtime with native function calling.

    The LLM decides which tools to use. The runtime executes them.
    """

    def __init__(
        self,
        session_id: str,
        llm_client: Any = None,
        tools: Optional[Dict[str, Callable[..., Any]]] = None,
        memory: Optional[Any] = None,
        sandbox: Any = None,
        system_prompt: Optional[str] = None,
    ):
        self.session_id = session_id
        self.llm = llm_client
        self.tools: Dict[str, Callable[..., Any]] = tools or {}
        self.memory = memory
        self.sandbox = sandbox

        self.state = AgentState.IDLE
        self.event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.conversation_history: List[Dict[str, Any]] = []

        # Context Management
        self._tokens_used: int = 0
        self._max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "32768"))
        self._checkpoint_engine: Optional[Any] = None
        self._last_usage_meta: Dict[str, Any] = {}

        # Token Budgeting (production-grade allocation)
        self._token_budget = {
            "system_prompt": int(self._max_context_tokens * 0.10),  # 10% for system
            "tools_schema": int(self._max_context_tokens * 0.15),   # 15% for tools
            "history": int(self._max_context_tokens * 0.60),        # 60% for conversation
            "response": int(self._max_context_tokens * 0.15),       # 15% for response
        }

        # Sliding window config
        self._max_history_messages = int(os.getenv("MAX_HISTORY_MESSAGES", "50"))
        self._compression_threshold = 0.60  # Compress at 60% capacity
        self._warning_threshold = 0.75      # Warn at 75% capacity
        self._critical_threshold = 0.85     # Emergency compress at 85%
        
        self._context_warning_sent = False  # Track if we've warned the agent
        self._flush_triggered = False        # Track if agentic flush has been triggered this cycle
        self._agentic_flush_enabled = os.getenv("AGENTIC_FLUSH_ENABLED", "true").lower() == "true"

        # Track if we've sent tools schema (cache optimization)
        self._tools_schema_sent = False
        self._cached_tools_schema: List[Dict[str, Any]] = []

        # Inject system prompt at the start of the conversation
        if system_prompt:
            self.conversation_history.append(
                {"role": "system", "content": system_prompt}
            )

        self._current_task: Optional[asyncio.Task[Any]] = None
        self._cancelled: bool = False

    def set_tools(self, tools: Dict[str, Callable[..., Any]]) -> None:
        """Inject tools after initialization."""
        self.tools = tools

    def add_tool(self, name: str, tool_fn: Callable[..., Any]) -> None:
        """Add a single tool mid-session (for dynamic tool activation).
        
        Automatically invalidates cached schemas so the next LLM call
        includes the newly added tool.
        """
        self.tools[name] = tool_fn
        self.invalidate_tools_schema()
        logger.info(f"Tool '{name}' added to runtime (session: {self.session_id})")

    def invalidate_tools_schema(self) -> None:
        """Clear cached tool schemas so they are rebuilt on next LLM call."""
        self._cached_tools_schema = []
        self._tools_schema_sent = False

    async def cancel_current_task(self) -> None:
        """Cancel the currently running task."""
        self._cancelled = True
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            try:
                await self._current_task
            except asyncio.CancelledError:
                pass
            await self.emit_event(
                "task_cancelled",
                {
                    "message": "Task cancelled by user",
                    "timestamp": datetime.now().isoformat(),
                },
            )

    async def emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit lifecycle event."""
        await self.event_queue.put(
            {
                "event_type": event_type,
                "timestamp": datetime.now().isoformat(),
                "payload": payload,
            }
        )

    async def transition_to(self, new_state: AgentState) -> None:
        """Transition state and emit event."""
        old_state = self.state
        self.state = new_state
        await self.emit_event(
            "state_changed",
            {"old_state": old_state.value, "new_state": new_state.value},
        )

    async def run_task(
        self, user_input: str, attachments: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Execute task with native function calling.

        Supports multimodal inputs (images).
        """
        self._cancelled = False

        async def _task_impl() -> None:
            try:
                await self._execute_task_with_attachments(user_input, attachments or [])
            except asyncio.CancelledError:
                await self.emit_event(
                    "state_changed",
                    {
                        "old_state": self.state.value,
                        "new_state": AgentState.IDLE.value,
                    },
                )
                raise

        self._current_task = asyncio.create_task(_task_impl())
        try:
            await self._current_task
        except asyncio.CancelledError:
            await self.transition_to(AgentState.IDLE)

    async def _execute_task_with_attachments(
        self, user_input: str, attachments: List[Dict[str, Any]]
    ) -> None:
        """Internal task execution with multi-round agentic tool-use loop."""
        try:
            logger.info("Starting task: %s...", user_input[:50] if user_input else "(no text)")

            # Inject time context for temporal awareness
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            time_context = f" [Current Time: {current_time}]"

            self.conversation_history.append(
                {"role": "user", "content": self._build_user_content(user_input + time_context, attachments)}
            )

            tools_schema = await self._build_tools_schema()
            round_count = 0

            # ── Agentic loop: LLM → tools → LLM → tools → ... → final response ──
            consecutive_errors = 0
            MAX_CONSECUTIVE_ERRORS = 3

            while round_count < MAX_TOOL_ROUNDS:
                round_count += 1

                if self._cancelled:
                    raise asyncio.CancelledError()

                # CRITICAL: Check and compress context BEFORE calling LLM
                await self._check_and_compress_context()

                await self.transition_to(AgentState.THINKING)
                await self.emit_event(
                    "thinking_start",
                    {"message": f"Analyzing request (round {round_count})..."},
                )

                # Graceful error handling: wrap LLM call so transient failures
                # don't kill the entire agentic loop
                try:
                    response = await self._call_llm_with_tools(
                        messages=self.conversation_history, tools=tools_schema
                    )
                    consecutive_errors = 0  # Reset on success
                except asyncio.CancelledError:
                    raise
                except Exception as llm_err:
                    consecutive_errors += 1
                    error_msg = f"LLM call failed (attempt {consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}): {llm_err}"
                    logger.error(error_msg)
                    await self.emit_event("error", {"message": error_msg, "recoverable": True})

                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        # Too many consecutive failures — give up gracefully
                        await self.transition_to(AgentState.RESPONDING)
                        await self._stream_response_content(
                            f"I encountered repeated errors communicating with the model. "
                            f"Last error: {llm_err}\n\n"
                            f"Please try again or switch to a different model/provider."
                        )
                        break

                    # Wait briefly and retry
                    await asyncio.sleep(min(2 ** consecutive_errors, 10))
                    continue

                tool_calls = self._normalize_tool_calls(
                    response.get("tool_calls") or []
                )

                # Fallback: Proactively parse markdown tool calls if native ones are missing
                if not tool_calls and response.get("content"):
                    content = response["content"]
                    parsed = self._parse_tool_calls_from_text(content)
                    if parsed["tool_calls"]:
                        logger.info(
                            "Proactively parsed %d tool calls from assistant text",
                            len(parsed["tool_calls"]),
                        )
                        tool_calls = self._normalize_tool_calls(parsed["tool_calls"])
                        # Strip the tool blocks from content so we don't duplicate them in history
                        response["content"] = parsed["content"]

                if not tool_calls:
                    # LLM chose not to call any tools — emit final response
                    await self.transition_to(AgentState.RESPONDING)
                    content = str(response.get("content", ""))
                    await self._stream_response_content(content)
                    break

                # Execute the tool calls and feed results back into history
                content = str(response.get("content", ""))
                if content:
                    await self._stream_thought_content(content)

                try:
                    loop_reset = await self._execute_tool_calls(tool_calls, content=content)
                except asyncio.CancelledError:
                    raise
                except Exception as tool_err:
                    # Tool execution failed — log error as a tool result so the LLM sees it
                    logger.error("Tool execution batch failed: %s", tool_err)
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": content or "",
                        "tool_calls": [
                            {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}}
                            for tc in tool_calls
                        ],
                    })
                    for tc in tool_calls:
                        self.conversation_history.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": f"Error: Tool execution failed: {tool_err}",
                        })
                    await self.emit_event("error", {"message": f"Tool error (recoverable): {tool_err}", "recoverable": True})
                    loop_reset = False

                # If a tool requested a loop reset (episodic execution), reset the round counter
                if loop_reset:
                    logger.info("Resetting round counter for episodic execution - continuing with fresh loop")
                    await self.emit_event(
                        "loop_reset",
                        {
                            "previous_round": round_count,
                            "message": "Loop counter reset for episodic execution. Continuing task with fresh context.",
                        },
                    )
                    round_count = 0  # Reset for the next episode

                # Update token usage from LLM response metadata if available
                usage = response.get("usage") or {}
                if usage:
                    self._last_usage_meta = usage
                    self._tokens_used = usage.get("total_tokens") or self._tokens_used
                    logger.info("Updated session tokens from LLM usage: %d", self._tokens_used)
                else:
                    # Fallback token estimation
                    try:
                        from .checkpoint_adapter import TokenCounter
                        tc = TokenCounter()
                        self._tokens_used = tc.count_messages(self.conversation_history)
                    except Exception:
                        pass
                    logger.info("Estimated session tokens: %d", self._tokens_used)

                # Emit usage update to frontend for context gauge
                await self.emit_event("usage_update", {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": self._tokens_used,
                    "max_tokens": self._max_context_tokens,
                    "percent": min(round((self._tokens_used / self._max_context_tokens) * 100), 100) if self._max_context_tokens > 0 else 0,
                    "model": response.get("model", ""),
                })

                logger.info(
                    "Completed tool round %d/%d — current tokens: %d — looping back to LLM",
                    round_count,
                    MAX_TOOL_ROUNDS,
                    self._tokens_used,
                )

            else:
                # Safety: hit max rounds without the LLM stopping
                logger.warning(
                    "Hit MAX_TOOL_ROUNDS (%d) — forcing final response",
                    MAX_TOOL_ROUNDS,
                )
                await self.transition_to(AgentState.RESPONDING)
                await self._stream_final_response()

            await self.transition_to(AgentState.IDLE)

        except asyncio.CancelledError:
            logger.info("Task was cancelled")
            await self.transition_to(AgentState.IDLE)
            raise
        except Exception as exc:
            logger.exception("Task failed")
            await self.emit_event("error", {"message": str(exc)})
            await self.transition_to(AgentState.IDLE)

    def _build_user_content(
        self, user_input: str, attachments: List[Dict[str, Any]]
    ) -> Any:
        """Build text-only or multimodal user content.

        Handles three attachment sources:
        1. ``url`` — direct URL (already usable)
        2. ``path`` — local file path (read and base64-encode)
        3. ``content`` — base64 data from the frontend FileReader API
           (may be a full data URL or raw base64)
        """
        if not attachments:
            return user_input

        content: List[Dict[str, Any]] = []
        if user_input:
            content.append({"type": "text", "text": user_input})

        for attachment in attachments:
            mime_type = attachment.get("mimeType", attachment.get("mime_type", ""))
            if not mime_type.startswith("image/"):
                continue

            image_url = attachment.get("url")

            # Try local file path
            if not image_url and attachment.get("path"):
                path = Path(str(attachment["path"]))
                if path.exists() and path.is_file():
                    image_url = self._file_to_data_url(path, mime_type)

            # Try base64 content from frontend (primary path for browser uploads)
            if not image_url and attachment.get("content"):
                raw = attachment["content"]
                if raw.startswith("data:"):
                    # Already a full data URL — use directly
                    image_url = raw
                else:
                    # Raw base64 without prefix — wrap it
                    image_url = f"data:{mime_type};base64,{raw}"

            if image_url:
                content.append({"type": "image_url", "image_url": {"url": image_url}})
                logger.info("Attached image to message: %s (%s, %d chars)",
                            attachment.get("filename", "unnamed"), mime_type, len(image_url))

        return content if content else user_input

    def _file_to_data_url(self, path: Path, mime_type: str) -> str:
        """Encode file content as data URL for multimodal requests."""
        with open(path, "rb") as file_obj:
            encoded = base64.b64encode(file_obj.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    async def _build_tools_schema(self) -> List[Dict[str, Any]]:
        """Build OpenAI-style tools schema from available tools (with aggressive caching)."""
        # Use in-memory cache first (fastest)
        if self._cached_tools_schema:
            logger.debug("Using in-memory cached tool schema")
            return self._cached_tools_schema

        # Try to get from Redis cache
        if self.memory:
            cached_schema = await self.memory.get_tool_schema(self.session_id)
            if cached_schema:
                logger.debug("Using Redis cached tool schema for session %s", self.session_id)
                self._cached_tools_schema = cached_schema  # Cache in memory too
                return cached_schema

        # Build fresh schema (only happens once per session)
        schemas: List[Dict[str, Any]] = []

        for name, tool_fn in self.tools.items():
            schema = getattr(tool_fn, "__tool_schema__", None) or {}
            parameters = schema.get("parameters") or {"type": "object", "properties": {}}
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": schema.get("description", f"Execute {name}"),
                        "parameters": parameters,
                    },
                }
            )

        # Store in both caches
        self._cached_tools_schema = schemas  # In-memory cache
        if self.memory and schemas:
            await self.memory.store_tool_schema(self.session_id, schemas)
            logger.debug("Cached tool schema for session %s", self.session_id)

        return schemas

    async def _call_llm_with_tools(
        self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Call LLM with tools and return response."""
        if not self.llm:
            raise RuntimeError("LLM client not available")
        if not hasattr(self.llm, "complete_with_tools"):
            raise RuntimeError("LLM client does not support complete_with_tools")
        try:
            return await self.llm.complete_with_tools(
                messages=messages,
                tools=tools,
            )
        except Exception as exc:
            message = str(exc).lower()
            tools_unsupported = any(
                hint in message
                for hint in (
                    "tool",
                    "function calling",
                    "tool_choice",
                    "does not support",
                )
            )
            if tools_unsupported and hasattr(self.llm, "complete"):
                logger.warning(
                    "Tool-calling failed; falling back to text-based tool parsing: %s",
                    exc,
                )
                response = await self.llm.complete(
                    messages=messages,
                    stream=False,
                    temperature=0.7,
                )
                content = getattr(response, "content", str(response))
                parsed = self._parse_tool_calls_from_text(content)
                return parsed
            raise

    def _parse_tool_calls_from_text(self, text: str) -> Dict[str, Any]:
        """Parse ```tool_call blocks from LLM text output.

        Returns a dict with 'content' (text without tool blocks) and 'tool_calls'.
        """
        import re

        tool_calls: List[Dict[str, Any]] = []
        # Match ```tool_call ... ``` blocks
        pattern = r"```tool_call\s*\n(.*?)\n```"
        matches = re.findall(pattern, text, re.DOTALL)

        for idx, match in enumerate(matches):
            try:
                parsed = json.loads(match.strip())
                name = parsed.get("name", "")
                arguments = parsed.get("arguments", {})

                # Validate the tool exists
                if name in self.tools:
                    tool_calls.append({
                        "id": f"text_call_{uuid.uuid4().hex[:8]}",
                        "name": name,
                        "arguments": arguments,
                    })
                    logger.info("Parsed text-based tool call: %s(%s)", name, arguments)
                else:
                    logger.warning("LLM tried to call unknown tool: %s", name)
            except json.JSONDecodeError as e:
                logger.warning("Failed to parse tool_call block: %s", e)

        # Strip tool_call blocks from the content
        remaining_content = re.sub(pattern, "", text, flags=re.DOTALL).strip()

        return {"content": remaining_content, "tool_calls": tool_calls}

    def _normalize_tool_calls(self, tool_calls: List[Any]) -> List[ToolCall]:
        """Normalize LLM tool calls into a consistent internal shape."""
        normalized: List[ToolCall] = []

        for idx, raw_call in enumerate(tool_calls):
            if isinstance(raw_call, ToolCall):
                normalized.append(raw_call)
                continue

            if not isinstance(raw_call, dict):
                continue

            call_id = str(raw_call.get("id") or f"call_{idx}")
            name = str(raw_call.get("name") or "")
            arguments = raw_call.get("arguments") or {}

            if not name and isinstance(raw_call.get("function"), dict):
                fn_data = raw_call["function"]
                name = str(fn_data.get("name") or "")
                arguments = fn_data.get("arguments") or arguments

            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except Exception:
                    arguments = {}

            if not isinstance(arguments, dict):
                arguments = {}

            if name:
                normalized.append(ToolCall(id=call_id, name=name, arguments=arguments))

        return normalized

    async def _execute_tool_calls(
        self, tool_calls: List[ToolCall], content: Optional[str] = None
    ) -> bool:
        """Execute tool calls from LLM.

        Returns True if any tool requested a loop reset, False otherwise.
        """
        await self.transition_to(AgentState.TOOL_CALLING)

        assistant_tool_calls: List[Dict[str, Any]] = []
        for call in tool_calls:
            assistant_tool_calls.append(
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                }
            )

        self.conversation_history.append(
            {
                "role": "assistant",
                "content": content or "",
                "tool_calls": assistant_tool_calls,
            }
        )

        tasks = [self._execute_single_tool(call) for call in tool_calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        loop_reset_requested = False

        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                call_id = tool_calls[idx].id if idx < len(tool_calls) else f"call_{idx}"
                output = f"Error: {result}"
                self.conversation_history.append(
                    {"role": "tool", "tool_call_id": call_id, "content": output}
                )
            else:
                # Check if the tool requested a loop reset
                if result.get("_reset_loop_requested"):
                    loop_reset_requested = True
                    logger.info("Tool '%s' requested loop reset for episodic execution", tool_calls[idx].name if idx < len(tool_calls) else "unknown")

                self.conversation_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": result["tool_call_id"],
                        "content": result["output"],
                    }
                )

        await self.transition_to(AgentState.OBSERVING)
        return loop_reset_requested

    async def _execute_single_tool(self, tool_call: ToolCall) -> Dict[str, Any]:
        """Execute a single tool and return result."""
        if self._cancelled:
            raise asyncio.CancelledError()

        tool_name = tool_call.name
        tool_id = tool_call.id
        arguments = tool_call.arguments

        execution = ToolExecution(
            id=str(uuid.uuid4()),
            tool=tool_name,
            params=arguments,
            status="running",
            started_at=datetime.now().isoformat(),
        )
        await self.emit_event(
            "tool_call_start",
            {"tool_id": execution.id, "tool": tool_name, "params": arguments},
        )

        start_time = asyncio.get_running_loop().time()

        try:
            tool_fn = self.tools.get(tool_name)
            if not tool_fn:
                raise ValueError(f"Tool '{tool_name}' not found")

            maybe_result = tool_fn(**arguments)
            output_obj = await maybe_result if inspect.isawaitable(maybe_result) else maybe_result
            if isinstance(output_obj, (dict, list)):
                output = json.dumps(output_obj, ensure_ascii=False)
            else:
                output = str(output_obj)

            execution_time = asyncio.get_running_loop().time() - start_time
            execution.status = "completed"
            execution.output = output[:1000]
            execution.ended_at = datetime.now().isoformat()

            await self.emit_event(
                "tool_call_complete",
                {
                    "tool_id": execution.id,
                    "tool": tool_name,
                    "output": execution.output,
                    "result": execution.output,
                    "execution_time": execution_time,
                },
            )

            # Episodic Memory: Log tool call result
            if self.memory:
                asyncio.create_task(self.memory.append_episode(self.session_id, {
                    "tool": tool_name,
                    "arguments": arguments,
                    "output": output[:2000],  # Truncate for memory efficiency
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                }))

            # Check if tool requested a loop reset (for episodic execution)
            reset_requested = False
            if isinstance(output_obj, dict) and output_obj.get("_reset_loop"):
                reset_requested = True
                logger.info("Tool '%s' requested loop reset - episodic execution enabled", tool_name)

            return {
                "tool_call_id": tool_id,
                "name": tool_name,
                "output": output,
                "success": True,
                "_reset_loop_requested": reset_requested,
            }

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            execution_time = asyncio.get_running_loop().time() - start_time
            execution.status = "failed"
            execution.output = str(exc)
            execution.ended_at = datetime.now().isoformat()

            await self.emit_event(
                "tool_call_failed",
                {
                    "tool_id": execution.id,
                    "tool": tool_name,
                    "error": str(exc),
                    "execution_time": execution_time,
                },
            )

            return {
                "tool_call_id": tool_id,
                "name": tool_name,
                "output": f"Error: {exc}",
                "success": False,
            }

    async def _stream_final_response(self) -> None:
        """Stream final response after tool execution."""
        if not self.llm:
            raise RuntimeError("LLM client not available")

        full_response = ""

        if hasattr(self.llm, "complete_stream"):
            async for chunk in self.llm.complete_stream(
                messages=self.conversation_history,
                temperature=0.7,
            ):
                if isinstance(chunk, str) and chunk.startswith("__USAGE__:"):
                    continue
                text = str(chunk)
                full_response += text
                await self.emit_event("response_chunk", {"chunk": text})
        else:
            response = await self.llm.complete(
                messages=self.conversation_history,
                stream=False,
                temperature=0.7,
            )
            full_response = getattr(response, "content", str(response))
            await self.emit_event("response_chunk", {"chunk": full_response})

        self.conversation_history.append({"role": "assistant", "content": full_response})
        await self.emit_event("response_complete", {"response": full_response})

    async def _stream_response_content(self, content: str) -> None:
        """Stream direct response content."""
        chunk_size = 10
        for idx in range(0, len(content), chunk_size):
            chunk = content[idx : idx + chunk_size]
            await self.emit_event("response_chunk", {"chunk": chunk})
            await asyncio.sleep(0.01)

        self.conversation_history.append({"role": "assistant", "content": content})
        await self.emit_event("response_complete", {"response": content})

    async def _stream_thought_content(self, content: str) -> None:
        """Stream intermediate reasoning thoughts to the UI."""
        chunk_size = 20
        for idx in range(0, len(content), chunk_size):
            chunk = content[idx : idx + chunk_size]
            await self.emit_event("thinking_chunk", {"chunk": chunk})
            await asyncio.sleep(0.01)

        await self.emit_event("thinking_complete", {})

    def _apply_sliding_window(self) -> None:
        """Apply sliding window to conversation history to prevent unbounded growth."""
        if len(self.conversation_history) <= self._max_history_messages:
            return

        # Keep system message if present
        system_msgs = [m for m in self.conversation_history if m["role"] == "system"]
        other_msgs = [m for m in self.conversation_history if m["role"] != "system"]

        # Keep only the most recent messages
        recent_msgs = other_msgs[-self._max_history_messages:]

        # Rebuild history
        self.conversation_history = system_msgs + recent_msgs

        logger.info(
            "Applied sliding window: kept %d messages (from %d total)",
            len(self.conversation_history),
            len(system_msgs) + len(other_msgs)
        )

    def _extract_critical_context(self) -> str:
        """Extract critical facts from conversation that MUST survive compression.

        Preserves: the original user request, key entities (model names, file paths,
        URLs, config values), tool results that contain important data, and the
        current task objective so the model doesn't lose track of what it's doing.
        """
        sections = []

        # 1. Original task / first user message (the most important thing)
        first_user = None
        for msg in self.conversation_history:
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Multimodal — extract text parts
                    content = " ".join(
                        b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                    )
                first_user = str(content)
                break
        if first_user:
            sections.append(f"ORIGINAL TASK:\n{first_user[:500]}")

        # 2. Extract key entities from ALL messages (model names, paths, etc.)
        import re
        entities = set()
        for msg in self.conversation_history:
            content = msg.get("content", "")
            if isinstance(content, list):
                content = " ".join(
                    str(b.get("text", "") if isinstance(b, dict) else b)
                    for b in content
                )
            content = str(content)
            # Model names (patterns like model/name, name-version, etc.)
            entities.update(re.findall(r'(?:[\w-]+/)?[\w]+-[\w.]+-[\w.]+(?:-\w+)*', content))
            # File paths
            entities.update(re.findall(r'/[\w/.-]+\.\w+', content))
            # URLs
            entities.update(re.findall(r'https?://[\w./:-]+', content))

        if entities:
            # Deduplicate and limit
            entity_list = sorted(entities)[:30]
            sections.append(f"KEY ENTITIES:\n" + "\n".join(f"- {e}" for e in entity_list))

        # 3. Last assistant response (current state of work)
        last_assistant = None
        for msg in reversed(self.conversation_history):
            if msg.get("role") == "assistant":
                content = str(msg.get("content", ""))
                if content and len(content) > 20:
                    last_assistant = content
                    break
        if last_assistant:
            sections.append(f"LAST RESPONSE:\n{last_assistant[:400]}")

        # 4. Successful tool results (important data the model discovered)
        tool_results = []
        for msg in self.conversation_history:
            if msg.get("role") == "tool":
                output = str(msg.get("content", ""))
                if output and not output.startswith("Error") and len(output) > 10:
                    tool_results.append(output[:200])
        if tool_results:
            # Keep the last few tool results
            sections.append(f"RECENT TOOL RESULTS:\n" + "\n---\n".join(tool_results[-5:]))

        return "\n\n".join(sections)

    async def _compress_context_simple(self, reason: str = "automatic") -> bool:
        """
        Context compression that preserves critical facts.

        Unlike naive truncation, this extracts key entities (model names, paths,
        URLs), the original task, and recent tool results before compressing.
        This prevents the model from losing track of what it's doing.
        """
        try:
            logger.info("Compressing context (reason: %s) - current tokens: %d", reason, self._tokens_used)

            await self.emit_event(
                "context_compression",
                {
                    "reason": reason,
                    "tokens_before": self._tokens_used,
                    "messages_before": len(self.conversation_history),
                }
            )

            # Keep system message
            system_msg = next((m for m in self.conversation_history if m["role"] == "system"), None)

            # CRITICAL: Extract important context BEFORE clearing history
            critical_context = self._extract_critical_context()

            # Build a concise recent exchange summary
            summary_parts = []
            for msg in self.conversation_history[-20:]:
                role = msg.get("role", "unknown")
                if role == "system":
                    continue
                elif role == "user":
                    content = str(msg.get("content", ""))
                    if isinstance(msg.get("content"), list):
                        content = " ".join(
                            str(b.get("text", "") if isinstance(b, dict) else b)
                            for b in msg["content"]
                        )
                    summary_parts.append(f"User: {content[:200]}")
                elif role == "assistant":
                    content = str(msg.get("content", ""))
                    if content:
                        summary_parts.append(f"Assistant: {content[:200]}")
                elif role == "tool":
                    tool_id = msg.get("tool_call_id", "")
                    output = str(msg.get("content", ""))[:100]
                    summary_parts.append(f"Tool [{tool_id[:8]}]: {output}")

            recent_summary = "\n".join(summary_parts[-15:])

            # Clear and rebuild history
            self.conversation_history = []
            if system_msg:
                self.conversation_history.append(system_msg)

            # Add rich continuation context with critical facts preserved
            self.conversation_history.append({
                "role": "user",
                "content": (
                    f"[CONTEXT COMPRESSED — {reason}]\n\n"
                    f"The conversation context was compressed to free up space. "
                    f"Below are the critical facts and recent history you MUST remember:\n\n"
                    f"{critical_context}\n\n"
                    f"--- RECENT EXCHANGES ---\n"
                    f"{recent_summary}\n\n"
                    f"Continue working on the task described above. "
                    f"Do NOT ask the user to repeat information — everything you need is above."
                )
            })

            # Persist critical context to episodic memory (survives session restarts)
            if self.memory:
                try:
                    await self.memory.append_episode(self.session_id, {
                        "type": "context_checkpoint",
                        "critical_context": critical_context[:3000],
                        "reason": reason,
                        "timestamp": datetime.now().isoformat(),
                    })
                except Exception as mem_err:
                    logger.warning("Failed to persist critical context to memory: %s", mem_err)

            # Re-estimate tokens
            try:
                from .checkpoint_adapter import TokenCounter
                tc = TokenCounter()
                self._tokens_used = tc.count_messages(self.conversation_history)
            except Exception:
                self._tokens_used = len(str(self.conversation_history)) // 4  # Rough estimate

            await self.emit_event(
                "context_compressed",
                {
                    "tokens_after": self._tokens_used,
                    "messages_after": len(self.conversation_history),
                    "compression_ratio": self._tokens_used / (self._tokens_used + 1000)
                }
            )

            logger.info("Context compressed: tokens now ~%d", self._tokens_used)
            return True

        except Exception as e:
            logger.error("Simple compression failed: %s", e, exc_info=True)
            # Last resort: just apply sliding window
            self._apply_sliding_window()
            return False



    async def _auto_checkpoint(self, reason: str) -> None:
        """Automatically save state before destructive actions."""
        if not self._checkpoint_engine:
            return

        logger.info(f"Auto-checkpointing trigger: {reason}")
        try:
            # We use a distinct objective for auto-checkpoints
            await self.checkpoint(objective=f"Auto-save: {reason}")
        except Exception as e:
            logger.error(f"Auto-checkpoint failed: {e}")

    async def _agentic_flush(self) -> None:
        """
        Give the agent one silent turn to save important context before compression.
        
        Instead of mechanically dumping the entire state, asks the LLM to decide
        what's worth preserving. The response is saved to daily memory.
        """
        if not self._agentic_flush_enabled or not self.memory:
            return
        
        if self._flush_triggered:
            return  # Already flushed this cycle
        
        self._flush_triggered = True
        
        logger.info("Agentic flush: asking agent to save important context")
        
        try:
            # Build a minimal prompt for the flush
            flush_prompt = [
                {
                    "role": "system",
                    "content": (
                        "Session nearing compaction. Review the conversation so far and save "
                        "any durable facts, decisions, or task state that should persist. "
                        "Format as a concise bullet list. Reply ONLY with the list, or "
                        "reply NO_SAVE if there is nothing important to preserve."
                    )
                }
            ]
            
            # Include last 10 conversation messages for context
            recent = self.conversation_history[-10:] if len(self.conversation_history) > 10 else self.conversation_history
            flush_prompt.extend(recent)
            
            # Single-turn LLM call (no tools)
            response = await self.llm.chat.completions.create(
                model=self.llm._model if hasattr(self.llm, '_model') else os.getenv("LLM_MODEL", "default"),
                messages=flush_prompt,
                max_tokens=500,
                temperature=0.3
            )
            
            content = response.choices[0].message.content.strip()
            
            if content and content.upper() != "NO_SAVE":
                await self.memory.log_daily(
                    content=f"[Agentic Flush] {content}",
                    source="agent",
                    tags=["agentic_flush", "pre_compression"]
                )
                logger.info("Agentic flush saved %d chars to daily memory", len(content))
            else:
                logger.info("Agentic flush: agent had nothing to save")
                
        except Exception as e:
            logger.warning("Agentic flush failed (non-fatal): %s", e)

    async def _check_and_compress_context(self) -> None:
        """
        Proactive context management with multiple failsafes.
        """
        # Always apply sliding window first
        self._apply_sliding_window()

        # Calculate current usage percentage
        usage_pct = self._tokens_used / self._max_context_tokens if self._max_context_tokens > 0 else 0
        
        # 1. Critical Threshold (85%) - Emergency Action
        if usage_pct >= self._critical_threshold:
            logger.warning("CRITICAL: Context at %.1f%% - forcing emergency compression!", usage_pct * 100)
            await self._auto_checkpoint(reason="critical_threshold_reached")
            await self._compress_context_simple(reason="critical_threshold")
            self._context_warning_sent = False # Reset warning after cleanup
            self._flush_triggered = False      # Reset flush flag
            return

        # 2. Warning Threshold (75%) - Agentic Flush then Notify Agent
        if usage_pct >= self._warning_threshold and not self._context_warning_sent:
            logger.info("Context at %.1f%% - triggering agentic flush + warning", usage_pct * 100)
            
            # Run agentic flush BEFORE showing the warning
            await self._agentic_flush()
            
            # Inject a system message warning
            self.conversation_history.append({
                "role": "system", 
                "content": (
                    f"⚠️ **SYSTEM WARNING**: Context usage is at {int(usage_pct*100)}%. "
                    "You are running low on memory. "
                    "Please finish your current task immediately or use `checkpoint_and_continue` to save state and reset."
                )
            })
            self._context_warning_sent = True
            return

        # 3. Proactive Compression (60%) - Attempt lossless compression
        if usage_pct >= self._compression_threshold:
            # If we haven't warned yet, we might want to try silent compression first
            logger.info("Context at %.1f%% - triggering proactive compression", usage_pct * 100)
            
            if self._checkpoint_engine:
                try:
                    success = await self.checkpoint(objective="Proactive maintenance")
                    if success:
                        self._context_warning_sent = False
                        return
                except Exception:
                    pass

            # If proactive fails, just wait for warning/critical thresholds
            # to avoid disrupting the flow too early

    async def checkpoint(self, objective: str = "Automated checkpoint") -> bool:
        """
        Trigger a checkpoint and clear history.
        
        Returns True if successful, False otherwise.
        """
        if not self._checkpoint_engine:
            logger.warning("Checkpoint engine not available for session %s", self.session_id)
            return False

        try:
            await self.emit_event(
                "checkpoint_start",
                {"message": "Compressing conversation context...", "timestamp": datetime.now().isoformat()}
            )

            # Reconstruct WorkingMemory if needed, or use the adapter's implementation
            # For now, let's use the engine's internal loop distillation if we can,
            # but ExecutionLoop expects to OWN the loop.
            
            # Since we have AgentRuntimeV2 owning the loop, we call distillation manually.
            from .checkpoint_adapter import TokenCounter
            tc = TokenCounter()
            history_str = json.dumps(self.conversation_history, indent=2)
            
            # Distill using the adapter logic
            distilled = await self._checkpoint_engine.agent.distill_checkpoint(
                objective=objective,
                working_memory_text=history_str,
                previous_checkpoint=None # TODO: Load previous chkpt if exists
            )
            
            # Create the checkpoint in episodic memory
            checkpoint = await self._checkpoint_engine.episodic_memory.save_checkpoint({
                "checkpoint_id": f"chk_{uuid.uuid4().hex[:8]}",
                "episode_number": 1,
                "objective": objective,
                "data": distilled,
                "created_at": datetime.now().isoformat()
            })
            
            # CLEAR HISTORY but keep system prompt and distilled state
            system_msg = next((m for m in self.conversation_history if m["role"] == "system"), None)
            self.conversation_history = []
            if system_msg:
                self.conversation_history.append(system_msg)
            
            # Add continuation prompt
            continuation = (
                f"### RESUMING FROM CHECKPOINT\n"
                f"Objective: {distilled.get('objective')}\n"
                f"Progress: {', '.join(distilled.get('progress_items', []))}\n"
                f"Current State: {json.dumps(distilled.get('current_state', {}))}\n"
                f"Next Actions: {', '.join(distilled.get('next_actions', []))}\n"
                f"Please continue with the next actions."
            )
            self.conversation_history.append({"role": "user", "content": continuation})
            
            # Update token count
            self._tokens_used = tc.count_messages(self.conversation_history)
            
            await self.emit_event(
                "checkpoint_complete",
                {"message": "Context compressed. Tokens reduced.", "tokens": self._tokens_used}
            )
            logger.info("Session %s checkpointed and history cleared", self.session_id)
            return True
        except Exception as e:
            logger.error("Failed to checkpoint session %s: %s", self.session_id, e, exc_info=True)
            await self.emit_event("error", {"message": f"Checkpoint failed: {e}"})
            return False

    def __aiter__(self) -> "AgentRuntimeV2":
        """Enable async iteration over queued events."""
        return self

    async def __anext__(self) -> Dict[str, Any]:
        """Return next event from queue."""
        return await self.event_queue.get()
