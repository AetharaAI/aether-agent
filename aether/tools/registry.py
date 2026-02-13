"""
Tool Registry

================================================================================
ARCHITECTURE: Tool Layer - Registry
================================================================================

Central registry for all agent-accessible tools.
Provides permission management, logging, and execution.

DESIGN PRINCIPLES:
1. Permission-based: Tools declare required permission level
2. Audit logging: All tool calls logged to Redis
3. Async-first: All tools are async for I/O operations
4. Type-safe: Structured input/output schemas

INTEGRATION:
- Used by AetherCore for tool execution
- Integrates with AutonomyController for permission checks
- Logs to AetherMemory for audit trail
================================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Awaitable
from datetime import datetime
import json


class ToolPermission(Enum):
    """Permission levels for tools"""
    INTERNAL = "internal"    # Always allowed (memory, stats)
    SEMI = "semi"           # Allowed in semi mode, no external calls
    AUTO = "auto"           # Requires auto mode or approval
    RESTRICTED = "restricted"  # Always requires approval

class Capability(str, Enum):
    """Tool capabilities for permission grouping"""
    READ_FILES = "read_files"
    WRITE_FILES = "write_files" 
    EXECUTE_CODE = "execute_code"
    NETWORK_ACCESS = "network_access"
    MEMORY_ACCESS = "memory_access"
    SYSTEM_CONTROL = "system_control"
    CODE_INTEL = "code_intel"


@dataclass
class ToolResult:
    """Result of tool execution"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    tool_name: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "tool_name": self.tool_name,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ToolCall:
    """Record of a tool call for audit logging"""
    tool_name: str
    arguments: Dict[str, Any]
    result: ToolResult
    autonomy_mode: str  # semi or auto
    user_approved: bool
    timestamp: datetime = field(default_factory=datetime.now)


class Tool(ABC):
    """
    Abstract base class for all tools.
    
    Tools must implement:
    - name: Unique tool identifier
    - description: Human-readable description
    - permission: Required permission level
    - execute(): The actual tool logic
    
    EXAMPLE:
        class MyTool(Tool):
            name = "my_tool"
            description = "Does something useful"
            permission = ToolPermission.SEMI
            
            async def execute(self, arg1: str, arg2: int = 0) -> ToolResult:
                # Tool logic here
                return ToolResult(success=True, data={"result": "done"})
    """
    
    name: str = ""
    description: str = ""
    permission: ToolPermission = ToolPermission.INTERNAL
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given arguments"""
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Get tool metadata for discovery"""
        return {
            "name": self.name,
            "description": self.description,
            "permission": self.permission.value,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """
    Central registry for agent tools.
    
    Manages tool registration, permission checking, and execution.
    Integrates with AetherMemory for audit logging.
    
    USAGE:
        registry = ToolRegistry()
        registry.register(MyTool())
        
        # Execute with permission check
        result = await registry.execute(
            "my_tool",
            arg1="value",
            autonomy_mode="semi"
        )
    """
    
    def __init__(self, memory=None):
        self._tools: Dict[str, Tool] = {}
        self._call_history: List[ToolCall] = []
        self._memory = memory  # AetherMemory for logging
        self._autonomy_mode: str = "semi"
    
    def register(self, tool: Tool) -> "ToolRegistry":
        """
        Register a tool in the registry.
        
        Args:
            tool: Tool instance to register
            
        Returns:
            Self for chaining
        """
        if not tool.name:
            raise ValueError("Tool must have a name")
        
        self._tools[tool.name] = tool
        return self
    
    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._tools.get(name)
    
    def list_tools(self, permission: Optional[ToolPermission] = None) -> List[Dict[str, Any]]:
        """
        List available tools.
        
        Args:
            permission: Filter by permission level (optional)
            
        Returns:
            List of tool metadata dictionaries
        """
        tools = self._tools.values()
        if permission:
            tools = [t for t in tools if t.permission == permission]
        return [t.to_dict() for t in tools]
    
    def check_permission(self, tool: Tool, autonomy_mode: str) -> bool:
        """
        Check if tool can be executed in current autonomy mode.
        
        Args:
            tool: Tool to check
            autonomy_mode: Current autonomy mode (semi or auto)
            
        Returns:
            True if allowed, False otherwise
        """
        if tool.permission == ToolPermission.INTERNAL:
            return True
        
        if tool.permission == ToolPermission.SEMI:
            return True
        
        if tool.permission in (ToolPermission.AUTO, ToolPermission.RESTRICTED):
            return autonomy_mode == "auto"
        
        return False
    
    async def execute(
        self,
        name: str,
        autonomy_mode: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Execute a tool with permission checking and logging.
        
        Args:
            name: Tool name
            autonomy_mode: Current autonomy mode (defaults to semi)
            **kwargs: Tool arguments
            
        Returns:
            ToolResult with execution results
        """
        start_time = datetime.now()
        
        # Get tool
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {name}",
                tool_name=name
            )
        
        mode = autonomy_mode or self._autonomy_mode
        
        # Check permission
        if not self.check_permission(tool, mode):
            return ToolResult(
                success=False,
                error=f"Tool '{name}' requires {tool.permission.value} mode (current: {mode})",
                tool_name=name
            )
        
        # Execute tool
        try:
            result = await tool.execute(**kwargs)
            result.tool_name = name
            
            # Calculate execution time
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            result.execution_time_ms = execution_time
            
        except Exception as e:
            result = ToolResult(
                success=False,
                error=str(e),
                tool_name=name,
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
        
        # Log to call history
        call_record = ToolCall(
            tool_name=name,
            arguments=kwargs,
            result=result,
            autonomy_mode=mode,
            user_approved=mode == "auto" or tool.permission == ToolPermission.INTERNAL
        )
        self._call_history.append(call_record)
        
        # Log to Redis if memory available
        if self._memory:
            try:
                await self._memory.log_daily(
                    f"Tool call: {name} - Success: {result.success}",
                    source="system",
                    tags=["tool", name, "success" if result.success else "error"]
                )
            except Exception:
                pass  # Don't fail if logging fails
        
        return result
    
    def get_history(self, limit: int = 100) -> List[ToolCall]:
        """Get recent tool call history"""
        return self._call_history[-limit:]
    
    def clear_history(self):
        """Clear tool call history"""
        self._call_history.clear()
    
    def set_memory(self, memory):
        """Set AetherMemory for audit logging"""
        self._memory = memory
    
    def set_autonomy_mode(self, mode: str):
        """Update default autonomy mode"""
        self._autonomy_mode = mode
