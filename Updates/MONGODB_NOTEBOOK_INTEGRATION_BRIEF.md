# MongoDB "Agent Notebook" Integration Brief

## For: IDE Claude (Claude Code / Cursor / etc.)
## Project: AetherOS — Hybrid Memory Architecture Upgrade
## Author: Cory (CEO, AetherPro Technologies) via Claude Opus
## Date: February 16, 2026

---

## 1. CONTEXT — What Already Exists

AetherOS agents currently use **Redis Stack** as their sole memory layer. The existing `aether/aether_memory.py` module manages three logical tiers in Redis:

### A. Stream of Consciousness (Daily Memory)
- **Key pattern:** `aether:daily:YYYY-MM-DD`
- **Data structures:** Redis List (chronological timeline) + Redis Hash (searchable fields)
- **Behavior:** Every message, thought, or tool output is pushed to the List for recency AND saved as a Hash with fields (`content`, `source`, `tags`, `score`) for search.

### B. Search Engine (RediSearch)
- **Index name:** `aether:memory:idx`
- **Feature:** `FT.SEARCH` full-text search over the Hashes
- **Behavior:** Agents recall relevant memories via text matching and score-based retrieval rather than scanning the full history.

### C. Time Travel (Checkpoints)
- **Key pattern:** `aether:checkpoint:<UUID>`
- **Data structure:** JSON blob (full state snapshot)
- **Behavior:** `checkpoint_snapshot()` dumps the entire memory state (daily logs + long-term summary) into a single JSON blob. Enables instant rollback to undo erratic agent behavior.

### What's NOT Changing
Redis remains the **hot memory and state engine**. Nothing about the existing Redis architecture changes. MongoDB is being added as a new, complementary layer.

---

## 2. THE PROBLEM — Why Redis Alone Isn't Enough

Redis is optimized for "What was I just thinking?" and "What happened 5 minutes ago?" It is **not** optimized for:

- **Large documents** — Storing multi-page reports in Redis bloats RAM (everything is in-memory)
- **Structured editing** — Updating a middle paragraph of a Redis string is complex and inefficient
- **Persistent artifacts** — Work products (proposals, research notes, code drafts) need durable, queryable storage that doesn't compete with the agent's working memory for RAM

---

## 3. THE SOLUTION — MongoDB as the "Agent Notebook"

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT COGNITIVE LOOP                       │
│                                                               │
│   ┌──────────────────┐          ┌──────────────────────┐     │
│   │   REDIS STACK     │          │   MONGODB              │     │
│   │   "Hot Memory"    │          │   "Notebook"           │     │
│   │                   │          │                        │     │
│   │  • Stream of      │  ref     │  • Full documents      │     │
│   │    consciousness  │◄────────►│  • Research notes      │     │
│   │  • Search index   │  title/  │  • Code snippets       │     │
│   │  • Checkpoints    │  summary │  • Proposals/reports   │     │
│   │  • Agent state    │  only    │  • Structured artifacts │     │
│   │                   │          │                        │     │
│   │  Speed: <1ms      │          │  Speed: 1-10ms         │     │
│   │  Storage: RAM     │          │  Storage: Disk (SSD)   │     │
│   └──────────────────┘          └──────────────────────────┘     │
│                                                               │
│   THE RULE: Redis holds titles/summaries/refs.               │
│             MongoDB holds the full content.                   │
│             LLM context window only gets summaries            │
│             unless the agent explicitly "opens" a notebook.   │
└─────────────────────────────────────────────────────────────┘
```

### The Reference Pattern (Critical Design Rule)

When an agent is working on a document:

1. **Redis stores a lightweight reference:**
   ```json
   {
     "type": "notebook_ref",
     "notebook_id": "proposal_abc123",
     "title": "Generic Agent Proposal v2",
     "summary": "Draft proposal for autonomous agent deployment framework",
     "collection": "pages",
     "updated_at": "2026-02-16T10:30:00Z",
     "status": "in_progress"
   }
   ```

2. **MongoDB stores the actual content:**
   ```json
   {
     "_id": "proposal_abc123",
     "title": "Generic Agent Proposal v2",
     "collection_type": "pages",
     "content": "## Executive Summary\n\nThis proposal outlines...",
     "metadata": {
       "created_by": "agent:percy",
       "created_at": "2026-02-15T08:00:00Z",
       "updated_at": "2026-02-16T10:30:00Z",
       "version": 3,
       "tags": ["proposal", "agents", "infrastructure"],
       "word_count": 2450
     },
     "sections": [
       { "heading": "Executive Summary", "content": "..." },
       { "heading": "Technical Architecture", "content": "..." }
     ],
     "history": [
       { "version": 1, "timestamp": "...", "summary": "Initial draft" },
       { "version": 2, "timestamp": "...", "summary": "Added technical section" }
     ]
   }
   ```

3. **The LLM context window only receives the title/summary from Redis** — preventing context overflow. The agent "opens" a notebook page (fetches from Mongo) only when it specifically needs to read or edit the full content.

---

## 4. IMPLEMENTATION PLAN

### 4.1 MongoDB Connection Setup

**Connection info:**
- MongoDB is running on Cory's R64 memory node (64GB RAM server)
- Default port: `27017`
- Database name: `aether_notebook`

**Required dependency:**
```bash
pip install motor  # Async MongoDB driver for Python (works with asyncio)
```

> **IMPORTANT:** Use `motor` (async), NOT `pymongo` (sync). AetherOS is async-first (FastAPI + asyncio). Motor wraps PyMongo with async/await support.

**Create:** `aether/notebook/connection.py`
```python
"""
MongoDB connection manager for AetherOS Agent Notebook.
Uses Motor (async MongoDB driver) to match AetherOS's async architecture.
"""
import os
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional

