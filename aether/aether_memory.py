"""
Aether Redis Memory Module

================================================================================
ARCHITECTURE: Identity Layer + Memory Layer + Context Layer
================================================================================

This module implements THREE architectural layers:

1. IDENTITY LAYER (Lines ~620-909)
   - Persistent identity and user profiles
   - Redis-backed storage (survives restarts)
   - Dynamic system prompt generation
   - Unlike OpenClaw's file-based approach

2. MEMORY LAYER (Redis Stack)
   - Daily logs (short-term, 7-day window)
   - Long-term memory (compressed summaries)
   - Checkpoints (atomic snapshots for rollback)
   - Scratchpads (ephemeral with TTL)
   - Semantic search via RedisSearch

3. CONTEXT LAYER (Stats, Compression, Limits)
   - Real-time memory usage statistics
   - Automatic compression (daily → long-term)
   - Retention policies (7-day raw, 50 checkpoints)
   - Usage thresholds for warnings

Patent claim: Novel method for AI agent memory mutation via distributed caches,
enabling reversible context tweaks without persistent file writes.

Key features:
- Dynamic flush/refresh/checkpoint/rollback operations
- Atomic snapshots via Redis AOF
- Ephemeral scratchpads with TTL
- Semantic search via RedisSearch
- Automatic migration from daily to long-term memory
================================================================================
"""

import os
import json
import math
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Union, Set
from dataclasses import dataclass, asdict
from pathlib import Path
import uuid as uuid_lib
import logging

import redis.asyncio as aioredis
try:
    from redis.commands.search.field import TextField, NumericField, TagField
    from redis.commands.search.index_definition import IndexDefinition, IndexType
    from redis.commands.search.query import Query
except ImportError:
    # Handle different redis-py versions (camelCase vs snake_case)
    from redis.commands.search.field import TextField, NumericField, TagField
    from redis.commands.search.indexDefinition import IndexDefinition, IndexType
    from redis.commands.search.query import Query

