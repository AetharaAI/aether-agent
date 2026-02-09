"""
Persi Memory Manager
Handles both short-term (Redis) and long-term (PostgreSQL) memory.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4
from urllib.parse import quote_plus, urlparse, urlunparse

import redis.asyncio as aioredis
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import structlog

from persi.memory.models import (
    Base, Conversation, Project, Task, AgentAction, Memory, AgentCoordination
)
from persi.config.settings import Settings

logger = structlog.get_logger()


def encode_password_in_url(url: str) -> str:
    """
    Properly encode password in database URL.
    
    PostgreSQL passwords with special characters (like @, :, /, #, etc.)
    need to be URL-encoded in the connection string.
    """
    parsed = urlparse(url)
    
    # Split username:password from host:port
    if '@' in parsed.netloc:
        auth, hostport = parsed.netloc.rsplit('@', 1)
        if ':' in auth:
            username, password = auth.split(':', 1)
            # URL encode the password to handle special characters
            encoded_password = quote_plus(password)
            encoded_auth = f"{username}:{encoded_password}"
            encoded_netloc = f"{encoded_auth}@{hostport}"
        else:
            encoded_netloc = parsed.netloc
    else:
        encoded_netloc = parsed.netloc
    
    # Reconstruct URL with encoded password
    encoded_url = urlunparse((
        parsed.scheme,
        encoded_netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        parsed.fragment
    ))
    
    return encoded_url


class MemoryManager:
    """
    Manages Persi's memory across both short-term and long-term storage.
    
    Short-term (Redis):
    - Current conversation context
    - Active task state
    - Cache for frequent queries
    
    Long-term (PostgreSQL):
    - Full conversation history
    - Projects and tasks
    - Agent actions (audit log)
    - Learned preferences
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        
        # PostgreSQL setup
        # Properly encode password in URL (handles special characters)
        db_url = encode_password_in_url(settings.database.url)
        
        # Convert postgresql:// to postgresql+asyncpg:// for async support
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        self.engine = create_async_engine(
            db_url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_pre_ping=settings.database.pool_pre_ping,
            echo=False
        )
        
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Redis setup
        self.redis: Optional[aioredis.Redis] = None
        self.redis_connection_timeout = 5  # seconds

        logger.info("Memory manager initialized")
    
    async def initialize(self):
        """Initialize connections and create tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Connect to Redis
        try:
            self.redis = await asyncio.wait_for(
                aioredis.from_url(
                    self.settings.redis.url,
                    encoding="utf-8",
                    decode_responses=True
                ),
                timeout=self.redis_connection_timeout
            )
            await asyncio.wait_for(self.redis.ping(), timeout=self.redis_connection_timeout)
            logger.info("Redis connected")
        except asyncio.TimeoutError:
            logger.warning("Redis connection timed out, running without cache", timeout=self.redis_connection_timeout)
            if self.redis:
                await self.redis.close()
            self.redis = None
        except Exception as e:
            logger.warning("Redis connection failed, running without cache", error=str(e))
            if self.redis:
                await self.redis.close()
            self.redis = None
    
    async def close(self):
        """Close all connections."""
        if self.redis:
            await self.redis.close()
        await self.engine.dispose()
    
    # ==================== Conversation Management ====================
    
    async def store_conversation(
        self,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        context: Optional[Dict[str, Any]] = None,
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> str:
        """Store a conversation turn in the database."""
        
        async with self.async_session() as session:
            conversation = Conversation(
                conversation_id=conversation_id,
                user_message=user_message,
                assistant_message=assistant_message,
                context=context or {},
                input_tokens=input_tokens,
                output_tokens=output_tokens
            )
            
            session.add(conversation)
            await session.commit()
            
            logger.info(
                "Conversation stored",
                conversation_id=conversation_id,
                id=str(conversation.id)
            )
            
            return str(conversation.id)
    
    async def get_recent_conversation(
        self,
        conversation_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent conversation history."""
        
        async with self.async_session() as session:
            stmt = select(Conversation).where(
                Conversation.conversation_id == conversation_id
            ).order_by(desc(Conversation.timestamp)).limit(limit)
            
            result = await session.execute(stmt)
            conversations = result.scalars().all()
            
            # Return in chronological order
            return [
                {
                    "role": "user",
                    "content": conv.user_message,
                    "timestamp": conv.timestamp.isoformat()
                }
                for conv in reversed(conversations)
            ] + [
                {
                    "role": "assistant",
                    "content": conv.assistant_message,
                    "timestamp": conv.timestamp.isoformat()
                }
                for conv in reversed(conversations)
            ]
    
    # ==================== Project Management ====================
    
    async def get_projects(
        self,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all projects, optionally filtered by status."""
        
        async with self.async_session() as session:
            stmt = select(Project)
            
            if status:
                stmt = stmt.where(Project.status == status)
            
            stmt = stmt.order_by(desc(Project.updated_at))
            
            result = await session.execute(stmt)
            projects = result.scalars().all()
            
            return [
                {
                    "id": str(proj.id),
                    "name": proj.name,
                    "description": proj.description,
                    "status": proj.status,
                    "updated_at": proj.updated_at.isoformat() if proj.updated_at else None,
                    "metrics": proj.metrics,
                    "meta_data": proj.meta_data
                }
                for proj in projects
            ]
    
    async def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        **kwargs
    ) -> str:
        """Create a new project."""
        
        async with self.async_session() as session:
            project = Project(
                name=name,
                description=description,
                **kwargs
            )
            
            session.add(project)
            await session.commit()
            
            logger.info("Project created", name=name, id=str(project.id))
            
            return str(project.id)
    
    # ==================== Task Management ====================
    
    async def get_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get tasks with optional filters."""
        
        async with self.async_session() as session:
            stmt = select(Task)
            
            conditions = []
            if status:
                conditions.append(Task.status == status)
            if priority:
                conditions.append(Task.priority == priority)
            if project_id:
                conditions.append(Task.project_id == project_id)
            
            if conditions:
                stmt = stmt.where(and_(*conditions))
            
            stmt = stmt.order_by(
                Task.priority.desc(),
                Task.created_at.asc()
            )
            
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            
            return [
                {
                    "id": str(task.id),
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                    "priority": task.priority,
                    "assigned_to": task.assigned_to,
                    "created_at": task.created_at.isoformat(),
                    "due_date": task.due_date.isoformat() if task.due_date else None,
                    "tags": task.tags,
                    "meta_data": task.meta_data
                }
                for task in tasks
            ]
    
    async def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        priority: str = "medium",
        **kwargs
    ) -> str:
        """Create a new task."""
        
        async with self.async_session() as session:
            task = Task(
                title=title,
                description=description,
                priority=priority,
                **kwargs
            )
            
            session.add(task)
            await session.commit()
            
            logger.info("Task created", title=title, id=str(task.id))
            
            return str(task.id)
    
    # ==================== Agent Actions (Audit Log) ====================
    
    async def log_action(
        self,
        action_type: str,
        action_name: str,
        input_data: Optional[Dict] = None,
        output_data: Optional[Dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        **kwargs
    ) -> str:
        """Log an agent action for audit trail."""
        
        async with self.async_session() as session:
            action = AgentAction(
                action_type=action_type,
                action_name=action_name,
                input_data=input_data,
                output_data=output_data,
                success=success,
                error_message=error_message,
                execution_time_ms=execution_time_ms,
                **kwargs
            )
            
            session.add(action)
            await session.commit()
            
            return str(action.id)
    
    # ==================== Memory/Preferences ====================
    
    async def store_memory(
        self,
        key: str,
        value: Any,
        category: Optional[str] = None
    ):
        """Store a learned preference or fact."""
        
        async with self.async_session() as session:
            # Check if exists
            stmt = select(Memory).where(Memory.key == key)
            result = await session.execute(stmt)
            memory = result.scalar_one_or_none()
            
            if memory:
                memory.value = value
                memory.updated_at = datetime.utcnow()
                memory.access_count += 1
            else:
                memory = Memory(
                    key=key,
                    value=value,
                    category=category
                )
                session.add(memory)
            
            await session.commit()
    
    async def get_memory(self, key: str) -> Optional[Any]:
        """Retrieve a stored memory."""
        
        async with self.async_session() as session:
            stmt = select(Memory).where(Memory.key == key)
            result = await session.execute(stmt)
            memory = result.scalar_one_or_none()
            
            if memory:
                # Update access tracking
                memory.accessed_at = datetime.utcnow()
                memory.access_count += 1
                await session.commit()
                
                return memory.value
            
            return None
    
    # ==================== Redis Cache (Short-term) ====================
    
    async def cache_set(
        self,
        key: str,
        value: Any,
        expire_seconds: int = 3600
    ):
        """Set a value in Redis cache."""
        if not self.redis:
            return
        
        try:
            await self.redis.setex(
                key,
                expire_seconds,
                json.dumps(value)
            )
        except Exception as e:
            logger.warning("Redis cache set failed", error=str(e))
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """Get a value from Redis cache."""
        if not self.redis:
            return None
        
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.warning("Redis cache get failed", error=str(e))
        
        return None
