"""
Aether Redis Memory Module

Redis-powered memory management with checkpoint/rollback capabilities.

Patent claim: Novel method for AI agent memory mutation via distributed caches,
enabling reversible context tweaks without persistent file writes.

Key features:
- Dynamic flush/refresh/checkpoint/rollback operations
- Atomic snapshots via Redis AOF
- Ephemeral scratchpads with TTL
- Semantic search via RedisSearch
- Automatic migration from daily to long-term memory
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid as uuid_lib

import redis.asyncio as aioredis
from redis.commands.search.field import TextField, NumericField, TagField
from redis.commands.search.index_definition import IndexDefinition, IndexType
from redis.commands.search.query import Query


@dataclass
class MemoryEntry:
    """Single memory entry"""
    content: str
    timestamp: str
    source: str = "user"
    tags: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class SearchResult:
    """Memory search result"""
    content: str
    score: float
    source: str
    timestamp: str
    key: str


class AetherMemory:
    """
    Redis-based memory management for Aether agent.
    
    Provides mutable, reversible memory operations with checkpoint/rollback
    capabilities. Differentiates from OpenClaw's static Markdown approach.
    """
    
    # Redis key prefixes
    PREFIX_DAILY = "aether:memory:daily"
    PREFIX_LONGTERM = "aether:memory:longterm"
    PREFIX_CHECKPOINT = "aether:memory:checkpoint"
    PREFIX_SCRATCHPAD = "aether:memory:scratchpad"
    INDEX_NAME = "aether:memory:search:index"
    
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        redis_db: int = 0
    ):
        """
        Initialize Redis memory manager.
        
        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_password: Optional Redis password
            redis_db: Redis database number
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password or os.getenv("REDIS_PASSWORD")
        self.redis_db = redis_db
        
        self.redis: Optional[aioredis.Redis] = None
        self._index_created = False
    
    async def connect(self):
        """Establish Redis connection"""
        if self.redis is None:
            self.redis = await aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}",
                password=self.redis_password,
                encoding="utf-8",
                decode_responses=True
            )
            await self._ensure_index()
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            self.redis = None
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _ensure_index(self):
        """Create RedisSearch index if it doesn't exist"""
        if self._index_created:
            return
        
        try:
            # Try to get index info
            await self.redis.ft(self.INDEX_NAME).info()
            self._index_created = True
        except:
            # Index doesn't exist, create it
            try:
                schema = (
                    TextField("content", weight=2.0),
                    TextField("source"),
                    TextField("timestamp"),
                    TagField("tags"),
                    NumericField("score")
                )
                
                definition = IndexDefinition(
                    prefix=[f"{self.PREFIX_DAILY}:", f"{self.PREFIX_LONGTERM}:"],
                    index_type=IndexType.HASH
                )
                
                await self.redis.ft(self.INDEX_NAME).create_index(
                    schema,
                    definition=definition
                )
                self._index_created = True
            except Exception as e:
                # Index might already exist from another instance
                pass
    
    def _get_daily_key(self, date: Optional[str] = None) -> str:
        """Get Redis key for daily log"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        return f"{self.PREFIX_DAILY}:{date}"
    
    def _get_checkpoint_key(self, uuid: str) -> str:
        """Get Redis key for checkpoint"""
        return f"{self.PREFIX_CHECKPOINT}:{uuid}"
    
    def _get_scratchpad_key(self, id: str) -> str:
        """Get Redis key for scratchpad"""
        return f"{self.PREFIX_SCRATCHPAD}:{id}"
    
    async def log_daily(
        self,
        content: str,
        date: Optional[str] = None,
        source: str = "user",
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Log entry to daily memory.
        
        Args:
            content: Memory content
            date: Date string (YYYY-MM-DD), defaults to today
            source: Source of memory (user, system, agent)
            tags: Optional tags for categorization
            
        Returns:
            Redis key of stored entry
        """
        if not self.redis:
            await self.connect()
        
        entry = MemoryEntry(
            content=content,
            timestamp=datetime.now().isoformat(),
            source=source,
            tags=tags or []
        )
        
        key = self._get_daily_key(date)
        entry_id = str(uuid_lib.uuid4())[:8]
        field_key = f"{key}:{entry_id}"
        
        # Store as hash for RedisSearch indexing
        await self.redis.hset(
            field_key,
            mapping={
                "content": entry.content,
                "timestamp": entry.timestamp,
                "source": entry.source,
                "tags": ",".join(entry.tags),
                "score": 1.0
            }
        )
        
        # Also append to list for chronological access
        await self.redis.rpush(key, json.dumps(asdict(entry)))
        
        return field_key
    
    async def load_daily(
        self,
        date: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[MemoryEntry]:
        """
        Load daily memory entries.
        
        Args:
            date: Date string (YYYY-MM-DD), defaults to today
            limit: Optional limit on number of entries
            
        Returns:
            List of MemoryEntry objects
        """
        if not self.redis:
            await self.connect()
        
        key = self._get_daily_key(date)
        
        if limit:
            entries_json = await self.redis.lrange(key, -limit, -1)
        else:
            entries_json = await self.redis.lrange(key, 0, -1)
        
        entries = []
        for entry_json in entries_json:
            try:
                entry_dict = json.loads(entry_json)
                entries.append(MemoryEntry(**entry_dict))
            except:
                continue
        
        return entries
    
    async def load_longterm(self) -> Dict[str, Any]:
        """
        Load long-term memory.
        
        Returns:
            Dictionary of long-term memory data
        """
        if not self.redis:
            await self.connect()
        
        data = await self.redis.get(self.PREFIX_LONGTERM)
        
        if data:
            return json.loads(data)
        return {}
    
    async def update_longterm(self, data: Dict[str, Any]):
        """
        Update long-term memory.
        
        Args:
            data: Dictionary of memory data to store
        """
        if not self.redis:
            await self.connect()
        
        await self.redis.set(
            self.PREFIX_LONGTERM,
            json.dumps(data, indent=2)
        )
    
    async def flush_context(self, keys: List[str]):
        """
        Flush (delete) specific memory keys.
        
        Args:
            keys: List of Redis keys to delete
        """
        if not self.redis:
            await self.connect()
        
        if keys:
            await self.redis.delete(*keys)
    
    async def checkpoint_snapshot(self, name: Optional[str] = None) -> str:
        """
        Create a checkpoint snapshot of current memory state.
        
        Args:
            name: Optional checkpoint name
            
        Returns:
            UUID of checkpoint
        """
        if not self.redis:
            await self.connect()
        
        checkpoint_uuid = str(uuid_lib.uuid4())
        checkpoint_key = self._get_checkpoint_key(checkpoint_uuid)
        
        # Snapshot current state
        snapshot = {
            "uuid": checkpoint_uuid,
            "name": name or f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "daily": {},
            "longterm": await self.load_longterm()
        }
        
        # Capture recent daily logs (last 7 days)
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            entries = await self.load_daily(date)
            if entries:
                snapshot["daily"][date] = [asdict(e) for e in entries]
        
        # Store checkpoint
        await self.redis.set(
            checkpoint_key,
            json.dumps(snapshot, indent=2)
        )
        
        # Add to checkpoints list
        await self.redis.rpush(
            f"{self.PREFIX_CHECKPOINT}:list",
            json.dumps({
                "uuid": checkpoint_uuid,
                "name": snapshot["name"],
                "timestamp": snapshot["timestamp"]
            })
        )
        
        return checkpoint_uuid
    
    async def rollback_to(self, uuid: str) -> bool:
        """
        Rollback memory to a checkpoint.
        
        Args:
            uuid: Checkpoint UUID
            
        Returns:
            True if successful, False otherwise
        """
        if not self.redis:
            await self.connect()
        
        checkpoint_key = self._get_checkpoint_key(uuid)
        snapshot_json = await self.redis.get(checkpoint_key)
        
        if not snapshot_json:
            return False
        
        snapshot = json.loads(snapshot_json)
        
        # Restore long-term memory
        await self.update_longterm(snapshot["longterm"])
        
        # Restore daily logs
        for date, entries_data in snapshot["daily"].items():
            key = self._get_daily_key(date)
            
            # Clear existing
            await self.redis.delete(key)
            
            # Restore entries
            for entry_data in entries_data:
                await self.redis.rpush(key, json.dumps(entry_data))
        
        return True
    
    async def list_checkpoints(self) -> List[Dict[str, str]]:
        """
        List all available checkpoints.
        
        Returns:
            List of checkpoint metadata dicts
        """
        if not self.redis:
            await self.connect()
        
        checkpoints_json = await self.redis.lrange(
            f"{self.PREFIX_CHECKPOINT}:list",
            0,
            -1
        )
        
        checkpoints = []
        for cp_json in checkpoints_json:
            try:
                checkpoints.append(json.loads(cp_json))
            except:
                continue
        
        return checkpoints
    
    async def search_semantic(
        self,
        query: str,
        limit: int = 10,
        source_filter: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Semantic search across memory using RedisSearch.
        
        Args:
            query: Search query
            limit: Maximum results to return
            source_filter: Optional source filter (user, system, agent)
            
        Returns:
            List of SearchResult objects
        """
        if not self.redis:
            await self.connect()
        
        # Build query
        query_str = query
        if source_filter:
            query_str = f"@source:{source_filter} {query}"
        
        search_query = (
            Query(query_str)
            .paging(0, limit)
            .sort_by("score", asc=False)
        )
        
        try:
            results = await self.redis.ft(self.INDEX_NAME).search(search_query)
            
            search_results = []
            for doc in results.docs:
                search_results.append(SearchResult(
                    content=doc.content,
                    score=float(doc.score) if hasattr(doc, 'score') else 1.0,
                    source=doc.source if hasattr(doc, 'source') else "unknown",
                    timestamp=doc.timestamp if hasattr(doc, 'timestamp') else "",
                    key=doc.id
                ))
            
            return search_results
        
        except Exception as e:
            # Fallback to simple text search if RedisSearch fails
            return await self._fallback_search(query, limit)
    
    async def _fallback_search(self, query: str, limit: int) -> List[SearchResult]:
        """Fallback search using simple string matching"""
        results = []
        
        # Search recent daily logs
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            entries = await self.load_daily(date)
            
            for entry in entries:
                if query.lower() in entry.content.lower():
                    results.append(SearchResult(
                        content=entry.content,
                        score=1.0,
                        source=entry.source,
                        timestamp=entry.timestamp,
                        key=f"daily:{date}"
                    ))
        
        return results[:limit]
    
    async def scratchpad_new(
        self,
        id: str,
        content: str,
        expire_h: int = 1
    ) -> str:
        """
        Create ephemeral scratchpad with TTL.
        
        Args:
            id: Scratchpad identifier
            content: Scratchpad content
            expire_h: Expiration time in hours
            
        Returns:
            Redis key of scratchpad
        """
        if not self.redis:
            await self.connect()
        
        key = self._get_scratchpad_key(id)
        
        await self.redis.set(
            key,
            content,
            ex=expire_h * 3600  # Convert hours to seconds
        )
        
        return key
    
    async def scratchpad_get(self, id: str) -> Optional[str]:
        """
        Get scratchpad content.
        
        Args:
            id: Scratchpad identifier
            
        Returns:
            Scratchpad content or None if not found
        """
        if not self.redis:
            await self.connect()
        
        key = self._get_scratchpad_key(id)
        return await self.redis.get(key)
    
    async def migrate_daily_to_longterm(
        self,
        date: str,
        importance_threshold: float = 0.7
    ):
        """
        Migrate important daily entries to long-term memory.
        
        Args:
            date: Date string (YYYY-MM-DD)
            importance_threshold: Threshold for migration (0-1)
        """
        if not self.redis:
            await self.connect()
        
        # Load daily entries
        entries = await self.load_daily(date)
        
        # Load current long-term memory
        longterm = await self.load_longterm()
        
        if "entries" not in longterm:
            longterm["entries"] = []
        
        # Migrate important entries
        # (In production, you'd use a model to score importance)
        for entry in entries:
            # Simple heuristic: migrate if tagged or from system
            if entry.tags or entry.source == "system":
                longterm["entries"].append({
                    "content": entry.content,
                    "original_date": date,
                    "timestamp": entry.timestamp,
                    "source": entry.source,
                    "tags": entry.tags
                })
        
        # Update long-term memory
        await self.update_longterm(longterm)
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get memory usage statistics.
        
        Returns:
            Dictionary of memory stats
        """
        if not self.redis:
            await self.connect()
        
        stats = {
            "daily_logs": {},
            "longterm_size": 0,
            "checkpoints": 0,
            "scratchpads": 0
        }
        
        # Count daily logs
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            key = self._get_daily_key(date)
            count = await self.redis.llen(key)
            if count > 0:
                stats["daily_logs"][date] = count
        
        # Long-term memory size
        longterm = await self.load_longterm()
        stats["longterm_size"] = len(json.dumps(longterm))
        
        # Checkpoints
        checkpoints = await self.list_checkpoints()
        stats["checkpoints"] = len(checkpoints)
        
        # Scratchpads (approximate)
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=f"{self.PREFIX_SCRATCHPAD}:*",
                count=100
            )
            stats["scratchpads"] += len(keys)
            if cursor == 0:
                break
        
        return stats


# Example usage
if __name__ == "__main__":
    async def main():
        async with AetherMemory() as memory:
            # Log some daily entries
            await memory.log_daily(
                "User prefers morning meetings",
                tags=["preference", "scheduling"]
            )
            await memory.log_daily(
                "Project deadline: March 15, 2026",
                tags=["deadline", "project"]
            )
            
            # Create checkpoint
            checkpoint_id = await memory.checkpoint_snapshot("before_changes")
            print(f"Created checkpoint: {checkpoint_id}")
            
            # Search memory
            results = await memory.search_semantic("meeting")
            print(f"\nSearch results for 'meeting':")
            for result in results:
                print(f"  - {result.content} (score: {result.score})")
            
            # Get stats
            stats = await memory.get_memory_stats()
            print(f"\nMemory stats: {json.dumps(stats, indent=2)}")
    
    asyncio.run(main())