# Configure logging
logger = logging.getLogger(__name__)

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
    
    Includes identity/profile persistence for true continuity across restarts.
    """
    
    # Redis key prefixes
    PREFIX_DAILY = "aether:daily"
    PREFIX_LONGTERM = "aether:longterm"
    PREFIX_CHECKPOINT = "aether:checkpoint"
    PREFIX_SCRATCHPAD = "aether:scratchpad"
    PREFIX_IDENTITY = "aether:identity"
    PREFIX_USER = "aether:user"
    PREFIX_SYSTEM = "aether:system"
    PREFIX_TOOLS = "aether:tools"
    PREFIX_EPISODE = "aether:episode"
    INDEX_NAME = "aether:memory:idx"
    
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
        
        # Vector memory (Qdrant) - optional, for hybrid search
        self._vector_memory = None
        self._vector_search_enabled = os.getenv("VECTOR_SEARCH_ENABLED", "true").lower() == "true"
        
        # Search tuning
        self._text_weight = float(os.getenv("SEARCH_TEXT_WEIGHT", "0.3"))
        self._vector_weight = float(os.getenv("SEARCH_VECTOR_WEIGHT", "0.7"))
        self._decay_half_life = float(os.getenv("MEMORY_DECAY_HALF_LIFE", "30"))
        self._mmr_lambda = float(os.getenv("MEMORY_MMR_LAMBDA", "0.7"))
    
    async def connect(self):
        """Establish Redis connection and optionally connect to Qdrant."""
        if self.redis is None:
            self.redis = await aioredis.from_url(
                f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}",
                password=self.redis_password,
                encoding="utf-8",
                decode_responses=True
            )
            await self._ensure_index()
        
        # Connect to Qdrant if vector search is enabled
        if self._vector_search_enabled and self._vector_memory is None:
            try:
                from .qdrant_adapter import QdrantMemory
                self._vector_memory = QdrantMemory()
                await self._vector_memory.connect()
                if self._vector_memory.client is None:
                    logger.warning("Qdrant connection failed - hybrid search disabled")
                    self._vector_memory = None
                else:
                    logger.info("Qdrant connected - hybrid search enabled")
            except ImportError:
                logger.warning("qdrant_adapter not available - vector search disabled")
            except Exception as e:
                logger.warning("Qdrant init failed: %s - vector search disabled", e)
                self._vector_memory = None
    
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
        
        # Auto-index to Qdrant for vector search
        if self._vector_memory and self._vector_memory.client:
            try:
                await self._vector_memory.add(
                    content=content,
                    role=source,
                    session_id="daily",
                    metadata={"tags": ",".join(tags or []), "date": date or datetime.now().strftime("%Y-%m-%d")},
                    timestamp=entry.timestamp
                )
            except Exception as e:
                logger.debug("Qdrant auto-index failed (non-fatal): %s", e)
        
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

    async def read_checkpoint(self, uuid: str) -> Optional[Dict[str, Any]]:
        """
        Read full checkpoint data by UUID.

        Args:
            uuid: Checkpoint UUID

        Returns:
            Checkpoint data dict or None if not found
        """
        if not self.redis:
            await self.connect()

        key = self._get_checkpoint_key(uuid)
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def search_semantic(
        self,
        query: str,
        limit: int = 10,
        source_filter: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Semantic search across memory.
        
        Uses hybrid BM25+vector search when Qdrant is available,
        falls back to RedisSearch full-text, then simple substring matching.
        
        Post-processing:
        - Temporal decay (recent memories rank higher)
        - MMR diversity (prevents near-duplicate results)
        
        Args:
            query: Search query
            limit: Maximum results to return
            source_filter: Optional source filter (user, system, agent)
            
        Returns:
            List of SearchResult objects, sorted by final score
        """
        if not self.redis:
            await self.connect()
        
        # Use hybrid search if vector memory is available
        if self._vector_memory and self._vector_memory.client:
            try:
                return await self._hybrid_search(query, limit, source_filter)
            except Exception as e:
                logger.warning("Hybrid search failed, falling back to text-only: %s", e)
        
        # Fallback: RedisSearch full-text only
        return await self._text_search(query, limit, source_filter)
    
    async def _text_search(
        self,
        query: str,
        limit: int = 10,
        source_filter: Optional[str] = None
    ) -> List[SearchResult]:
        """Full-text search via RedisSearch with temporal decay and MMR."""
        query_str = query
        if source_filter:
            query_str = f"@source:{source_filter} {query}"
        
        search_query = (
            Query(query_str)
            .paging(0, limit * 3)  # Fetch extra for post-processing
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
            
            # Apply temporal decay and MMR
            search_results = self._apply_temporal_decay(search_results)
            search_results = self._apply_mmr(search_results, limit=limit)
            
            return search_results
        
        except Exception as e:
            logger.debug("RedisSearch failed: %s, using fallback", e)
            return await self._fallback_search(query, limit)
    
    async def _hybrid_search(
        self,
        query: str,
        limit: int = 10,
        source_filter: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Hybrid BM25 + vector search with score fusion.
        
        1. Run RedisSearch FT query → text_results with BM25-style scores
        2. Run QdrantMemory.search() → vector_results with cosine scores  
        3. Merge by content key: final = text_weight × text_score + vector_weight × vector_score
        4. Apply temporal decay
        5. Apply MMR diversity
        """
        fetch_limit = limit * 3  # Fetch more for fusion + post-processing
        
        # 1. Text search (RedisSearch)
        text_results: Dict[str, SearchResult] = {}
        text_max_score = 1.0
        
        query_str = query
        if source_filter:
            query_str = f"@source:{source_filter} {query}"
        
        try:
            search_query = (
                Query(query_str)
                .paging(0, fetch_limit)
                .sort_by("score", asc=False)
            )
            ft_results = await self.redis.ft(self.INDEX_NAME).search(search_query)
            
            for doc in ft_results.docs:
                content = doc.content if hasattr(doc, 'content') else ""
                score = float(doc.score) if hasattr(doc, 'score') else 1.0
                text_max_score = max(text_max_score, score)
                
                text_results[content] = SearchResult(
                    content=content,
                    score=score,
                    source=doc.source if hasattr(doc, 'source') else "unknown",
                    timestamp=doc.timestamp if hasattr(doc, 'timestamp') else "",
                    key=doc.id
                )
        except Exception as e:
            logger.debug("RedisSearch component of hybrid search failed: %s", e)
        
        # 2. Vector search (Qdrant)
        vector_results: Dict[str, float] = {}
        vector_metadata: Dict[str, Dict[str, str]] = {}
        
        try:
            qdrant_results = await self._vector_memory.search(
                query=query,
                limit=fetch_limit
            )
            for entry in qdrant_results:
                vector_results[entry.content] = entry.score  # cosine similarity, 0-1
                vector_metadata[entry.content] = {
                    "source": entry.role,
                    "timestamp": entry.timestamp,
                    "key": f"qdrant:{entry.id}"
                }
        except Exception as e:
            logger.debug("Qdrant component of hybrid search failed: %s", e)
        
        # 3. Merge scores with weighted fusion
        all_contents: Set[str] = set(text_results.keys()) | set(vector_results.keys())
        merged: List[SearchResult] = []
        
        for content in all_contents:
            # Normalize text score to 0-1 range
            text_score = 0.0
            if content in text_results:
                text_score = text_results[content].score / text_max_score if text_max_score > 0 else 0.0
            
            vector_score = vector_results.get(content, 0.0)
            
            # Weighted fusion
            final_score = (self._text_weight * text_score) + (self._vector_weight * vector_score)
            
            # Get metadata from whichever source has it
            if content in text_results:
                result = SearchResult(
                    content=content,
                    score=final_score,
                    source=text_results[content].source,
                    timestamp=text_results[content].timestamp,
                    key=text_results[content].key
                )
            else:
                meta = vector_metadata.get(content, {})
                result = SearchResult(
                    content=content,
                    score=final_score,
                    source=meta.get("source", "unknown"),
                    timestamp=meta.get("timestamp", ""),
                    key=meta.get("key", "qdrant")
                )
            
            merged.append(result)
        
        # 3.5  Cross-encoder reranker (if available)
        if self._vector_memory and self._vector_memory.use_reranker and merged:
            try:
                docs = [r.content for r in merged]
                reranked = await self._vector_memory.rerank(
                    query=query,
                    documents=docs,
                    top_n=limit * 2  # Get more than needed for MMR to work with
                )
                if reranked:
                    # Rebuild merged list using reranker scores
                    reranked_results = []
                    for item in reranked:
                        idx = item["index"]
                        if idx < len(merged):
                            merged[idx].score = float(item["score"])
                            reranked_results.append(merged[idx])
                    merged = reranked_results
                    logger.debug("Reranker re-scored %d results", len(merged))
            except Exception as e:
                logger.debug("Reranker step failed (non-fatal): %s", e)
        
        # 4. Apply temporal decay
        merged = self._apply_temporal_decay(merged)
        
        # 5. Apply MMR diversity and return top-K
        merged = self._apply_mmr(merged, limit=limit)
        
        return merged
    
    def _apply_temporal_decay(
        self,
        results: List[SearchResult],
    ) -> List[SearchResult]:
        """
        Apply exponential temporal decay to search results.
        
        Formula: decayed_score = score × e^(-λ × age_in_days)
        Where λ = ln(2) / half_life_days
        
        A 30-day half-life means a memory scores 50% at 30 days, 25% at 60 days.
        Long-term/identity entries (with empty timestamps) are exempt.
        """
        if self._decay_half_life <= 0:
            return results
        
        lambda_ = math.log(2) / self._decay_half_life
        now = datetime.now()
        
        for result in results:
            if not result.timestamp:
                continue  # Exempt: no timestamp = evergreen
            
            try:
                entry_time = datetime.fromisoformat(result.timestamp)
                # Make both naive for comparison
                if entry_time.tzinfo:
                    entry_time = entry_time.replace(tzinfo=None)
                
                age_days = max(0, (now - entry_time).total_seconds() / 86400)
                decay_factor = math.exp(-lambda_ * age_days)
                result.score *= decay_factor
            except (ValueError, TypeError):
                pass  # Can't parse timestamp, skip decay
        
        # Re-sort by decayed score
        results.sort(key=lambda r: r.score, reverse=True)
        return results
    
    def _apply_mmr(
        self,
        results: List[SearchResult],
        limit: Optional[int] = None
    ) -> List[SearchResult]:
        """
        Maximal Marginal Relevance re-ranking.
        
        Iteratively selects results that maximize:
            MMR = λ × relevance − (1−λ) × max_similarity_to_already_selected
        
        Similarity: Jaccard on word-level tokens.
        λ=1.0 → pure relevance, λ=0.0 → max diversity.
        """
        if not results or self._mmr_lambda >= 1.0:
            return results[:limit] if limit else results
        
        limit = limit or len(results)
        
        # Tokenize all results
        tokenized = []
        for r in results:
            tokens = set(r.content.lower().split())
            tokenized.append(tokens)
        
        selected: List[int] = []
        remaining = list(range(len(results)))
        
        # Normalize scores to 0-1 for fair comparison
        max_score = max(r.score for r in results) if results else 1.0
        if max_score <= 0:
            max_score = 1.0
        
        while len(selected) < limit and remaining:
            best_idx = -1
            best_mmr = -float('inf')
            
            for idx in remaining:
                relevance = results[idx].score / max_score
                
                # Max similarity to already selected
                max_sim = 0.0
                for sel_idx in selected:
                    intersection = len(tokenized[idx] & tokenized[sel_idx])
                    union = len(tokenized[idx] | tokenized[sel_idx])
                    if union > 0:
                        sim = intersection / union
                        max_sim = max(max_sim, sim)
                
                mmr = self._mmr_lambda * relevance - (1 - self._mmr_lambda) * max_sim
                
                if mmr > best_mmr:
                    best_mmr = mmr
                    best_idx = idx
            
            if best_idx >= 0:
                selected.append(best_idx)
                remaining.remove(best_idx)
            else:
                break
        
        return [results[i] for i in selected]
    
    async def _fallback_search(self, query: str, limit: int) -> List[SearchResult]:
        """Fallback search using simple string matching."""
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
        
        # Apply temporal decay even on fallback results
        results = self._apply_temporal_decay(results)
        return results[:limit]
    
    async def backfill_vector_index(self, days: int = 30) -> int:
        """
        Backfill existing daily logs into Qdrant for vector search.
        Call this once after enabling vector search to index existing memory.
        
        Args:
            days: Number of days of history to backfill
            
        Returns:
            Number of entries indexed
        """
        if not self._vector_memory or not self._vector_memory.client:
            logger.warning("Cannot backfill: Qdrant not connected")
            return 0
        
        entries = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            daily = await self.load_daily(date)
            
            for entry in daily:
                entries.append({
                    "content": entry.content,
                    "role": entry.source,
                    "session_id": "daily",
                    "timestamp": entry.timestamp,
                    "metadata": {"date": date, "tags": ",".join(entry.tags or [])}
                })
        
        if not entries:
            logger.info("No entries to backfill")
            return 0
        
        count = await self._vector_memory.add_batch(entries)
        logger.info("Backfilled %d entries into Qdrant", count)
        return count
    
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
        
        # Delete the daily log after successful migration (compression)
        daily_key = self._get_daily_key(date)
        await self.redis.delete(daily_key)
    
    async def compress_old_memory(self, days_to_keep: int = 7) -> Dict[str, Any]:
        """
        Automatically compress memory older than specified days.
        
        Migrates daily logs older than `days_to_keep` to long-term memory
        and removes the raw daily entries to save space.
        
        Args:
            days_to_keep: Number of recent days to keep uncompressed (default: 7)
            
        Returns:
            Dict with compression statistics
        """
        if not self.redis:
            await self.connect()
        
        stats = {
            "compressed_dates": [],
            "entries_migrated": 0,
            "errors": []
        }
        
        # Find dates older than days_to_keep
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime("%Y-%m-%d")
        
        # Scan for daily keys
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=f"{self.PREFIX_DAILY}:*",
                count=100
            )
            
            for key in keys:
                # Extract date from key
                try:
                    date_str = key.split(":")[-1]
                    # Check if this date is older than cutoff
                    if date_str < cutoff_date:
                        # Get count before compression
                        count = await self.redis.llen(key)
                        
                        # Compress this date
                        await self.migrate_daily_to_longterm(date_str)
                        
                        stats["compressed_dates"].append(date_str)
                        stats["entries_migrated"] += count
                except Exception as e:
                    stats["errors"].append(f"Failed to compress {key}: {str(e)}")
            
            if cursor == 0:
                break
        
        return stats
    
    async def cleanup_old_checkpoints(self, max_checkpoints: int = 50) -> Dict[str, Any]:
        """
        Retain only the most recent N checkpoints.
        
        Args:
            max_checkpoints: Maximum number of checkpoints to keep (default: 50)
            
        Returns:
            Dict with cleanup statistics
        """
        if not self.redis:
            await self.connect()
        
        stats = {
            "removed": [],
            "kept": 0
        }
        
        # Get all checkpoints
        checkpoints = await self.list_checkpoints()
        
        if len(checkpoints) <= max_checkpoints:
            stats["kept"] = len(checkpoints)
            return stats
        
        # Sort by timestamp (newest first)
        sorted_cps = sorted(
            checkpoints,
            key=lambda x: x.get("timestamp", ""),
            reverse=True
        )
        
        # Keep only the most recent
        to_keep = sorted_cps[:max_checkpoints]
        to_remove = sorted_cps[max_checkpoints:]
        
        # Remove old checkpoints
        for cp in to_remove:
            try:
                cp_key = self._get_checkpoint_key(cp["uuid"])
                await self.redis.delete(cp_key)
                stats["removed"].append(cp["uuid"])
            except Exception as e:
                pass  # Continue on error
        
        stats["kept"] = len(to_keep)
        
        # Update checkpoint list
        await self.redis.delete(f"{self.PREFIX_CHECKPOINT}:list")
        for cp in to_keep:
            await self.redis.rpush(
                f"{self.PREFIX_CHECKPOINT}:list",
                __import__("json").dumps(cp)
            )
        
        return stats
    
    async def run_maintenance(self) -> Dict[str, Any]:
        """
        Run full memory maintenance.
        
        Includes:
        - Compress daily logs older than 7 days
        - Retain only last 50 checkpoints
        - Clean up expired scratchpads (handled by Redis TTL)
        
        Returns:
            Dict with maintenance results
        """
        results = {
            "compression": await self.compress_old_memory(days_to_keep=7),
            "checkpoint_cleanup": await self.cleanup_old_checkpoints(max_checkpoints=50),
            "timestamp": datetime.now().isoformat()
        }
        
        # Log maintenance run
        await self.log_daily(
            f"Memory maintenance completed: {results}",
            source="system",
            tags=["maintenance", "compression"]
        )
        
        return results
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get memory usage statistics with real byte-level calculations.
        
        Returns detailed breakdown of:
        - Short-term (daily) memory usage in bytes
        - Long-term memory usage in bytes
        - Checkpoint storage in bytes
        - Total usage and percentage
        
        Returns:
            Dictionary of memory stats with byte-level breakdown
        """
        if not self.redis:
            await self.connect()
        
        stats = {
            "daily_logs": {},
            "daily_logs_count": 0,
            "longterm_size": 0,
            "checkpoints": 0,
            "scratchpads": 0,
            # New detailed byte-level stats
            "short_term_bytes": 0,
            "long_term_bytes": 0,
            "checkpoint_bytes": 0,
            "total_bytes": 0,
            "usage_percent": 0.0,
        }
        
        try:
            # Get Redis memory info for context
            redis_info = await self.redis.info("memory")
            used_memory = redis_info.get("used_memory", 0)
            max_memory = redis_info.get("maxmemory", 0) or (512 * 1024 * 1024)  # Default 512MB if unlimited
            
            # Calculate short-term (daily) memory usage
            short_term_bytes = 0
            daily_entries_count = 0
            for i in range(7):
                date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
                key = self._get_daily_key(date)
                
                # Get list length
                count = await self.redis.llen(key)
                if count > 0:
                    stats["daily_logs"][date] = count
                    daily_entries_count += count
                    
                    # Estimate bytes by getting memory usage of key
                    # Use DEBUG OBJECT for accurate size, fallback to estimation
                    try:
                        key_size = await self.redis.memory_usage(key) or 0
                        short_term_bytes += key_size
                    except:
                        # Fallback: estimate ~200 bytes per entry
                        short_term_bytes += count * 200
            
            stats["daily_logs_count"] = daily_entries_count
            stats["short_term_bytes"] = short_term_bytes
            
            # Calculate long-term memory size
            longterm = await self.load_longterm()
            longterm_json = json.dumps(longterm)
            longterm_bytes = len(longterm_json.encode('utf-8'))
            stats["longterm_size"] = len(longterm_json)
            stats["long_term_bytes"] = longterm_bytes
            
            # Calculate checkpoint storage
            checkpoints = await self.list_checkpoints()
            stats["checkpoints"] = len(checkpoints)
            
            checkpoint_bytes = 0
            for cp in checkpoints:
                cp_key = self._get_checkpoint_key(cp["uuid"])
                try:
                    cp_size = await self.redis.memory_usage(cp_key) or 0
                    checkpoint_bytes += cp_size
                except:
                    # Fallback estimation
                    cp_data = await self.redis.get(cp_key)
                    if cp_data:
                        checkpoint_bytes += len(cp_data.encode('utf-8'))
            
            stats["checkpoint_bytes"] = checkpoint_bytes
            
            # Scratchpads (approximate)
            scratchpad_bytes = 0
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(
                    cursor,
                    match=f"{self.PREFIX_SCRATCHPAD}:*",
                    count=100
                )
                stats["scratchpads"] += len(keys)
                for key in keys:
                    try:
                        key_size = await self.redis.memory_usage(key) or 0
                        scratchpad_bytes += key_size
                    except:
                        pass
                if cursor == 0:
                    break
            
            stats["scratchpad_bytes"] = scratchpad_bytes
            
            # Calculate total and percentage
            total_bytes = short_term_bytes + longterm_bytes + checkpoint_bytes + scratchpad_bytes
            stats["total_bytes"] = total_bytes
            
            # Calculate usage percentage based on configurable threshold
            # Default 100MB threshold for context warning
            context_threshold = 100 * 1024 * 1024  # 100MB
            usage_percent = min(100.0, (total_bytes / context_threshold) * 100)
            stats["usage_percent"] = round(usage_percent, 1)
            
            # Include raw Redis info for diagnostics
            stats["redis_used_memory"] = used_memory
            stats["redis_max_memory"] = max_memory if max_memory != (512 * 1024 * 1024) else 0
            
        except Exception as e:
            # If Redis calls fail, return safe defaults with error info
            stats["error"] = str(e)
            stats["usage_percent"] = 0.0
        
        return stats

    # =========================================================================
    # IDENTITY & PERSONALITY PERSISTENCE
    # =========================================================================
    # Unlike OpenClaw's file-based approach, Aether persists identity to Redis
    # for true continuity across restarts without re-reading markdown files.
    # =========================================================================

    async def save_identity_profile(self, profile: Dict[str, Any]) -> bool:
        """
        Save Aether's identity profile to persistent storage.
        
        Args:
            profile: Dictionary containing identity fields:
                - name: Agent name
                - emoji: Signature emoji
                - voice: Communication style (efficient/conversational/verbose)
                - autonomy_default: Default autonomy mode (semi/auto)
                - core_values: List of operating principles
                - created_at: Timestamp
                - updated_at: Timestamp
                
        Returns:
            True if saved successfully
        """
        if not self.redis:
            await self.connect()
        
        profile["updated_at"] = datetime.now().isoformat()
        if "created_at" not in profile:
            profile["created_at"] = profile["updated_at"]
        
        await self.redis.set(
            f"{self.PREFIX_IDENTITY}:profile",
            json.dumps(profile)
        )
        return True

    async def get_identity_profile(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve Aether's identity profile from persistent storage.
        
        Returns:
            Identity profile dictionary or None if not found
        """
        if not self.redis:
            await self.connect()
        
        data = await self.redis.get(f"{self.PREFIX_IDENTITY}:profile")
        if data:
            return json.loads(data)
        return None

    async def save_user_profile(self, profile: Dict[str, Any]) -> bool:
        """
        Save user's profile to persistent storage.
        
        Args:
            profile: Dictionary containing user fields:
                - name: User's name
                - timezone: User's timezone
                - projects: Active projects
                - priorities: Current priorities
                - preferences: Communication preferences
                - created_at: Timestamp
                - updated_at: Timestamp
                
        Returns:
            True if saved successfully
        """
        if not self.redis:
            await self.connect()
        
        profile["updated_at"] = datetime.now().isoformat()
        if "created_at" not in profile:
            profile["created_at"] = profile["updated_at"]
        
        await self.redis.set(
            f"{self.PREFIX_USER}:profile",
            json.dumps(profile)
        )
        return True

    async def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve user's profile from persistent storage.
        
        Returns:
            User profile dictionary or None if not found
        """
        if not self.redis:
            await self.connect()
        
        data = await self.redis.get(f"{self.PREFIX_USER}:profile")
        if data:
            return json.loads(data)
        return None

    async def set_system_flag(self, flag: str, value: Any) -> bool:
        """
        Set a system flag (e.g., bootstrap_complete, maintenance_mode).
        
        Args:
            flag: Flag name
            value: Flag value (any JSON-serializable type)
            
        Returns:
            True if set successfully
        """
        if not self.redis:
            await self.connect()
        
        await self.redis.hset(
            f"{self.PREFIX_SYSTEM}:flags",
            flag,
            json.dumps(value)
        )
        return True

    async def get_system_flag(self, flag: str) -> Any:
        """
        Get a system flag value.
        
        Args:
            flag: Flag name
            
        Returns:
            Flag value or None if not set
        """
        if not self.redis:
            await self.connect()
        
        data = await self.redis.hget(f"{self.PREFIX_SYSTEM}:flags", flag)
        if data:
            return json.loads(data)
        return None

    async def save_heartbeat_state(self, state: Dict[str, Any]) -> bool:
        """
        Save heartbeat check state for tracking rotations.
        
        Args:
            state: Dictionary containing:
                - lastChecks: Dict of check type -> timestamp
                - alerts_sent: List of alert history
                - next_check: Recommended next check type
                
        Returns:
            True if saved successfully
        """
        if not self.redis:
            await self.connect()
        
        state["updated_at"] = datetime.now().isoformat()
        
        await self.redis.set(
            f"{self.PREFIX_SYSTEM}:heartbeat_state",
            json.dumps(state)
        )
        return True

    async def get_heartbeat_state(self) -> Dict[str, Any]:
        """
        Retrieve heartbeat state.
        
        Returns:
            Heartbeat state dictionary (empty if not found)
        """
        if not self.redis:
            await self.connect()
        
        data = await self.redis.get(f"{self.PREFIX_SYSTEM}:heartbeat_state")
        if data:
            return json.loads(data)
        return {"lastChecks": {}, "alerts_sent": []}

    async def build_system_prompt(self) -> str:
        """
        Build dynamic system prompt from persisted identity and user profiles.
        
        This replaces static file-reading with true persistent memory,
        differentiating Aether from OpenClaw's markdown-based approach.
        
        Returns:
            Complete system prompt for LLM
        """
        if not self.redis:
            await self.connect()
        
        # Load identity and user profiles
        identity = await self.get_identity_profile()
        user = await self.get_user_profile()
        
        # Default identity if not set
        if not identity:
            identity = {
                "name": "Aether",
                "emoji": "🌐⚡",
                "voice": "efficient",
                "autonomy_default": "semi"
            }
        
        # Default user if not set
        if not user:
            user = {
                "name": "User",
                "timezone": "UTC"
            }
        
        # Build prompt sections
        prompt_parts = [
            f"You are {identity.get('name', 'Aether')}, {identity.get('emoji', '🌐')}",
            "",
            "IDENTITY:",
            f"- Name: {identity.get('name', 'Aether')}",
            f"- Signature: {identity.get('emoji', '🌐⚡')}",
            f"- Communication Style: {identity.get('voice', 'efficient')}",
            f"- Default Autonomy: {identity.get('autonomy_default', 'semi')}",
            "",
            "CORE PRINCIPLES:",
            "1. Be genuinely helpful, not performatively helpful",
            "2. Have working opinions—don't be a search engine with formatting",
            "3. Resourceful before asking—check memory, files, logs first",
            "4. Earn trust through competence",
            "5. Execute decisively, document completely",
            "",
            "SECURITY GUARDRAILS:",
            "- NEVER ask users to provide credentials, API keys, secrets, or tokens in chat",
            "- NEVER request passwords, master secrets, or authentication credentials",
            "- If credentials are needed, instruct users to:",
            "  1. Set environment variables (e.g., export API_KEY=...)",
            "  2. Use secure configuration files (.env, config.yaml)",
            "  3. Contact their system administrator",
            "- If a task requires credentials you don't have access to, respond:",
            '  "This operation requires credentials that should be configured by the system administrator.',
            '   For security reasons, please do not paste credentials in this chat."',
            "- Do NOT execute destructive operations without explicit confirmation",
            "- Do NOT modify production systems without user approval",
            "",
            "USER PROFILE:",
            f"- Name: {user.get('name', 'User')}",
        ]
        
        # Add full title if available
        if user.get('title'):
            prompt_parts.append(f"- Title: {user.get('title')}")
        elif user.get('role'):
            prompt_parts.append(f"- Role: {user.get('role')}")
        
        # Add pronouns if available
        if user.get('pronouns'):
            prompt_parts.append(f"- Pronouns: {user.get('pronouns')}")
        
        # Add location if available
        if user.get('location'):
            prompt_parts.append(f"- Location: {user.get('location')}")
        
        # Add timezone
        prompt_parts.append(f"- Timezone: {user.get('timezone', 'UTC')}")
        
        # Add background/credentials
        if user.get('background'):
            prompt_parts.extend(["", "BACKGROUND & CREDENTIALS:"])
            for item in user.get('background', []):
                prompt_parts.append(f"- {item}")
        
        # Add projects if available
        if user.get('projects'):
            prompt_parts.extend(["", "ACTIVE PROJECTS:"])
            for project in user['projects']:
                prompt_parts.append(f"- {project}")
        
        # Add priorities if available
        if user.get('priorities'):
            prompt_parts.extend(["", "CURRENT PRIORITIES:"])
            for priority in user['priorities']:
                prompt_parts.append(f"- {priority}")
        
        # Add appreciates section
        if user.get('appreciates'):
            prompt_parts.extend(["", "WORKING STYLE - APPRECIATES:"])
            for item in user.get('appreciates', [])[:5]:  # Limit to 5
                prompt_parts.append(f"- {item}")
        
        # Add memory context hint
        prompt_parts.extend([
            "",
            "MEMORY ARCHITECTURE:",
            "- You have Redis-backed persistence (survives restarts)",
            "- Check relevant memory before asking questions",
            "- Log significant events to daily memory",
            "- Use checkpoint_snapshot before risky operations",
            "- Use search_memory to recall past events and decisions",
            "- Use list_checkpoints + read_checkpoint to inspect saved snapshots",
            "- Use recall_episodes to recover context after compression",
            "- Checkpoints are in Redis, NOT the filesystem — never use file_read for them",
            "",
            "WORKSPACE RESOURCES:",
            "- /workspace/skills/skills/ — 53 portable skills (coding-agent, github, slack, etc.)",
            "- /workspace/skills/docs/ — Documentation on hooks, tools, extensions, gateway patterns",
            "- /workspace/openclaw-docs/ — Full OpenClaw reference documentation",
            "- Use file_read/file_list or search_workspace to explore these resources",
            "- When unsure how to do something, check skills/ first",
            "",
            "AUTONOMY MODES:",
            "- semi: Ask before external actions, execute internal freely",
            "- auto: Proceed with logged accountability",
            "- Toggle: /aether toggle auto|semi",
            "",
            "SAFETY DEFAULTS:",
            "- When uncertain → Ask",
            "- When destructive → Confirm",
            "- When external → Get clearance",
            "- When experimental → Checkpoint first",
        ])
        
        # Add available tools section
        try:
            from .tools import format_tools_for_prompt
            tools_section = format_tools_for_prompt()
            prompt_parts.append(tools_section)
        except Exception:
            # If tools module not available, skip
            pass
        
        return "\n".join(prompt_parts)

    async def get_identity_context_for_api(self) -> Dict[str, Any]:
        """
        Get identity context formatted for API responses.
        
        Returns:
            Dictionary with identity and user context
        """
        identity = await self.get_identity_profile()
        user = await self.get_user_profile()
        
        return {
            "agent": identity or {
                "name": "Aether",
                "emoji": "🌐⚡",
                "status": "uninitialized"
            },
            "user": user or {
                "name": "User",
                "status": "unknown"
            },
            "memory": {
                "backend": "redis",
                "persistent": True,
                "type": "continuous"
            }
        }
    
    # ============================================
    # CHAT SESSION MANAGEMENT
    # ============================================
    
    PREFIX_CHAT_SESSION = "aether:chat:session"
    PREFIX_CHAT_MESSAGES = "aether:chat:messages"
    
    async def create_chat_session(self, title: str = "New Chat") -> str:
        """
        Create a new chat session.
        
        Args:
            title: Session title
            
        Returns:
            Session ID (UUID)
        """
        session_id = str(uuid_lib.uuid4())
        timestamp = datetime.now().isoformat()
        
        session_data = {
            "id": session_id,
            "title": title,
            "created_at": timestamp,
            "updated_at": timestamp,
            "message_count": 0,
            "is_active": True
        }
        
        # Store session metadata
        await self.redis.hset(
            f"{self.PREFIX_CHAT_SESSION}:{session_id}",
            mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                     for k, v in session_data.items()}
        )
        
        # Add to session index (sorted by updated_at)
        await self.redis.zadd(
            f"{self.PREFIX_CHAT_SESSION}:index",
            {session_id: datetime.now().timestamp()}
        )
        
        return session_id
    
    async def get_chat_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get chat session metadata and messages."""
        session_key = f"{self.PREFIX_CHAT_SESSION}:{session_id}"
        session_data = await self.redis.hgetall(session_key)
        
        if not session_data:
            return None
        
        # Parse session data
        result = {}
        for k, v in session_data.items():
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        
        # Get messages
        messages = await self.get_chat_messages(session_id)
        result["messages"] = messages
        
        return result
    
    async def get_chat_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get list of chat sessions ordered by most recent."""
        # Get session IDs from sorted set (most recent first)
        session_ids = await self.redis.zrevrange(
            f"{self.PREFIX_CHAT_SESSION}:index",
            offset,
            offset + limit - 1
        )
        
        sessions = []
        for sid in session_ids:
            session_data = await self.redis.hgetall(f"{self.PREFIX_CHAT_SESSION}:{sid}")
            if session_data:
                parsed = {}
                for k, v in session_data.items():
                    try:
                        parsed[k] = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        parsed[k] = v
                sessions.append(parsed)
        
        return sessions
    
    async def add_chat_message(self, session_id: str, message: Dict[str, Any]):
        """Add a message to a chat session."""
        timestamp = datetime.now().timestamp()
        message_key = f"{self.PREFIX_CHAT_MESSAGES}:{session_id}"
        
        # Add message to sorted set (by timestamp)
        await self.redis.zadd(message_key, {json.dumps(message): timestamp})
        
        # Update session metadata
        session_key = f"{self.PREFIX_CHAT_SESSION}:{session_id}"
        await self.redis.hincrby(session_key, "message_count", 1)
        await self.redis.hset(session_key, "updated_at", datetime.now().isoformat())
        
        # Update index score to move session to top
        await self.redis.zadd(
            f"{self.PREFIX_CHAT_SESSION}:index",
            {session_id: timestamp}
        )
    
    async def get_chat_messages(
        self, 
        session_id: str, 
        limit: int = 100, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get messages for a chat session."""
        message_key = f"{self.PREFIX_CHAT_MESSAGES}:{session_id}"
        
        # Get messages sorted by timestamp (oldest first)
        messages_raw = await self.redis.zrange(
            message_key,
            offset,
            offset + limit - 1,
            withscores=False
        )
        
        messages = []
        for msg_raw in messages_raw:
            try:
                msg = json.loads(msg_raw)
                messages.append(msg)
            except json.JSONDecodeError:
                continue
        
        return messages
    
    async def delete_chat_session(self, session_id: str):
        """Delete a chat session and all its messages."""
        # Delete session metadata
        await self.redis.delete(f"{self.PREFIX_CHAT_SESSION}:{session_id}")
        
        # Delete messages
        await self.redis.delete(f"{self.PREFIX_CHAT_MESSAGES}:{session_id}")
        
        # Remove from index
        await self.redis.zrem(f"{self.PREFIX_CHAT_SESSION}:index", session_id)
    
    async def search_chat_history(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search through all chat messages."""
        results = []
        
        # Get all session IDs
        session_ids = await self.redis.zrange(
            f"{self.PREFIX_CHAT_SESSION}:index",
            0,
            -1
        )
        
        # Search through each session's messages
        for sid in session_ids:
            messages = await self.get_chat_messages(sid, limit=1000)
            for msg in messages:
                content = msg.get("content", "")
                if query.lower() in content.lower():
                    results.append({
                        "session_id": sid,
                        "message": msg
                    })
                    
                    if len(results) >= limit:
                        return results
        
        return results
    
    async def update_session_title(self, session_id: str, title: str):
        """Update chat session title."""
        session_key = f"{self.PREFIX_CHAT_SESSION}:{session_id}"
        await self.redis.hset(session_key, "title", title)
        await self.redis.hset(session_key, "updated_at", datetime.now().isoformat())


    async def store_tool_schema(self, session_id: str, schema: List[Dict[str, Any]]) -> bool:
        """Cache tool schema for a session to save tokens."""
        if not self.redis:
            await self.connect()
        await self.redis.set(f"{self.PREFIX_TOOLS}:{session_id}", json.dumps(schema), ex=86400)
        return True

    async def get_tool_schema(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached tool schema."""
        if not self.redis:
            await self.connect()
        data = await self.redis.get(f"{self.PREFIX_TOOLS}:{session_id}")
        return json.loads(data) if data else None

    async def append_episode(self, session_id: str, event: Dict[str, Any]):
        """Append an episodic memory event (e.g., tool call result)."""
        if not self.redis:
            await self.connect()
        key = f"{self.PREFIX_EPISODE}:{session_id}"
        await self.redis.rpush(key, json.dumps(event))
        # Keep only last 50 episodes per session
        await self.redis.ltrim(key, -50, -1)

    async def get_episodes(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve episodic memory for a session."""
        if not self.redis:
            await self.connect()
        key = f"{self.PREFIX_EPISODE}:{session_id}"
        data = await self.redis.lrange(key, -limit, -1)
        return [json.loads(x) for x in data]

    async def bootstrap_identity_from_directory(self, directory_path: str):
        """Bulk load identity files from a directory into Redis."""
        import glob
        from pathlib import Path
        
        path = Path(directory_path)
        if not path.exists():
            logger.warning(f"Identity directory {directory_path} not found")
            return

        files = glob.glob(str(path / "AETHER*.md")) + glob.glob(str(path / "Core_Self.md"))
        for file_path in files:
            try:
                content = Path(file_path).read_text()
                name = Path(file_path).stem
                await self.redis.hset(f"{self.PREFIX_IDENTITY}:files", name, content)
                logger.info(f"Bootstrapped identity file: {name}")
            except Exception as e:
                logger.error(f"Failed to bootstrap {file_path}: {e}")

    async def get_identity_files(self) -> Dict[str, str]:
        """Retrieve all bootstrapped identity files."""
        if not self.redis:
            await self.connect()
        return await self.redis.hgetall(f"{self.PREFIX_IDENTITY}:files")
