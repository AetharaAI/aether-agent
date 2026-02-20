"""
Aether Tool Layer

================================================================================
ARCHITECTURE: Tool Layer — Tiered Dynamic Loading
================================================================================

Tools are split into two tiers:
  - CORE: Always loaded at startup (~8 tools). Essential for every conversation.
  - EXTENDED: Stored in MongoDB, loaded on-demand via search_tools + use_tool.

If MongoDB is unavailable, falls back to eager loading (all tools at startup).

LAYER POSITION:
  Identity Layer -> Memory Layer -> Context Layer -> Provider Layer -> [TOOL LAYER]

PERMISSION MODEL:
- semi: Ask before external actions, internal freely
- auto: Proceed with logged accountability
- Tools log all calls to Redis for audit

USAGE:
    from aether.tools import get_registry
    
    registry = get_registry()
    result = await registry.execute("checkpoint", name="before_changes")

================================================================================
"""

from .registry import ToolRegistry, Tool, ToolResult, ToolPermission
from .tavily_search import TavilySearchTool
from .url_read import URLReadTool
from .fabric_adapter import FabricTool
from .mcp_adapter import StandardMCPTool
from .core_tools import (
    checkpoint_tool,
    checkpoint_and_continue_tool,
    compress_context_tool,
    get_context_stats_tool,
    terminal_exec_tool,
    file_upload_tool,
    file_read_tool,
    file_list_tool,
    file_write_tool,
    set_mode_tool,
    search_memory_tool,
    list_checkpoints_tool,
    read_checkpoint_tool,
    recall_episodes_tool,
    search_workspace_tool,
)
from ..ledger import (
    ledger_create_tool,
    ledger_read_tool,
    ledger_update_tool,
    ledger_search_tool,
    ledger_list_tool,
    ledger_delete_tool,
)

__all__ = [
    "ToolRegistry",
    "Tool",
    "ToolResult",
    "ToolPermission",
    "get_registry",
    "set_runtime_for_tools",
    "register_fabric_tools",
    "register_mcp_tools",
    "setup_dynamic_registry",
]

# Global registry instance
_registry: ToolRegistry | None = None

# Dynamic registry (MongoDB-backed)
_dynamic_registry = None

# Flag: set to True to fall back to eager loading (all tools at startup)
_eager_fallback: bool = False


# ─── Tool Tiers ──────────────────────────────────────────────────────────────
# Core tools: always loaded, essential for every conversation
# NOTE: Memory/context tools are here (not extended) because they are Python
# objects dispatched directly by the runtime — NOT through the use_tool
# meta-tool. They must be in self.tools regardless of Dynamic Registry mode.
_CORE_TOOL_INSTANCES = lambda: [
    terminal_exec_tool,
    file_read_tool,
    file_list_tool,
    file_write_tool,
    checkpoint_tool,
    checkpoint_and_continue_tool,
    set_mode_tool,
    # Memory/context tools — always registered so they work in dynamic mode too
    compress_context_tool,
    get_context_stats_tool,
    search_memory_tool,
    list_checkpoints_tool,
    read_checkpoint_tool,
    recall_episodes_tool,
]

# Extended tools: loaded eagerly ONLY as fallback when MongoDB is unavailable
# (search_workspace, file_upload, web_search, url_read, ledger_* tools)
_EXTENDED_TOOL_INSTANCES = lambda: [
    TavilySearchTool(),
    URLReadTool(),
    search_workspace_tool,
    file_upload_tool,
    ledger_create_tool,
    ledger_read_tool,
    ledger_update_tool,
    ledger_search_tool,
    ledger_list_tool,
    ledger_delete_tool,
]


