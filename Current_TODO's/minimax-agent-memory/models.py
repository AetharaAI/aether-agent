"""
Persi Database Models
SQLAlchemy models for PostgreSQL with pgvector support.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Text, DateTime, JSON, Integer, Boolean,
    ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import uuid

# Try to import pgvector, fallback gracefully if not available
try:
    from pgvector.sqlalchemy import Vector
    VECTOR_AVAILABLE = True
except ImportError:
    VECTOR_AVAILABLE = False
    Vector = None

Base = declarative_base()


class Conversation(Base):
    """Conversation history table."""
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(String(255), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    user_message = Column(Text, nullable=False)
    assistant_message = Column(Text, nullable=False)
    
    context = Column(JSONB, default={})
    
    # Token counts for cost tracking
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    
    # Vector embedding for semantic search (if pgvector available)
    if VECTOR_AVAILABLE:
        embedding = Column(Vector(1536))
    
    # Indexes
    __table_args__ = (
        Index('idx_conversation_timestamp', 'conversation_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<Conversation {self.id} - {self.timestamp}>"


class Project(Base):
    """Projects tracking table."""
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    status = Column(String(50), default="active")  # active, paused, completed, archived
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_activity = Column(DateTime(timezone=True))
    
    # Metrics and metadata
    metrics = Column(JSONB, default={})
    meta_data = Column(JSONB, default={})
    
    # Notes/documentation
    notes = Column(Text)
    
    # Repository/deployment info
    repo_url = Column(String(500))
    deployment_url = Column(String(500))
    
    def __repr__(self):
        return f"<Project {self.name} - {self.status}>"


class Task(Base):
    """Tasks/TODOs table."""
    __tablename__ = "tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    
    status = Column(String(50), default="todo")  # todo, in_progress, blocked, done
    priority = Column(String(20), default="medium")  # low, medium, high, critical
    
    # Relationships
    project_id = Column(UUID(as_uuid=True), ForeignKey('projects.id'), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Assignment (could be Persi, Cory, or another agent)
    assigned_to = Column(String(100), default="persi")
    
    # Metadata
    tags = Column(JSONB, default=[])
    meta_data = Column(JSONB, default={})
    
    # Indexes
    __table_args__ = (
        Index('idx_task_status_priority', 'status', 'priority'),
        Index('idx_task_project', 'project_id'),
    )
    
    def __repr__(self):
        return f"<Task {self.title} - {self.status}>"


class AgentAction(Base):
    """Log of agent actions for audit trail."""
    __tablename__ = "agent_actions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    action_type = Column(String(100), nullable=False)  # tool_execution, delegation, etc.
    action_name = Column(String(255), nullable=False)
    
    # Input/output
    input_data = Column(JSONB)
    output_data = Column(JSONB)
    
    # Result
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    # Execution details
    execution_time_ms = Column(Integer)
    
    # Context
    conversation_id = Column(String(255), nullable=True)
    triggered_by = Column(String(100), default="user")  # user, autonomous, scheduled, etc.
    
    # Indexes
    __table_args__ = (
        Index('idx_action_timestamp', 'timestamp'),
        Index('idx_action_type', 'action_type'),
    )
    
    def __repr__(self):
        return f"<AgentAction {self.action_name} - {self.timestamp}>"


class Memory(Base):
    """Key-value memory store for learned information."""
    __tablename__ = "memory"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(255), nullable=False, unique=True, index=True)
    value = Column(JSONB, nullable=False)
    
    category = Column(String(100))  # preferences, facts, context, etc.
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    accessed_at = Column(DateTime(timezone=True))
    access_count = Column(Integer, default=0)
    
    # Metadata
    meta_data = Column(JSONB, default={})
    
    def __repr__(self):
        return f"<Memory {self.key}>"


class AgentCoordination(Base):
    """Track agent-to-agent coordination."""
    __tablename__ = "agent_coordination"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Which agents are involved
    coordinator_agent = Column(String(100), default="persi")
    target_agent = Column(String(100), nullable=False)
    
    # Task details
    task_type = Column(String(100), nullable=False)
    task_description = Column(Text)
    parameters = Column(JSONB)
    
    # Status
    status = Column(String(50), default="pending")  # pending, in_progress, completed, failed
    
    # Results
    result = Column(JSONB)
    error_message = Column(Text, nullable=True)
    
    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    
    def __repr__(self):
        return f"<AgentCoordination {self.coordinator_agent} -> {self.target_agent}>"
