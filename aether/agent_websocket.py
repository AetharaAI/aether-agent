"""
Agent Runtime WebSocket manager.

"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

from .agent_runtime_v2 import AgentRuntimeV2
from .database import db
from .fabric_integration import FabricIntegration

logger = logging.getLogger(__name__)


class AgentSessionManager:
    """Manage active agent sessions over WebSocket."""

    def __init__(self) -> None:
        self.active_runtimes: Dict[str, AgentRuntimeV2] = {}
        self.connections: Dict[str, WebSocket] = {}
        self.running_tasks: Dict[str, asyncio.Task[Any]] = {}
        self.tool_registry: Any = None
        self._titled_sessions: set = set()  # Sessions that already have a title
        self.fabric: Optional[FabricIntegration] = None

    def set_tool_registry(self, registry: Any) -> None:
        """Inject tool registry from API server startup."""
        self.tool_registry = registry
        tools_map = self._build_tools_map()
        for runtime in self.active_runtimes.values():
            runtime.set_tools(tools_map)

    def _build_tools_map(self) -> Dict[str, Any]:
        """Build runtime-callable tools from the registered ToolRegistry."""
        if not self.tool_registry:
            return {}

        tools_map: Dict[str, Any] = {}
        tool_metas = self.tool_registry.list_tools()

        for tool_meta in tool_metas:
            name = tool_meta.get("name")
            if not name:
                continue

            async def _tool_wrapper(_name: str = name, **kwargs: Any) -> Any:
                result = await self.tool_registry.execute(_name, **kwargs)
                if hasattr(result, "to_dict"):
                    return result.to_dict()
                return result

            _tool_wrapper.__tool_schema__ = {
                "description": tool_meta.get("description", ""),
                "parameters": self._to_json_schema(tool_meta.get("parameters") or {}),
            }
            tools_map[name] = _tool_wrapper

        return tools_map

    async def _setup_fabric(self) -> None:
        """Initialize Fabric integration if configured (non-blocking)."""
        import os
        if os.getenv("FABRIC_BASE_URL") and not self.fabric:
            self.fabric = FabricIntegration(agent_id="aether")
            
            # Register A2A message handler
            @self.fabric.on_message("task")
            async def handle_remote_task(message):
                logger.info(f"Received A2A task from {message['from_agent']}: {message['payload'].get('task_type')}")
                # Broadcast to all active sessions (or find specific one)
                for sid, ws in self.connections.items():
                    await self._send_event(ws, {
                        "event_type": "fabric_message",
                        "timestamp": datetime.now().isoformat(),
                        "payload": message
                    })

            async def _start_fabric_background():
                try:
                    logger.info("Starting Fabric Integration (background)...")
                    await self.fabric.start()
                    logger.info("Fabric messaging integration started successfully")
                except Exception as e:
                    logger.warning(f"Fabric messaging unavailable, continuing without it: {e}")

            # Fire and forget - don't block session startup
            asyncio.create_task(_start_fabric_background())

    def _build_system_prompt(self) -> str:
        """Build a system prompt that tells the LLM about its tools."""
        lines = [
            "You are Aether, an autonomous AI agent with access to tools.",
            "",
            "IMPORTANT: You have tools available. When a user asks you to perform",
            "an action that requires reading files, listing directories, executing",
            "commands, searching the web, or any other operation you have a tool for,",
            "you MUST call the appropriate tool. Do NOT guess or make up results.",
            "",
            "After calling tools, analyze their output and either:",
            "- Call more tools if needed to complete the task",
            "- Provide a final response incorporating the tool results",
            "",
            "HOW TO CALL TOOLS:",
            "To call a tool, output a JSON block in this exact format:",
            "",
            "```tool_call",
            '{"name": "tool_name", "arguments": {"param1": "value1"}}',
            "```",
            "",
            "You may call multiple tools by outputting multiple ```tool_call blocks.",
            "After tool results are returned, continue your response.",
            "",
            "AVAILABLE TOOLS:",
        ]

        if self.tool_registry:
            for tool_meta in self.tool_registry.list_tools():
                name = tool_meta.get("name", "")
                desc = tool_meta.get("description", "")
                params = tool_meta.get("parameters", {})
                param_strs = []
                for pname, pmeta in params.items():
                    if isinstance(pmeta, dict):
                        ptype = pmeta.get("type", "string")
                        pdesc = pmeta.get("description", "")
                        req = " (required)" if pmeta.get("required") else ""
                        param_strs.append(f"    - {pname}: {ptype} — {pdesc}{req}")
                    else:
                        param_strs.append(f"    - {pname}: string")
                lines.append(f"\n  {name}: {desc}")
                if param_strs:
                    lines.extend(param_strs)

        lines.extend([
            "",
            "RULES:",
            "- Always use tools for file operations, never guess file contents",
            "- Report tool errors honestly",
            "- You may call multiple tools in sequence to complete complex tasks",
            "- ALWAYS use the ```tool_call JSON format shown above to invoke tools",
        ])

        return "\n".join(lines)

    @staticmethod
    def _to_json_schema(param_defs: Dict[str, Any]) -> Dict[str, Any]:
        """Convert registry parameter definitions to JSON schema."""
        # Already a valid JSON Schema? Pass through unchanged.
        if param_defs.get("type") == "object" and "properties" in param_defs:
            return param_defs

        properties: Dict[str, Any] = {}
        required = []

        for param_name, meta in param_defs.items():
            if not isinstance(meta, dict):
                properties[param_name] = {"type": "string"}
                continue

            schema = {
                "type": meta.get("type", "string"),
                "description": meta.get("description", ""),
            }
            if "default" in meta:
                schema["default"] = meta["default"]
            if "enum" in meta:
                schema["enum"] = meta["enum"]
            properties[param_name] = schema

            if meta.get("required", False):
                required.append(param_name)

        json_schema: Dict[str, Any] = {"type": "object", "properties": properties}
        if required:
            json_schema["required"] = required
        return json_schema

    async def handle_agent_session(
        self,
        websocket: WebSocket,
        session_id: str,
        llm_client: Any = None,
    ) -> None:
        """Handle a complete agent session lifecycle."""
        await self._setup_fabric()
        await websocket.accept()
        self.connections[session_id] = websocket
        
        # Persist session
        await db.create_session(session_id, user_id="default", metadata={"start_time": datetime.now().isoformat()})

        try:
            runtime = self.active_runtimes.get(session_id)
            if not runtime:
                runtime = AgentRuntimeV2(
                    session_id=session_id,
                    llm_client=llm_client,
                    tools=self._build_tools_map(),
                    system_prompt=self._build_system_prompt(),
                )
                
                # Opt-in Checkpointing integration
                if os.getenv("AETHER_CHECKPOINTING", "").lower() == "true":
                    try:
                        from .checkpoint_adapter import wrap_runtime_with_checkpointing
                        runtime = wrap_runtime_with_checkpointing(runtime, session_id)
                    except Exception as e:
                        logger.error(f"Failed to wrap runtime with checkpointing: {e}")
                
                self.active_runtimes[session_id] = runtime
            elif llm_client is not None:
                runtime.llm = llm_client

            logger.info("Agent session started: %s", session_id)
            await self._send_event(
                websocket,
                {
                    "event_type": "session_started",
                    "timestamp": datetime.now().isoformat(),
                    "payload": {"session_id": session_id, "agent_state": runtime.state.value},
                },
            )

            while True:
                try:
                    data = await websocket.receive_json()
                    msg_type = data.get("type", "user_input")

                    if msg_type == "user_input":
                        await self._handle_user_input(websocket, runtime, data, session_id)
                    elif msg_type == "cancel_task":
                        await runtime.cancel_current_task()
                        await self._send_event(
                            websocket,
                            {
                                "event_type": "task_cancelled",
                                "timestamp": datetime.now().isoformat(),
                                "payload": {},
                            },
                        )
                    else:
                        logger.warning("Unknown message type: %s", msg_type)

                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected for session %s", session_id)
                    break
                except RuntimeError as exc:
                    if "disconnect" in str(exc).lower() or "not connected" in str(exc).lower():
                        logger.info("WebSocket disconnected for session %s", session_id)
                        break
                    logger.error("Runtime error in message loop: %s", exc)
                    break
                except Exception as exc:
                    logger.error("Error in message loop: %s", exc, exc_info=True)
                    break

        finally:
            await self._cleanup_session(session_id)

    async def _handle_user_input(
        self,
        websocket: WebSocket,
        runtime: AgentRuntimeV2,
        data: Dict[str, Any],
        session_id: str,
    ) -> None:
        """Process user input and stream runtime events."""
        user_input = data.get("message", "")
        attachments = data.get("attachments", []) or []

        if not user_input and not attachments:
            return

        logger.info("Received user input: %s...", user_input[:50] if user_input else "(no text)")

        if session_id in self.running_tasks and not self.running_tasks[session_id].done():
            logger.warning("Task already running for session %s, cancelling it", session_id)
            await runtime.cancel_current_task()

        await db.save_message(session_id, "user", user_input)

        # Auto-title session from first user message
        if session_id not in self._titled_sessions and user_input:
            self._titled_sessions.add(session_id)
            title = user_input[:60].strip()
            if len(user_input) > 60:
                title += "…"
            await db.update_session_title(session_id, title)

        await self._send_event(
            websocket,
            {
                "event_type": "user_message",
                "timestamp": datetime.now().isoformat(),
                "payload": {"content": user_input, "attachments": attachments},
            },
        )

        task = asyncio.create_task(runtime.run_task(user_input, attachments=attachments))
        self.running_tasks[session_id] = task

        try:
            while True:
                if task.done() and runtime.event_queue.empty():
                    break

                try:
                    event = await asyncio.wait_for(runtime.__anext__(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue

                # Forward all V2 events directly to client.
                await self._send_event(websocket, event)

                # Persist assistant response
                if event.get("event_type") == "response_complete":
                     content = event.get("payload", {}).get("response", "")
                     if content:
                        await db.save_message(session_id, "assistant", content)

            await task

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Error processing task: %s", exc, exc_info=True)
            await self._send_event(
                websocket,
                {
                    "event_type": "error",
                    "timestamp": datetime.now().isoformat(),
                    "payload": {"message": str(exc)},
                },
            )
        finally:
            if session_id in self.running_tasks:
                del self.running_tasks[session_id]

    async def _cleanup_session(self, session_id: str) -> None:
        """Cancel running work and remove session state."""
        runtime = self.active_runtimes.get(session_id)
        if runtime:
            try:
                await runtime.cancel_current_task()
            except Exception:
                pass

        if session_id in self.running_tasks:
            task = self.running_tasks[session_id]
            if not task.done():
                task.cancel()
            del self.running_tasks[session_id]

        if session_id in self.connections:
            del self.connections[session_id]
        if session_id in self.active_runtimes:
            del self.active_runtimes[session_id]

        logger.info("Agent session ended: %s", session_id)

    async def _send_event(self, websocket: WebSocket, event: Dict[str, Any]) -> None:
        """Send an event to the WebSocket client."""
        try:
            await websocket.send_json(event)
        except Exception:
            # Ignore send failures, likely due to disconnect.
            pass

    async def handle_approval(self, session_id: str, approved: bool) -> None:
        """Legacy no-op for backward compatibility."""
        _ = (session_id, approved)
        return

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get current state of a session."""
        runtime = self.active_runtimes.get(session_id)
        if not runtime:
            return None

        return {"state": runtime.state.value, "session_id": session_id}


_manager: Optional[AgentSessionManager] = None


def get_agent_manager() -> AgentSessionManager:
    """Get or create global agent session manager."""
    global _manager
    if _manager is None:
        _manager = AgentSessionManager()
    return _manager