class NotebookDB:
    _client: Optional[AsyncIOMotorClient] = None
    _db = None

    @classmethod
    async def connect(cls):
        """Initialize MongoDB connection. Call once at app startup."""
        mongo_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        cls._client = AsyncIOMotorClient(mongo_url)
        cls._db = cls._client["aether_notebook"]
        
        # Create indexes for fast lookups
        await cls._db.pages.create_index("metadata.created_by")
        await cls._db.pages.create_index("metadata.tags")
        await cls._db.pages.create_index([("metadata.updated_at", -1)])
        await cls._db.pages.create_index([("title", "text"), ("content", "text")])
        
        await cls._db.code_snippets.create_index("metadata.language")
        await cls._db.code_snippets.create_index("metadata.created_by")
        
        await cls._db.research_notes.create_index("metadata.source_url")
        await cls._db.research_notes.create_index("metadata.created_by")
        
        return cls._db

    @classmethod
    def get_db(cls):
        """Get the database instance. Raises if not connected."""
        if cls._db is None:
            raise RuntimeError("NotebookDB not connected. Call await NotebookDB.connect() first.")
        return cls._db

    @classmethod
    async def disconnect(cls):
        """Clean shutdown."""
        if cls._client:
            cls._client.close()
```

### 4.2 MongoDB Collections (Schema Design)

Use **three collections** to start. MongoDB is schemaless, so these can evolve, but starting with clear structure prevents chaos.

**Collection: `pages`** — Long-form documents (proposals, reports, plans)
```python
# Document schema
{
    "_id": str,              # Unique ID (use uuid4 or slugified title)
    "title": str,            # Human-readable title
    "content": str,          # Full markdown/text content
    "summary": str,          # Auto-generated or agent-written summary (max ~200 chars)
    "sections": [            # Optional structured sections for large docs
        {"heading": str, "content": str}
    ],
    "metadata": {
        "created_by": str,   # Agent ID (e.g., "agent:percy", "agent:maestro")
        "created_at": datetime,
        "updated_at": datetime,
        "version": int,
        "tags": [str],
        "word_count": int,
        "status": str        # "draft", "in_progress", "complete", "archived"
    },
    "history": [             # Version breadcrumbs (not full content — just summaries)
        {"version": int, "timestamp": datetime, "summary": str, "changed_by": str}
    ]
}
```

**Collection: `code_snippets`** — Code the agent writes, reviews, or references
```python
{
    "_id": str,
    "title": str,            # e.g., "FastAPI WebSocket handler"
    "code": str,             # The actual code
    "language": str,         # "python", "javascript", "bash", etc.
    "description": str,      # What this code does
    "metadata": {
        "created_by": str,
        "created_at": datetime,
        "updated_at": datetime,
        "tags": [str],
        "related_page": str  # Optional link to a pages doc
    }
}
```

**Collection: `research_notes`** — Web research, findings, references
```python
{
    "_id": str,
    "title": str,
    "content": str,          # The research content/notes
    "source_url": str,       # Where it came from (optional)
    "key_findings": [str],   # Bullet-point findings for quick summary
    "metadata": {
        "created_by": str,
        "created_at": datetime,
        "updated_at": datetime,
        "tags": [str],
        "confidence": float, # 0.0-1.0 how confident the agent is in this info
        "related_pages": [str]
    }
}
```

### 4.3 The NotebookTool — Agent-Facing Interface

This is the core tool that agents use to interact with their notebook. It should be registered as a tool in whatever tool system AetherOS uses.

**Create:** `aether/notebook/tool.py`
```python
"""
NotebookTool — The agent's interface to MongoDB persistent storage.

This tool gives agents the ability to:
  - Create new notebook pages, code snippets, and research notes
  - Read/open existing entries
  - Update/edit entries
  - Search across all notebooks
  - List recent entries
  - Delete entries

DESIGN PRINCIPLE: Every write to MongoDB should also push a lightweight
reference to Redis so the agent's stream of consciousness stays aware
of what's in the notebook without loading full content into context.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from aether.notebook.connection import NotebookDB


class NotebookTool:
    """Agent tool for persistent notebook operations backed by MongoDB."""

    VALID_COLLECTIONS = ["pages", "code_snippets", "research_notes"]

    def __init__(self, agent_id: str, redis_client=None):
        """
        Args:
            agent_id: The ID of the agent using this tool (e.g., "percy", "maestro")
            redis_client: The existing Redis client for pushing references
        """
        self.agent_id = f"agent:{agent_id}"
        self.redis = redis_client
        self.db = NotebookDB.get_db()

    # ─── TOOL DEFINITIONS (for LLM tool calling) ────────────────────────
    
    @staticmethod
    def get_tool_definitions() -> List[Dict]:
        """Return tool definitions for LLM function calling."""
        return [
            {
                "name": "notebook_create",
                "description": "Create a new notebook entry (page, code snippet, or research note). Use for storing documents, code, or research that the agent is working on.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "collection": {
                            "type": "string",
                            "enum": ["pages", "code_snippets", "research_notes"],
                            "description": "Type of notebook entry"
                        },
                        "title": {
                            "type": "string",
                            "description": "Title of the entry"
                        },
                        "content": {
                            "type": "string",
                            "description": "Full content (markdown for pages, code for snippets, notes for research)"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Tags for categorization"
                        },
                        "summary": {
                            "type": "string",
                            "description": "Brief summary (auto-generated if not provided)"
                        }
                    },
                    "required": ["collection", "title", "content"]
                }
            },
            {
                "name": "notebook_read",
                "description": "Read/open a notebook entry by ID. Returns the full content. Use when the agent needs to review or reference a specific document.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "notebook_id": {
                            "type": "string",
                            "description": "The ID of the notebook entry to read"
                        },
                        "collection": {
                            "type": "string",
                            "enum": ["pages", "code_snippets", "research_notes"],
                            "description": "Which collection to look in"
                        }
                    },
                    "required": ["notebook_id", "collection"]
                }
            },
            {
                "name": "notebook_update",
                "description": "Update an existing notebook entry. Can update content, title, tags, or status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "notebook_id": {"type": "string"},
                        "collection": {
                            "type": "string",
                            "enum": ["pages", "code_snippets", "research_notes"]
                        },
                        "content": {"type": "string", "description": "New content (replaces existing)"},
                        "title": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "summary": {"type": "string"},
                        "status": {"type": "string", "enum": ["draft", "in_progress", "complete", "archived"]}
                    },
                    "required": ["notebook_id", "collection"]
                }
            },
            {
                "name": "notebook_search",
                "description": "Search across notebook entries by text query or tags. Returns titles and summaries only (not full content) to keep context lean.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text search query"},
                        "collection": {
                            "type": "string",
                            "enum": ["pages", "code_snippets", "research_notes"],
                            "description": "Limit search to specific collection (optional)"
                        },
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer", "default": 10}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "notebook_list",
                "description": "List recent notebook entries. Returns titles, summaries, and metadata (not full content).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "collection": {
                            "type": "string",
                            "enum": ["pages", "code_snippets", "research_notes"]
                        },
                        "limit": {"type": "integer", "default": 10},
                        "status": {"type": "string", "enum": ["draft", "in_progress", "complete", "archived"]}
                    }
                }
            },
            {
                "name": "notebook_delete",
                "description": "Delete a notebook entry by ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "notebook_id": {"type": "string"},
                        "collection": {
                            "type": "string",
                            "enum": ["pages", "code_snippets", "research_notes"]
                        }
                    },
                    "required": ["notebook_id", "collection"]
                }
            }
        ]

    # ─── CORE OPERATIONS ─────────────────────────────────────────────────

    async def create(
        self,
        collection: str,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None,
        **extra_fields
    ) -> Dict[str, Any]:
        """Create a new notebook entry."""
        self._validate_collection(collection)
        
        doc_id = str(uuid.uuid4())[:12]  # Short but unique
        now = datetime.now(timezone.utc)
        
        # Auto-generate summary if not provided (first 200 chars)
        if not summary:
            summary = content[:200].strip() + ("..." if len(content) > 200 else "")

        document = {
            "_id": doc_id,
            "title": title,
            "content": content,
            "summary": summary,
            "metadata": {
                "created_by": self.agent_id,
                "created_at": now,
                "updated_at": now,
                "version": 1,
                "tags": tags or [],
                "word_count": len(content.split()),
                "status": "draft"
            },
            "history": [
                {"version": 1, "timestamp": now, "summary": "Created", "changed_by": self.agent_id}
            ],
            **extra_fields
        }

        coll = self.db[collection]
        await coll.insert_one(document)

        # Push reference to Redis stream of consciousness
        await self._push_redis_ref(doc_id, title, summary, collection, "created")

        return {
            "notebook_id": doc_id,
            "title": title,
            "collection": collection,
            "status": "created"
        }

    async def read(self, notebook_id: str, collection: str) -> Optional[Dict[str, Any]]:
        """Read a full notebook entry. Returns entire document including content."""
        self._validate_collection(collection)
        coll = self.db[collection]
        doc = await coll.find_one({"_id": notebook_id})
        
        if doc:
            # Log the "opened" event to Redis
            await self._push_redis_ref(
                notebook_id, doc["title"], doc.get("summary", ""), collection, "opened"
            )
        
        return doc

    async def update(
        self,
        notebook_id: str,
        collection: str,
        content: Optional[str] = None,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an existing notebook entry."""
        self._validate_collection(collection)
        coll = self.db[collection]
        
        # Build update dict with only provided fields
        update_fields = {"metadata.updated_at": datetime.now(timezone.utc)}
        changes = []
        
        if content is not None:
            update_fields["content"] = content
            update_fields["metadata.word_count"] = len(content.split())
            changes.append("content updated")
        if title is not None:
            update_fields["title"] = title
            changes.append(f"title changed to '{title}'")
        if tags is not None:
            update_fields["metadata.tags"] = tags
            changes.append("tags updated")
        if summary is not None:
            update_fields["summary"] = summary
        if status is not None:
            update_fields["metadata.status"] = status
            changes.append(f"status → {status}")

        # Increment version and add history entry
        result = await coll.find_one_and_update(
            {"_id": notebook_id},
            {
                "$set": update_fields,
                "$inc": {"metadata.version": 1},
                "$push": {
                    "history": {
                        "version": "$metadata.version",  # Will be the new version
                        "timestamp": datetime.now(timezone.utc),
                        "summary": "; ".join(changes) if changes else "Updated",
                        "changed_by": self.agent_id
                    }
                }
            },
            return_document=True  # Return updated doc
        )

        if result:
            await self._push_redis_ref(
                notebook_id, result["title"], result.get("summary", ""),
                collection, "updated"
            )
            return {"notebook_id": notebook_id, "status": "updated", "version": result["metadata"]["version"]}
        
        return {"notebook_id": notebook_id, "status": "not_found"}

    async def search(
        self,
        query: str,
        collection: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search notebook entries. Returns summaries only (not full content)
        to keep LLM context window lean.
        """
        search_filter = {}
        
        if tags:
            search_filter["metadata.tags"] = {"$in": tags}

        # Text search across title and content
        if query:
            search_filter["$text"] = {"$search": query}

        collections_to_search = [collection] if collection else self.VALID_COLLECTIONS
        results = []

        for coll_name in collections_to_search:
            self._validate_collection(coll_name)
            coll = self.db[coll_name]
            
            # Project only summary fields — never return full content in search
            cursor = coll.find(
                search_filter,
                {
                    "_id": 1,
                    "title": 1,
                    "summary": 1,
                    "metadata.tags": 1,
                    "metadata.updated_at": 1,
                    "metadata.status": 1,
                    "metadata.created_by": 1,
                    "metadata.word_count": 1
                }
            ).sort("metadata.updated_at", -1).limit(limit)
            
            async for doc in cursor:
                doc["_collection"] = coll_name
                results.append(doc)

        return results

    async def list_entries(
        self,
        collection: Optional[str] = None,
        limit: int = 10,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List recent entries. Returns summaries only."""
        search_filter = {}
        if status:
            search_filter["metadata.status"] = status

        collections_to_search = [collection] if collection else self.VALID_COLLECTIONS
        results = []

        for coll_name in collections_to_search:
            self._validate_collection(coll_name)
            coll = self.db[coll_name]
            
            cursor = coll.find(
                search_filter,
                {
                    "_id": 1,
                    "title": 1,
                    "summary": 1,
                    "metadata.tags": 1,
                    "metadata.updated_at": 1,
                    "metadata.status": 1,
                    "metadata.word_count": 1
                }
            ).sort("metadata.updated_at", -1).limit(limit)
            
            async for doc in cursor:
                doc["_collection"] = coll_name
                results.append(doc)

        return sorted(results, key=lambda x: x.get("metadata", {}).get("updated_at", ""), reverse=True)[:limit]

    async def delete(self, notebook_id: str, collection: str) -> Dict[str, Any]:
        """Delete a notebook entry."""
        self._validate_collection(collection)
        coll = self.db[collection]
        result = await coll.delete_one({"_id": notebook_id})
        
        if result.deleted_count > 0:
            await self._push_redis_ref(notebook_id, "", "", collection, "deleted")
            return {"notebook_id": notebook_id, "status": "deleted"}
        
        return {"notebook_id": notebook_id, "status": "not_found"}

    # ─── REDIS INTEGRATION ───────────────────────────────────────────────

    async def _push_redis_ref(
        self, notebook_id: str, title: str, summary: str,
        collection: str, action: str
    ):
        """
        Push a lightweight notebook reference to the Redis stream of consciousness.
        This keeps the agent aware of notebook activity without loading full content.
        """
        if not self.redis:
            return
        
        import json
        from datetime import date
        
        ref = json.dumps({
            "type": "notebook_ref",
            "action": action,
            "notebook_id": notebook_id,
            "title": title,
            "summary": summary[:200] if summary else "",
            "collection": collection,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": self.agent_id
        })
        
        # Push to the daily stream (same pattern as existing AetherMemory)
        today = date.today().isoformat()
        await self.redis.rpush(f"aether:daily:{today}", ref)
        
        # Also store as a searchable hash for RediSearch
        hash_key = f"aether:notebook:ref:{notebook_id}"
        await self.redis.hset(hash_key, mapping={
            "content": f"[Notebook {action}] {title}: {summary[:200]}",
            "source": "notebook",
            "tags": collection,
            "score": "0.8",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    # ─── HELPERS ─────────────────────────────────────────────────────────

    def _validate_collection(self, collection: str):
        if collection not in self.VALID_COLLECTIONS:
            raise ValueError(
                f"Invalid collection '{collection}'. Must be one of: {self.VALID_COLLECTIONS}"
            )
```

### 4.4 Integration with Existing AetherMemory

The key integration point is in `aether/aether_memory.py`. The Notebook tool should be initialized alongside the existing Redis memory system.

**Modify:** `aether/aether_memory.py` (add, don't replace)
```python
# At the top of the file, add:
from aether.notebook.connection import NotebookDB
from aether.notebook.tool import NotebookTool

# In your agent/memory initialization (wherever Redis client is created):
class AetherMemory:
    def __init__(self, agent_id: str, redis_client):
        self.redis = redis_client
        # ... existing Redis setup ...
        
        # NEW: Add notebook capability
        self.notebook = NotebookTool(agent_id=agent_id, redis_client=redis_client)
    
    async def initialize(self):
        # ... existing Redis initialization ...
        
        # NEW: Connect to MongoDB
        await NotebookDB.connect()
```

### 4.5 App Startup/Shutdown Hooks

**Modify:** Your FastAPI app startup (wherever that lives)
```python
from aether.notebook.connection import NotebookDB

@app.on_event("startup")
async def startup():
    # ... existing Redis connection ...
    await NotebookDB.connect()  # Add this

@app.on_event("shutdown")
async def shutdown():
    # ... existing cleanup ...
    await NotebookDB.disconnect()  # Add this
```

### 4.6 Environment Variable

Add to your `.env` or environment config:
```bash
MONGODB_URL=mongodb://<R64_NODE_IP>:27017
```

---

## 5. FILE STRUCTURE

New files to create:
```
aether/
├── notebook/
│   ├── __init__.py              # Export NotebookDB and NotebookTool
│   ├── connection.py            # MongoDB connection manager (Section 4.1)
│   └── tool.py                  # NotebookTool class (Section 4.3)
```

Files to modify:
```
aether/
├── aether_memory.py             # Add NotebookTool initialization (Section 4.4)
├── [your FastAPI app entry]     # Add startup/shutdown hooks (Section 4.5)
└── .env                         # Add MONGODB_URL (Section 4.6)
```

---

## 6. HOW THE AGENT USES IT — Workflow Example

Here's a complete flow of an agent writing a proposal over multiple sessions:

### Session 1: Agent starts a new document
```
Agent thinks: "I need to write a proposal for the drone swarm architecture."

Agent calls: notebook_create(
    collection="pages",
    title="AetherSync Drone Swarm Architecture Proposal",
    content="## Overview\n\nThis proposal outlines the distributed autonomous...",
    tags=["aethersync", "drones", "proposal"]
)

Redis stream gets: {"type": "notebook_ref", "action": "created", "title": "AetherSync Drone..."}
MongoDB stores: Full document content
```

### Session 2: Agent resumes work
```
Agent's context window loads from Redis → sees notebook_ref: "AetherSync Drone Swarm..."
Agent knows it has a document in progress without the full content being in context.

Agent calls: notebook_read(notebook_id="abc123", collection="pages")
→ Full content loaded into working context
→ Agent edits and updates

Agent calls: notebook_update(
    notebook_id="abc123",
    collection="pages",
    content="[updated full content]",
    status="in_progress"
)
```

### Session 3: Agent needs to reference while doing other work
```
Agent is answering a user question about drones.
Agent's context has the notebook_ref summary from Redis.
Agent can reference the proposal's existence and summary WITHOUT opening it.
If the user asks for details → Agent calls notebook_read to pull the full doc.
```

---

## 7. CRITICAL DESIGN RULES

1. **Never store full document content in Redis** — Only titles, summaries, and references go into Redis. Full content lives in MongoDB.

2. **Always push a Redis reference on notebook writes** — This keeps the agent's stream of consciousness aware of notebook activity. The `_push_redis_ref` method handles this automatically.

3. **Search returns summaries, not content** — The `search()` and `list_entries()` methods project only summary fields. The agent must explicitly `read()` to get full content. This prevents accidental context window flooding.

4. **Checkpoints should include notebook state** — When `checkpoint_snapshot()` runs, it should also capture a list of notebook entry IDs and their versions (but NOT their full content). This allows rollback awareness without bloating the checkpoint.

5. **One MongoDB instance, multiple agents** — All agents share the same MongoDB database but their entries are tagged with `metadata.created_by`. Agents can read each other's notebooks (collaboration) but should primarily work with their own.

6. **Version tracking is lightweight** — The `history` array stores only version numbers and change summaries, not full content diffs. This keeps documents lean. If full version history is needed later, consider a separate `versions` collection.

---

## 8. TESTING CHECKLIST

After implementation, verify:

- [ ] `await NotebookDB.connect()` succeeds and creates indexes
- [ ] `notebook_create` inserts document into MongoDB AND pushes ref to Redis
- [ ] `notebook_read` returns full content and logs "opened" to Redis
- [ ] `notebook_update` increments version, updates content, pushes ref to Redis
- [ ] `notebook_search` returns ONLY summaries (never full content)
- [ ] `notebook_list` returns recent entries sorted by updated_at
- [ ] `notebook_delete` removes from MongoDB and logs to Redis
- [ ] Agent's context window shows notebook refs (titles/summaries) from Redis
- [ ] Agent can "open" a notebook page and see full content on demand
- [ ] Multiple agents can create entries in the same database
- [ ] App starts and stops cleanly with MongoDB connection lifecycle

---

## 9. FUTURE ENHANCEMENTS (Not for now — just awareness)

- **Vector search in MongoDB**: MongoDB Atlas supports vector search. Could add embedding-based semantic search to notebooks later.
- **Notebook sharing/permissions**: Agent-level read/write permissions on notebook entries.
- **Auto-summarization**: When an agent creates a long document, auto-generate a summary using the LLM.
- **Notebook-to-checkpoint integration**: Include notebook state in Redis checkpoints for full state rollback.
- **GridFS for large files**: If agents need to store files (PDFs, images), use MongoDB GridFS instead of cramming them into documents.
- **Telemetry-as-Memory bridge**: Connect notebook operations to the OpenTelemetry observability layer discussed in prior sessions for full cognitive tracing.