def get_registry(memory=None) -> ToolRegistry:
    """Get or create the global tool registry.
    
    In tiered mode: registers only core tools + meta-tools (search_tools, use_tool).
    In fallback mode: registers all tools eagerly (legacy behavior).
    """
    global _registry, _eager_fallback
    if _registry is None:
        _registry = ToolRegistry(memory=memory)

        # Always register core tools
        for tool in _CORE_TOOL_INSTANCES():
            _registry.register(tool)

        # Wire set_mode_tool with registry reference
        set_mode_tool.set_registry(_registry)

        if _eager_fallback:
            # Fallback: register everything (legacy behavior)
            for tool in _EXTENDED_TOOL_INSTANCES():
                _registry.register(tool)
        else:
            # Tiered mode: register meta-tools for dynamic discovery
            try:
                from .dynamic_registry import search_tools_tool, use_tool_tool
                _registry.register(search_tools_tool)
                _registry.register(use_tool_tool)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Failed to load dynamic meta-tools, falling back to eager loading: {e}"
                )
                _eager_fallback = True
                for tool in _EXTENDED_TOOL_INSTANCES():
                    _registry.register(tool)

        # Set memory reference for tools that need it
        if memory:
            _wire_memory(memory)

    return _registry


def _wire_memory(memory):
    """Set memory reference for all tools that need it."""
    checkpoint_tool.set_memory(memory)
    compress_context_tool.set_memory(memory)
    get_context_stats_tool.set_memory(memory)
    search_memory_tool.set_memory(memory)
    list_checkpoints_tool.set_memory(memory)
    read_checkpoint_tool.set_memory(memory)
    recall_episodes_tool.set_memory(memory)

    # Ledger tools need memory for Redis ref pushing
    ledger_create_tool.set_memory(memory)
    ledger_read_tool.set_memory(memory)
    ledger_update_tool.set_memory(memory)
    ledger_search_tool.set_memory(memory)
    ledger_list_tool.set_memory(memory)
    ledger_delete_tool.set_memory(memory)


def set_runtime_for_tools(runtime):
    """Set runtime reference for tools that need it (called after runtime creation)."""
    checkpoint_and_continue_tool.set_runtime(runtime)
    recall_episodes_tool.set_runtime(runtime)

    # Also wire the use_tool meta-tool with the runtime
    try:
        from .dynamic_registry import use_tool_tool
        use_tool_tool.set_runtime(runtime)
    except Exception:
        pass


def set_ledger_db_for_tools(db):
    """Inject MongoDB database reference into all ledger tools (called after LedgerDB.connect())."""
    ledger_create_tool.set_ledger_db(db)
    ledger_read_tool.set_ledger_db(db)
    ledger_update_tool.set_ledger_db(db)
    ledger_search_tool.set_ledger_db(db)
    ledger_list_tool.set_ledger_db(db)
    ledger_delete_tool.set_ledger_db(db)

    # Also wire the use_tool meta-tool with ledger_db
    try:
        from .dynamic_registry import use_tool_tool
        use_tool_tool.set_ledger_db(db)
    except Exception:
        pass


async def setup_dynamic_registry(mongo_url: str = None, memory=None):
    """Initialize the MongoDB-backed dynamic tool registry.
    
    Called during API server startup after LedgerDB.connect().
    If this fails, the system falls back to eager loading.
    
    Returns:
        DynamicToolRegistry instance or None on failure.
    """
    global _dynamic_registry, _eager_fallback, _registry
    import os
    from motor.motor_asyncio import AsyncIOMotorClient
    import logging

    logger = logging.getLogger(__name__)

    if not mongo_url:
        mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")

    try:
        client = AsyncIOMotorClient(mongo_url)
        db = client[os.getenv("MONGO_DB_NAME", "aether_agent")]

        # Quick health check: verify the tools collection exists and has data
        count = await db.tools.count_documents({"enabled": True})
        if count == 0:
            logger.warning(
                "MongoDB tools collection is empty. "
                "Run 'python seed_tool_registry.py' to populate it. "
                "Falling back to eager tool loading."
            )
            _eager_fallback = True
            # Re-register extended tools if registry already exists
            if _registry:
                for tool in _EXTENDED_TOOL_INSTANCES():
                    if not _registry.get(tool.name):
                        _registry.register(tool)
                if memory:
                    _wire_memory(memory)
            return None

        from .dynamic_registry import (
            DynamicToolRegistry,
            search_tools_tool,
            use_tool_tool,
        )

        _dynamic_registry = DynamicToolRegistry(db)

        # Wire meta-tools with the dynamic registry
        search_tools_tool.set_dynamic_registry(_dynamic_registry)
        use_tool_tool.set_dynamic_registry(_dynamic_registry)

        if _registry:
            use_tool_tool.set_tool_registry(_registry)
            if memory:
                use_tool_tool.set_memory(memory)

        logger.info(f"Dynamic Tool Registry connected ({count} tools available)")
        return _dynamic_registry

    except Exception as e:
        logger.error(f"Failed to initialize Dynamic Tool Registry: {e}")
        _eager_fallback = True
        # Re-register extended tools if registry already exists
        if _registry:
            for tool in _EXTENDED_TOOL_INSTANCES():
                if not _registry.get(tool.name):
                    _registry.register(tool)
            if memory:
                _wire_memory(memory)
        return None


