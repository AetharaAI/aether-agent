import os
import logging
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

try:
    from qdrant_client import QdrantClient, models
except ImportError:
    QdrantClient = None
    models = None

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
    Uses 'fastembed' for local embedding generation to keep data sovereign.
    """
    
    COLLECTION_NAME = "aether_memory"
    # standard dimension for fastembed's default model (sentence-transformers/all-MiniLM-L6-v2) is 384
    # if using OpenAI, it would be 1536. FastEmbed handles this automatically.
    
    def __init__(self):
        self.url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.api_key = os.getenv("QDRANT_API_KEY", None)
        self.client: Optional[QdrantClient] = None
        
    async def connect(self):
        """Initialize Qdrant client and ensure collection exists."""
        if not QdrantClient:
            logger.warning("QdrantClient not installed. functionality disabled.")
            return

        try:
            # fastembed is enabled by default in QdrantClient when adding documents
            self.client = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                # optimizations for cloud/remote
                prefer_grpc=os.getenv("QDRANT_GRPC_ENABLED", "false").lower() == "true"
            )
            
            # Check if collection exists
            if not self.client.collection_exists(self.COLLECTION_NAME):
                logger.info(f"Creating Qdrant collection: {self.COLLECTION_NAME}")
                # We let FastEmbed determine vector size implicitly or specify "fastembed"
                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=self.client.get_fastembed_vector_params()
                )
                
            logger.info(f"Connected to Qdrant at {self.url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            self.client = None

    async def add(
        self, 
        content: str, 
        role: str, 
        session_id: str, 
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Add a text entry to vector memory. 
        Embeddings are generated locally via FastEmbed.
        """
        if not self.client:
            return ""

        entry_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        payload = {
            "content": content,
            "role": role,
            "timestamp": timestamp,
            "session_id": session_id,
            **(metadata or {})
        }
        
        try:
            # Qdrant's add method with fastembed support handles embedding generation automatically
            self.client.add(
                collection_name=self.COLLECTION_NAME,
                documents=[content],
                metadata=[payload],
                ids=[entry_id]
            )
            return entry_id
        except Exception as e:
            logger.error(f"Failed to add to Qdrant: {e}")
            return ""

    async def search(
        self, 
        query: str, 
        limit: int = 5, 
        session_id: Optional[str] = None
    ) -> List[VectorMemoryEntry]:
        """
        Semantic search for memory entries.
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

            # Search properly generates query embedding via fastembed
            results = self.client.query(
                collection_name=self.COLLECTION_NAME,
                query_text=query,
                limit=limit,
                query_filter=query_filter
            )
            
            memory_entries = []
            for hit in results:
                payload = hit.metadata
                memory_entries.append(VectorMemoryEntry(
                    id=hit.id,
                    content=payload.get("content", ""),
                    role=payload.get("role", "unknown"),
                    timestamp=payload.get("timestamp", ""),
                    session_id=payload.get("session_id", ""),
                    metadata=payload,
                    score=hit.score
                ))
                
            return memory_entries
            
        except Exception as e:
            logger.error(f"Failed to search Qdrant: {e}")
            return []

    async def close(self):
        """Cleanup resources."""
        # QdrantClient (sync wrapper) manages its own connection pool usually
        self.client = None
