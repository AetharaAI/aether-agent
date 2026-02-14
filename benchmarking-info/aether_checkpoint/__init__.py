"""
AetherCheckpoint - Infinite Execution Engine
=============================================
Checkpointed episodic execution with context compaction and loop rehydration.

Converts any stateless LLM agent into a persistent process with theoretically
unlimited runtime by decoupling working memory from persistent memory.

Architecture:
    Working Memory (Redis)  →  fast, ephemeral, current loop only
    Episodic Memory (Postgres) →  checkpoint summaries, continuation state
    Semantic Memory (Weaviate) →  long-term facts, embeddings, knowledge graph

Usage:
    from aether_checkpoint import CheckpointEngine, MemoryConfig

    engine = CheckpointEngine(config=MemoryConfig(...))
    engine.run(objective="Deploy Docker pipeline for AetherOS")

Author: Cory / AetherPro Technologies LLC
License: Proprietary
"""

from .engine import CheckpointEngine
from .config import MemoryConfig, CheckpointTrigger, StorageBackend
from .memory import WorkingMemory, EpisodicMemory, SemanticMemory
from .checkpoint import CheckpointManager, Checkpoint
from .checkpointer import (
    Checkpointer,
    CheckpointState,
    DistillationStrategy,
    RuleBasedDistillation,
    LLMDistillation,
)
from .loop import ExecutionLoop, AgentProtocol

__version__ = "1.0.0"
__all__ = [
    # Top-level orchestrator
    "CheckpointEngine",
    # Configuration
    "MemoryConfig",
    "CheckpointTrigger",
    "StorageBackend",
    # Memory layers
    "WorkingMemory",
    "EpisodicMemory",
    "SemanticMemory",
    # Checkpoint models
    "CheckpointManager",
    "Checkpoint",
    # State distillation
    "Checkpointer",
    "CheckpointState",
    "DistillationStrategy",
    "RuleBasedDistillation",
    "LLMDistillation",
    # Execution
    "ExecutionLoop",
    "AgentProtocol",
]
