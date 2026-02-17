"""
Dynamic Tool Registry — MongoDB-backed on-demand tool loading.

Production-hardened evolution of prototypes/mongo_registry.py.
Reuses the existing Motor connection from LedgerDB and integrates
with the ToolRegistry dependency injection pattern (set_memory,
set_runtime, set_ledger_db).

Usage:
    from aether.tools.dynamic_registry import DynamicToolRegistry

    dtr = DynamicToolRegistry(db)
    results = await dtr.search_tools("web search")
    tool_fn = await dtr.activate_tool("web_search", registry, memory=memory)
"""

import asyncio
import importlib
import logging
from typing import Any, Dict, List, Optional

from .registry import Tool, ToolResult, ToolPermission

logger = logging.getLogger("aether.tools.dynamic_registry")


class DynamicToolRegistry:
    """MongoDB-backed registry for on-demand tool loading."""

    def __init__(self, db, collection_name: str = "tools"):
        """
        Args:
            db: Motor database instance (aether_agent db, NOT agent_ledger).
            collection_name: Name of the tools collection.
        """
        self._db = db
        self._coll = db[collection_name]
        self._activation_lock = asyncio.Lock()
        # Track which tools have been activated this session
        self._activated: set = set()

    async def search_tools(
        self, query: str, limit: int = 10, tier: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for tools by keyword across name, description, and tags.

        Returns lightweight summaries (no full parameters) to keep context lean.
        """
        search_filter: Dict[str, Any] = {"enabled": True}

        if tier:
            search_filter["tier"] = tier

        # Use MongoDB text search if available, fall back to regex
        try:
            search_filter["$text"] = {"$search": query}
            cursor = self._coll.find(
                search_filter,
                {
                    "_id": 0,
                    "name": 1,
                    "description": 1,
                    "tags": 1,
                    "tier": 1,
                    "permission": 1,
                    "score": {"$meta": "textScore"},
                },
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)
            results = await cursor.to_list(length=limit)
        except Exception:
            # Fallback: regex search across name, description, tags
            del search_filter["$text"]
            import re
            pattern = re.compile(re.escape(query), re.IGNORECASE)
            search_filter["$or"] = [
                {"name": pattern},
                {"description": pattern},
                {"tags": pattern},
            ]
            cursor = self._coll.find(
                search_filter,
                {"_id": 0, "name": 1, "description": 1, "tags": 1, "tier": 1, "permission": 1},
            ).limit(limit)
            results = await cursor.to_list(length=limit)

        # Mark which ones are already activated
        for r in results:
            r["activated"] = r["name"] in self._activated

        return results

    async def get_tool_definition(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get full tool definition by name."""
        return await self._coll.find_one(
            {"name": tool_name, "enabled": True},
            {"_id": 0},
        )

    async def activate_tool(
        self,
        tool_name: str,
        registry: Any,
        memory: Any = None,
        runtime: Any = None,
        ledger_db: Any = None,
    ) -> Optional[str]:
        """Load a tool from MongoDB and register it in the live ToolRegistry.

        Returns:
            The tool name if successfully activated, None on failure.
        """
        async with self._activation_lock:
            # Already activated?
            if tool_name in self._activated:
                return tool_name

            definition = await self.get_tool_definition(tool_name)
            if not definition:
                logger.warning(f"Tool '{tool_name}' not found in MongoDB")
                return None

            handler_path = definition.get("handler_path")
            if not handler_path:
                logger.error(f"Tool '{tool_name}' has no handler_path")
                return None

            try:
                # Parse "aether.tools.core_tools.FileUploadTool" → module + class
                parts = handler_path.rsplit(".", 1)
                if len(parts) != 2:
                    logger.error(f"Invalid handler_path: {handler_path}")
                    return None

                module_path, class_name = parts
                mod = importlib.import_module(module_path)
                tool_cls = getattr(mod, class_name)

                # Instantiate
                tool_instance = tool_cls()

                # Dependency injection (tools opt-in via set_* methods)
                if memory and hasattr(tool_instance, "set_memory"):
                    tool_instance.set_memory(memory)
                if runtime and hasattr(tool_instance, "set_runtime"):
                    tool_instance.set_runtime(runtime)
                if ledger_db and hasattr(tool_instance, "set_ledger_db"):
                    tool_instance.set_ledger_db(ledger_db)
                if registry and hasattr(tool_instance, "set_registry"):
                    tool_instance.set_registry(registry)

                # Register in the live ToolRegistry
                registry.register(tool_instance)
                self._activated.add(tool_name)

                logger.info(f"Dynamically activated tool: {tool_name}")
                return tool_name

            except Exception as e:
                logger.error(f"Failed to activate tool '{tool_name}': {e}", exc_info=True)
                return None

    async def get_extended_tool_count(self) -> int:
        """Count available extended tools in MongoDB."""
        return await self._coll.count_documents({"tier": "extended", "enabled": True})

    async def list_all_tools(self, tier: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all available tools (summaries only)."""
        search_filter: Dict[str, Any] = {"enabled": True}
        if tier:
            search_filter["tier"] = tier

        cursor = self._coll.find(
            search_filter,
            {"_id": 0, "name": 1, "description": 1, "tags": 1, "tier": 1},
        )
        return await cursor.to_list(length=100)

    @property
    def activated_tools(self) -> set:
        """Set of tool names activated this session."""
        return self._activated.copy()


# ─── Meta-Tools ──────────────────────────────────────────────────────────────
# These are always-loaded tools that let the agent discover and activate
# extended tools at runtime.


class SearchToolsTool(Tool):
    """Search for available tools by capability keyword.

    Returns tool names and descriptions (not full content) so the agent
    can decide which tools to activate for the current task.
    """

    name = "search_tools"
    description = (
        "Search for available tools by keyword (e.g., 'web', 'memory', 'ledger', 'filesystem'). "
        "Returns tool names and descriptions. Use this to discover tools you need, "
        "then call use_tool to activate them."
    )
    permission = ToolPermission.INTERNAL
    parameters = {
        "query": {
            "type": "string",
            "description": "Search keyword or phrase describing the capability needed",
            "required": True,
        },
        "limit": {
            "type": "integer",
            "description": "Max results to return (default: 10)",
            "required": False,
        },
    }

    def __init__(self):
        self._dynamic_registry: Optional[DynamicToolRegistry] = None

    def set_dynamic_registry(self, dtr: DynamicToolRegistry):
        self._dynamic_registry = dtr

    async def execute(self, query: str, limit: int = 10, **kwargs) -> ToolResult:
        if not self._dynamic_registry:
            return ToolResult(
                success=False,
                error="Dynamic tool registry not available. All tools may already be loaded.",
            )

        try:
            results = await self._dynamic_registry.search_tools(query, limit=limit)
            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "tools": results,
                    "count": len(results),
                    "hint": "Use use_tool(name='tool_name') to activate a tool before calling it.",
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Tool search failed: {e}")


class UseToolTool(Tool):
    """Activate a discovered tool so it becomes available for the current session.

    After activation, the tool can be called directly by name.
    """

    name = "use_tool"
    description = (
        "Activate a tool by name so you can use it in this session. "
        "Call search_tools first to discover available tools, then use_tool to activate them. "
        "Once activated, call the tool directly by its name."
    )
    permission = ToolPermission.INTERNAL
    parameters = {
        "name": {
            "type": "string",
            "description": "Name of the tool to activate (from search_tools results)",
            "required": True,
        },
    }

    def __init__(self):
        self._dynamic_registry: Optional[DynamicToolRegistry] = None
        self._tool_registry: Optional[Any] = None
        self._memory: Optional[Any] = None
        self._runtime: Optional[Any] = None
        self._ledger_db: Optional[Any] = None
        self._on_tool_activated: Optional[Any] = None  # callback

    def set_dynamic_registry(self, dtr: DynamicToolRegistry):
        self._dynamic_registry = dtr

    def set_tool_registry(self, registry: Any):
        self._tool_registry = registry

    def set_memory(self, memory: Any):
        self._memory = memory

    def set_runtime(self, runtime: Any):
        self._runtime = runtime

    def set_ledger_db(self, db: Any):
        self._ledger_db = db

    def set_on_tool_activated(self, callback):
        """Set a callback to be called when a tool is activated (for rebuilding schemas)."""
        self._on_tool_activated = callback

    async def execute(self, name: str, **kwargs) -> ToolResult:
        if not self._dynamic_registry:
            return ToolResult(
                success=False,
                error="Dynamic tool registry not available.",
            )

        if not self._tool_registry:
            return ToolResult(
                success=False,
                error="Tool registry not available.",
            )

        try:
            result = await self._dynamic_registry.activate_tool(
                name,
                registry=self._tool_registry,
                memory=self._memory,
                runtime=self._runtime,
                ledger_db=self._ledger_db,
            )

            if result:
                # Notify runtime to rebuild tool schemas
                if self._on_tool_activated:
                    await self._on_tool_activated(name)

                return ToolResult(
                    success=True,
                    data={
                        "tool_name": name,
                        "status": "activated",
                        "message": f"Tool '{name}' is now available. Call it directly by name.",
                    },
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Tool '{name}' could not be activated. It may not exist or may be disabled.",
                )
        except Exception as e:
            return ToolResult(success=False, error=f"Tool activation failed: {e}")


# Module-level instances for registration
search_tools_tool = SearchToolsTool()
use_tool_tool = UseToolTool()
