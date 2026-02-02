"""
Aether - Semi-Autonomous AI Assistant Agent

Patent-worthy features:
1. Mutable memory via Redis Stack (checkpoint/rollback)
2. Hybrid human-AI autonomy with approval gates
3. Fleet Manager pod orchestration

Built on OpenClaw (formerly Clawdbot) foundation with novel extensions.
"""

__version__ = "1.0.0"
__author__ = "AetherPro Technologies"

from .nvidia_kit import NVIDIAKit, ModelResponse, quick_complete, quick_vision
from .aether_memory import AetherMemory, MemoryEntry, SearchResult
from .aether_core import AetherCore, AgentConfig, Task, AutonomyController, FleetManager
from .browser_control import BrowserControl, BrowserToolIntegration, BrowserState, BrowserAction

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
]