def get_dynamic_registry():
    """Get the global DynamicToolRegistry instance (may be None)."""
    return _dynamic_registry


async def register_fabric_tools(registry: ToolRegistry) -> int:
    """
    Discover and register Fabric MCP tools.
    
    Returns:
        Number of tools registered.
    """
    import os
    from ..fabric_integration import FabricIntegration
    
    fabric_url = os.getenv("FABRIC_BASE_URL")
    if not fabric_url:
        return 0
        
    try:
        async with FabricIntegration() as fabric:
            tools = await fabric.discover_tools()
            for tool_def in tools:
                # Wrap each Fabric tool in our adapter
                registry.register(FabricTool(tool_def, client=fabric.client))
            return len(tools)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to register Fabric tools: {e}")
        return 0


async def register_mcp_tools(registry: ToolRegistry, url: str) -> int:
    """
    Discover and register tools from a standard MCP server (SSE).
    """
    from ..mcp_client import StandardMCPClient
    from .mcp_adapter import StandardMCPTool
    
    try:
        async with StandardMCPClient(url) as client:
            tools = await client.list_tools()
            for tool_def in tools:
                registry.register(StandardMCPTool(tool_def, client=client))
            return len(tools)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to register tools from MCP server {url}: {e}")
        return 0


def get_available_tools() -> list[dict]:
    """Get list of all available tools with their metadata"""
    registry = get_registry()
    return registry.list_tools()


def get_tool_schemas() -> dict:
    """Get schemas for all tools in a format suitable for LLM system prompts"""
    registry = get_registry()
    tools = registry.list_tools()

    schemas = {}
    for tool in tools:
        schemas[tool["name"]] = {
            "description": tool["description"],
            "permission": tool["permission"],
            "parameters": tool["parameters"]
        }

    return schemas


def format_tools_for_prompt() -> str:
    """Format available tools as a string for inclusion in system prompts"""
    tools = get_available_tools()

    lines = ["\n=== AVAILABLE TOOLS ===\n"]

    for tool in tools:
        lines.append(f"\n{tool['name']}:")
        lines.append(f"  Description: {tool['description']}")
        lines.append(f"  Permission: {tool['permission']}")
        if tool['parameters']:
            lines.append("  Parameters:")
            for param_name, param_info in tool['parameters'].items():
                required = " (required)" if param_info.get('required') else ""
                lines.append(f"    - {param_name}: {param_info.get('description', 'No description')}{required}")
        else:
            lines.append("  Parameters: None")

    lines.append("\n=== TOOL USAGE ===")
    lines.append("To use a tool, you must:")
    lines.append("1. Check if you have permission (check tool.permission)")
    lines.append("2. Call the tool with required parameters")
    lines.append("3. Wait for the result before proceeding")
    lines.append("4. NEVER hallucinate tool results - only report actual tool outputs")
    lines.append("\nIf you don't have a tool for a task, say so explicitly.")

    return "\n".join(lines)
