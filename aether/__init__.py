"""
Aether - Semi-Autonomous AI Assistant Agent

Patent-worthy features:
1. Mutable memory via Redis Stack (checkpoint/rollback)
2. Native model-driven tool orchestration runtime
3. Fleet Manager pod orchestration

Built on OpenClaw (formerly Clawdbot) foundation with novel extensions.
"""

__version__ = "1.0.0"
__author__ = "AetherPro Technologies"

from .nvidia_kit import NVIDIAKit, ModelResponse, quick_complete, quick_vision
from .aether_memory import AetherMemory, MemoryEntry, SearchResult
from .aether_core import AetherCore, AgentConfig, Task, AutonomyController, FleetManager
from .browser_control import BrowserControl, BrowserToolIntegration, BrowserState, BrowserAction
from .agent_runtime_v2 import AgentRuntimeV2, AgentState, ToolCall, ToolExecution
from .agent_websocket import AgentSessionManager, get_agent_manager

__all__ = [
    # NVIDIA Kit
    "NVIDIAKit",
    "ModelResponse",
    "quick_complete",
    "quick_vision",
    
    # Memory
    "AetherMemory",
    "MemoryEntry",
    "SearchResult",
    
    # Core
    "AetherCore",
    "AgentConfig",
    "Task",
    "AutonomyController",
    "FleetManager",
    
    # Browser
    "BrowserControl",
    "BrowserToolIntegration",
    "BrowserState",
    "BrowserAction",
    
    # Agent Runtime (Event-driven state machine)
    "AgentRuntimeV2",
    "AgentState",
    "ToolCall",
    "ToolExecution",
    "AgentSessionManager",
    "get_agent_manager",
]
