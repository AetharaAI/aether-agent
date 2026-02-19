"""
aether/qdrant_adapter.py
Vector memory adapter for Aether using Qdrant.

Supports two embedding modes:
1. Local FastEmbed (default, zero-dependency)
2. External TEI/OpenAI-compatible endpoint (for bge-m3 on L4 GPU cluster)

Set EMBEDDING_API_URL to switch to external mode:
    EMBEDDING_API_URL=http://your-l4-node:8080/v1/embeddings
    EMBEDDING_MODEL=BAAI/bge-m3
    EMBEDDING_DIMS=1024
"""

import os
import logging
import uuid
import json
import math
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    from qdrant_client import QdrantClient, models
except ImportError:
    QdrantClient = None
    models = None

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger("aether.qdrant")


@dataclass
class VectorMemoryEntry:
    id: str
    content: str
    role: str
    timestamp: str
    session_id: str
    metadata: Dict[str, Any]
    score: float = 0.0


class QdrantMemory:
    """
    Vector memory adapter for Aether using Qdrant.
    
    Supports:
    - Local FastEmbed (all-MiniLM-L6-v2, 384-dim) for zero-config
    - External embedding endpoint (bge-m3 via TEI, 1024-dim) for production
    - Batch indexing for backfilling existing memory
    - Session filtering
    - Score normalization (0-1 cosine similarity)
    """
    
    COLLECTION_NAME = "aether_memory"
    
    def __init__(self):
        self.url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.api_key = os.getenv("QDRANT_API_KEY", None)
        self.client: Optional[QdrantClient] = None
        
        # External embedding config
        self.embedding_api_url = os.getenv("EMBEDDING_API_URL", "")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        self.embedding_dims = int(os.getenv("EMBEDDING_DIMS", "1024"))
        self.use_external_embeddings = bool(self.embedding_api_url)
        
        # Reranker config
        self.reranker_api_url = os.getenv("RERANKER_API_URL", "")
        self.use_reranker = bool(self.reranker_api_url)
        
        self._http_client: Optional[Any] = None
        
    async def connect(self):
        """Initialize Qdrant client and ensure collection exists."""
        if not QdrantClient:
            logger.warning("qdrant-client not installed. Vector memory disabled.")
            return

        try:
            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                prefer_grpc=os.getenv("QDRANT_GRPC_ENABLED", "false").lower() == "true"
            )
            
            # Determine vector size
            if self.use_external_embeddings:
                vector_size = self.embedding_dims
                logger.info(
                    "Using external embeddings: %s (%d dims) at %s",
                    self.embedding_model, vector_size, self.embedding_api_url
                )
            else:
                # FastEmbed default: all-MiniLM-L6-v2 = 384 dims
                vector_size = 384
                logger.info("Using local FastEmbed (all-MiniLM-L6-v2, 384 dims)")
            
            # Create or verify collection (handle config mismatch from previous runs)
            needs_create = False
            
            if self.client.collection_exists(self.COLLECTION_NAME):
                # Check if existing collection matches our expected config
                try:
                    info = self.client.get_collection(self.COLLECTION_NAME)
                    existing_config = info.config.params.vectors
                    
                    # If using external embeddings, we need unnamed vectors with correct size
                    if self.use_external_embeddings:
                        if isinstance(existing_config, dict):
                            # Collection has named vectors (FastEmbed) — mismatch
                            logger.warning(
                                "Collection '%s' has named vectors (FastEmbed config) but external "
                                "embeddings are configured. Recreating with %d-dim unnamed vectors.",
                                self.COLLECTION_NAME, vector_size
                            )
                            self.client.delete_collection(self.COLLECTION_NAME)
                            needs_create = True
                        elif hasattr(existing_config, 'size') and existing_config.size != vector_size:
                            # Wrong vector size
                            logger.warning(
                                "Collection '%s' has %d-dim vectors but %d expected. Recreating.",
                                self.COLLECTION_NAME, existing_config.size, vector_size
                            )
                            self.client.delete_collection(self.COLLECTION_NAME)
                            needs_create = True
                except Exception as e:
                    logger.debug("Could not verify collection config: %s", e)
            else:
                needs_create = True
            
            if needs_create:
                logger.info("Creating Qdrant collection: %s (%d dims)", self.COLLECTION_NAME, vector_size)
                
                if self.use_external_embeddings:
                    self.client.create_collection(
                        collection_name=self.COLLECTION_NAME,
                        vectors_config=models.VectorParams(
                            size=vector_size,
                            distance=models.Distance.COSINE
                        )
                    )
                else:
                    self.client.create_collection(
                        collection_name=self.COLLECTION_NAME,
                        vectors_config=self.client.get_fastembed_vector_params()
                    )
            
            # Init HTTP client for external embeddings and reranker
            if (self.use_external_embeddings or self.use_reranker) and httpx:
                self._http_client = httpx.AsyncClient(timeout=30.0)
                    
            logger.info("Connected to Qdrant at %s", self.url)
            
        except Exception as e:
            logger.error("Failed to connect to Qdrant: %s", e)
            self.client = None

    async def _get_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Get embeddings from external TEI/OpenAI-compatible endpoint.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors, or None on failure
        """
        if not self._http_client or not self.embedding_api_url:
            return None
        
        try:
            response = await self._http_client.post(
                self.embedding_api_url,
                json={
                    "input": texts,
                    "model": self.embedding_model
                },
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            data = response.json()
            # OpenAI-compatible response format
            embeddings = [item["embedding"] for item in data["data"]]
            return embeddings
            
        except Exception as e:
            logger.error("External embedding failed: %s", e)
            return None

    async def add(
        self, 
        content: str, 
        role: str, 
        session_id: str, 
        metadata: Dict[str, Any] = None,
        timestamp: Optional[str] = None
    ) -> str:
        """
        Add a text entry to vector memory. 
        Uses external embeddings if configured, otherwise FastEmbed.
        """
        if not self.client:
            return ""

        entry_id = str(uuid.uuid4())
        ts = timestamp or datetime.now().isoformat()
        
        payload = {
            "content": content,
            "role": role,
            "timestamp": ts,
            "session_id": session_id,
            **(metadata or {})
        }
        
        try:
            if self.use_external_embeddings:
                # Use external embedding endpoint
                embeddings = await self._get_embeddings([content])
                if not embeddings:
                    logger.warning("External embedding failed, skipping vector indexing")
                    return ""
                
                self.client.upsert(
                    collection_name=self.COLLECTION_NAME,
                    points=[
                        models.PointStruct(
                            id=entry_id,
                            vector=embeddings[0],
                            payload=payload
                        )
                    ]
                )
            else:
                # Use FastEmbed (local)
                self.client.add(
                    collection_name=self.COLLECTION_NAME,
                    documents=[content],
                    metadata=[payload],
                    ids=[entry_id]
                )
            return entry_id
            
        except Exception as e:
            logger.error("Failed to add to Qdrant: %s", e)
            return ""

    async def add_batch(
        self,
        entries: List[Dict[str, Any]],
        batch_size: int = 64
    ) -> int:
        """
        Batch-add entries to vector memory.
        
        Args:
            entries: List of dicts with keys: content, role, session_id, metadata, timestamp
            batch_size: Number of entries per embedding API call
            
        Returns:
            Number of entries successfully indexed
        """
        if not self.client:
            return 0
        
        indexed = 0
        
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]
            texts = [e["content"] for e in batch]
            
            try:
                if self.use_external_embeddings:
                    embeddings = await self._get_embeddings(texts)
                    if not embeddings:
                        continue
                    
                    points = []
                    for j, entry in enumerate(batch):
                        entry_id = str(uuid.uuid4())
                        payload = {
                            "content": entry["content"],
                            "role": entry.get("role", "system"),
                            "timestamp": entry.get("timestamp", datetime.now().isoformat()),
                            "session_id": entry.get("session_id", "backfill"),
                            **(entry.get("metadata") or {})
                        }
                        points.append(
                            models.PointStruct(
                                id=entry_id,
                                vector=embeddings[j],
                                payload=payload
                            )
                        )
                    
                    self.client.upsert(
                        collection_name=self.COLLECTION_NAME,
                        points=points
                    )
                    indexed += len(batch)
                else:
                    # FastEmbed batch
                    for entry in batch:
                        await self.add(
                            content=entry["content"],
                            role=entry.get("role", "system"),
                            session_id=entry.get("session_id", "backfill"),
                            metadata=entry.get("metadata"),
                            timestamp=entry.get("timestamp")
                        )
                        indexed += 1
                        
            except Exception as e:
                logger.error("Batch indexing error at offset %d: %s", i, e)
                continue
        
        logger.info("Batch indexed %d / %d entries", indexed, len(entries))
        return indexed

    async def search(
        self, 
        query: str, 
        limit: int = 5, 
        session_id: Optional[str] = None
    ) -> List[VectorMemoryEntry]:
        """
        Semantic search for memory entries.
        Returns results with cosine similarity scores (0-1).
        """
        if not self.client:
            return []

        try:
            # Build filter if session_id provided
            query_filter = None
            if session_id:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="session_id",
                            match=models.MatchValue(value=session_id)
                        )
                    ]
                )

            if self.use_external_embeddings:
                # Get query embedding from external endpoint
                embeddings = await self._get_embeddings([query])
                if not embeddings:
                    return []
                
                results = self.client.search(
                    collection_name=self.COLLECTION_NAME,
                    query_vector=embeddings[0],
                    limit=limit,
                    query_filter=query_filter
                )
                
                memory_entries = []
                for hit in results:
                    payload = hit.payload or {}
                    memory_entries.append(VectorMemoryEntry(
                        id=str(hit.id),
                        content=payload.get("content", ""),
                        role=payload.get("role", "unknown"),
                        timestamp=payload.get("timestamp", ""),
                        session_id=payload.get("session_id", ""),
                        metadata=payload,
                        score=hit.score  # cosine similarity, 0-1
                    ))
                return memory_entries
            else:
                # FastEmbed search
                results = self.client.query(
                    collection_name=self.COLLECTION_NAME,
                    query_text=query,
                    limit=limit,
                    query_filter=query_filter
                )
                
                memory_entries = []
                for hit in results:
                    payload = hit.metadata if hasattr(hit, 'metadata') else {}
                    memory_entries.append(VectorMemoryEntry(
                        id=str(hit.id),
                        content=payload.get("content", ""),
                        role=payload.get("role", "unknown"),
                        timestamp=payload.get("timestamp", ""),
                        session_id=payload.get("session_id", ""),
                        metadata=payload,
                        score=hit.score if hasattr(hit, 'score') else 0.0
                    ))
                    
                return memory_entries
            
        except Exception as e:
            logger.error("Failed to search Qdrant: %s", e)
            return []

    async def delete_by_session(self, session_id: str) -> bool:
        """Delete all entries for a given session."""
        if not self.client:
            return False
        
        try:
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="session_id",
                                match=models.MatchValue(value=session_id)
                            )
                        ]
                    )
                )
            )
            return True
        except Exception as e:
            logger.error("Failed to delete by session: %s", e)
            return False

    async def get_collection_info(self) -> Dict[str, Any]:
        """Get collection statistics."""
        if not self.client:
            return {"status": "disconnected"}
        
        try:
            info = self.client.get_collection(self.COLLECTION_NAME)
            return {
                "status": "connected",
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "segments_count": info.segments_count,
                "embedding_mode": "external" if self.use_external_embeddings else "local",
                "embedding_model": self.embedding_model if self.use_external_embeddings else "all-MiniLM-L6-v2",
                "vector_dims": self.embedding_dims if self.use_external_embeddings else 384
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Re-rank documents using cross-encoder reranker (bge-reranker-v2-m3).
        
        Args:
            query: The search query
            documents: List of document texts to re-rank
            top_n: Max results to return (default: all)
            
        Returns:
            List of {"index": int, "score": float} sorted by relevance,
            or None if reranker unavailable/failed
        """
        if not self._http_client or not self.reranker_api_url:
            return None
        
        if not documents:
            return []
        
        try:
            payload = {
                "query": query,
                "texts": documents,
            }
            if top_n:
                payload["top_n"] = top_n
            
            response = await self._http_client.post(
                self.reranker_api_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            data = response.json()
            # TEI rerank response: [{"index": 0, "score": 0.95}, ...]
            # Already sorted by score descending
            return data
            
        except Exception as e:
            logger.warning("Reranker failed (non-fatal): %s", e)
            return None

    async def close(self):
        """Cleanup resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self.client = None
