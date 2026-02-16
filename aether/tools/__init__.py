"""
Aether Tool Layer

================================================================================
ARCHITECTURE: Tool Layer
================================================================================

This module provides a formal tool registry for agent-accessible operations.
Tools are permissioned and logged for auditability.

LAYER POSITION:
  Identity Layer -> Memory Layer -> Context Layer -> Provider Layer -> [TOOL LAYER]

TOOL CATEGORIES:
1. Memory Tools: checkpoint, compress_context, get_context_stats
2. System Tools: terminal_exec, file_upload
3. Future: TypeScript helpers via subprocess/RPC

PERMISSION MODEL:
- semi: Ask before external actions, internal freely
- auto: Proceed with logged accountability
- Tools log all calls to Redis for audit

USAGE:
    from aether.tools import ToolRegistry, get_registry
    
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

__all__ = [
    "ToolRegistry",
    "Tool",
    "ToolResult",
    "ToolPermission",
    "get_registry",
    "set_runtime_for_tools",
    "register_fabric_tools",
    "register_mcp_tools",
]

# Global registry instance
_registry: ToolRegistry | None = None


def get_registry(memory=None) -> ToolRegistry:
    """Get or create the global tool registry"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry(memory=memory)
        # Register core tools
        _registry.register(checkpoint_tool)
        _registry.register(checkpoint_and_continue_tool)
        _registry.register(compress_context_tool)
        _registry.register(get_context_stats_tool)
        _registry.register(terminal_exec_tool)
        _registry.register(file_upload_tool)
        _registry.register(file_read_tool)
        _registry.register(file_list_tool)
        _registry.register(file_write_tool)
        _registry.register(TavilySearchTool()) # Switched to Tavily
        _registry.register(URLReadTool())      # Added URL Reader
        _registry.register(set_mode_tool)
        _registry.register(search_memory_tool)
        _registry.register(list_checkpoints_tool)
        _registry.register(read_checkpoint_tool)
        _registry.register(recall_episodes_tool)
        _registry.register(search_workspace_tool)

        # Wire set_mode_tool with registry reference so it can change the mode
        set_mode_tool.set_registry(_registry)

        # Set memory reference for tools that need it
        if memory:
            checkpoint_tool.set_memory(memory)
            compress_context_tool.set_memory(memory)
            get_context_stats_tool.set_memory(memory)
            search_memory_tool.set_memory(memory)
            list_checkpoints_tool.set_memory(memory)
            read_checkpoint_tool.set_memory(memory)
            recall_episodes_tool.set_memory(memory)

    return _registry


def set_runtime_for_tools(runtime):
    """Set runtime reference for tools that need it (called after runtime creation)."""
    checkpoint_and_continue_tool.set_runtime(runtime)
    recall_episodes_tool.set_runtime(runtime)


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
