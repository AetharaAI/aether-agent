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
MAX_TOOL_ROUNDS = 10


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
        sandbox: Any = None,
        system_prompt: Optional[str] = None,
    ):
        self.session_id = session_id
        self.llm = llm_client
        self.tools: Dict[str, Callable[..., Any]] = tools or {}
        self.sandbox = sandbox

        self.state = AgentState.IDLE
        self.event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.conversation_history: List[Dict[str, Any]] = []

        # Context Management
        self._tokens_used: int = 0
        self._max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "32768"))
        self._checkpoint_engine: Optional[Any] = None
        self._last_usage_meta: Dict[str, Any] = {}

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

            self.conversation_history.append(
                {"role": "user", "content": self._build_user_content(user_input, attachments)}
            )

            tools_schema = self._build_tools_schema()
            round_count = 0

            # ── Agentic loop: LLM → tools → LLM → tools → ... → final response ──
            while round_count < MAX_TOOL_ROUNDS:
                round_count += 1

                if self._cancelled:
                    raise asyncio.CancelledError()

                await self.transition_to(AgentState.THINKING)
                await self.emit_event(
                    "thinking_start",
                    {"message": f"Analyzing request (round {round_count})..."},
                )

                response = await self._call_llm_with_tools(
                    messages=self.conversation_history, tools=tools_schema
                )

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

                await self._execute_tool_calls(tool_calls, content=content)

                # Update token usage from LLM response metadata if available
                usage = response.get("usage") or {}
                if usage:
                    self._last_usage_meta = usage
                    self._tokens_used = usage.get("total_tokens") or self._tokens_used
                    logger.info("Updated session tokens from LLM usage: %d", self._tokens_used)
                else:
                    # Fallback token estimation
                    from .checkpoint_adapter import TokenCounter
                    tc = TokenCounter()
                    self._tokens_used = tc.count_messages(self.conversation_history)
                    logger.info("Estimated session tokens: %d", self._tokens_used)

                logger.info(
                    "Completed tool round %d/%d — current tokens: %d — looping back to LLM",
                    round_count,
                    MAX_TOOL_ROUNDS,
                    self._tokens_used,
                )
                # Loop continues: the LLM sees the tool results and decides
                # whether to call more tools or produce a final response.

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
        """Build text-only or multimodal user content."""
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
            if not image_url and attachment.get("path"):
                path = Path(str(attachment["path"]))
                if path.exists() and path.is_file():
                    image_url = self._file_to_data_url(path, mime_type)

            if image_url:
                content.append({"type": "image_url", "image_url": {"url": image_url}})

        return content if content else user_input

    def _file_to_data_url(self, path: Path, mime_type: str) -> str:
        """Encode file content as data URL for multimodal requests."""
        with open(path, "rb") as file_obj:
            encoded = base64.b64encode(file_obj.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _build_tools_schema(self) -> List[Dict[str, Any]]:
        """Build OpenAI-style tools schema from available tools."""
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
    ) -> None:
        """Execute tool calls from LLM."""
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

        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                call_id = tool_calls[idx].id if idx < len(tool_calls) else f"call_{idx}"
                output = f"Error: {result}"
                self.conversation_history.append(
                    {"role": "tool", "tool_call_id": call_id, "content": output}
                )
            else:
                self.conversation_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": result["tool_call_id"],
                        "content": result["output"],
                    }
                )

        await self.transition_to(AgentState.OBSERVING)

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

            return {
                "tool_call_id": tool_id,
                "name": tool_name,
                "output": output,
                "success": True,
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
