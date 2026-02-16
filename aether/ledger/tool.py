"""
Agent Ledger Tools — MongoDB-backed persistent document storage for agents.

6 tools following the AetherOS Tool base class pattern:
  - ledger_create: Create page/code_snippet/research_note
  - ledger_read: Open full document by ID
  - ledger_update: Update content/title/tags/status, increment version
  - ledger_search: Text search returning summaries only
  - ledger_list: List recent entries with summaries
  - ledger_delete: Remove an entry

DESIGN RULE: Redis holds titles/summaries/refs. MongoDB holds full content.
Every write pushes a lightweight ref to the Redis daily stream.
"""

import uuid
import json
import logging
from datetime import datetime, timezone, date
from typing import Optional, List, Dict, Any

from aether.tools.registry import Tool, ToolResult, ToolPermission

logger = logging.getLogger("aether.ledger")

VALID_COLLECTIONS = ["pages", "code_snippets", "research_notes"]


def _validate_collection(collection: str):
    if collection not in VALID_COLLECTIONS:
        raise ValueError(f"Invalid collection '{collection}'. Must be one of: {VALID_COLLECTIONS}")


async def _push_redis_ref(redis, agent_id: str, notebook_id: str, title: str,
                          summary: str, collection: str, action: str):
    """Push a lightweight ledger reference to the Redis stream of consciousness."""
    if redis is None:
        return

    ref = json.dumps({
        "type": "ledger_ref",
        "action": action,
        "notebook_id": notebook_id,
        "title": title,
        "summary": summary[:200] if summary else "",
        "collection": collection,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent_id,
    })

    today = date.today().isoformat()
    try:
        await redis.rpush(f"aether:daily:{today}", ref)

        hash_key = f"aether:ledger:ref:{notebook_id}"
        await redis.hset(hash_key, mapping={
            "content": f"[Ledger {action}] {title}: {summary[:200] if summary else ''}",
            "source": "ledger",
            "tags": collection,
            "score": "0.8",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"Failed to push ledger ref to Redis: {e}")


# ─── TOOL CLASSES ────────────────────────────────────────────────────────────


class LedgerCreateTool(Tool):
    """Create a new entry in the Agent Ledger (page, code snippet, or research note)."""

    name = "ledger_create"
    description = (
        "Create a new ledger entry (page, code_snippet, or research_note). "
        "Use for storing documents, code, or research the agent is working on. "
        "Full content is stored in MongoDB; a lightweight reference is pushed to Redis."
    )
    permission = ToolPermission.SEMI
    parameters = {
        "collection": {
            "type": "string",
            "enum": ["pages", "code_snippets", "research_notes"],
            "description": "Type of ledger entry",
            "required": True,
        },
        "title": {
            "type": "string",
            "description": "Title of the entry",
            "required": True,
        },
        "content": {
            "type": "string",
            "description": "Full content (markdown for pages, code for snippets, notes for research)",
            "required": True,
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tags for categorization",
            "required": False,
        },
        "summary": {
            "type": "string",
            "description": "Brief summary (auto-generated from first 200 chars if not provided)",
            "required": False,
        },
    }

    def __init__(self):
        self._memory = None
        self._db = None

    def set_memory(self, memory):
        self._memory = memory

    def set_ledger_db(self, db):
        self._db = db

    async def execute(self, collection: str, title: str, content: str,
                      tags: Optional[List[str]] = None,
                      summary: Optional[str] = None, **kwargs) -> ToolResult:
        if self._db is None:
            return ToolResult(success=False, error="Agent Ledger not connected")

        try:
            _validate_collection(collection)
            doc_id = str(uuid.uuid4())[:12]
            now = datetime.now(timezone.utc)

            if not summary:
                summary = content[:200].strip() + ("..." if len(content) > 200 else "")

            document = {
                "_id": doc_id,
                "title": title,
                "content": content,
                "summary": summary,
                "metadata": {
                    "created_by": "agent:aether",
                    "created_at": now,
                    "updated_at": now,
                    "version": 1,
                    "tags": tags or [],
                    "word_count": len(content.split()),
                    "status": "draft",
                },
                "history": [
                    {"version": 1, "timestamp": now, "summary": "Created", "changed_by": "agent:aether"}
                ],
            }

            coll = self._db[collection]
            await coll.insert_one(document)

            redis = getattr(self._memory, "redis", None)
            await _push_redis_ref(redis, "agent:aether", doc_id, title, summary, collection, "created")

            return ToolResult(
                success=True,
                data={
                    "notebook_id": doc_id,
                    "title": title,
                    "collection": collection,
                    "status": "created",
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to create ledger entry: {e}")


class LedgerReadTool(Tool):
    """Read/open a ledger entry by ID. Returns full content."""

    name = "ledger_read"
    description = (
        "Read a ledger entry by ID. Returns the full content from MongoDB. "
        "Use when the agent needs to review or reference a specific document."
    )
    permission = ToolPermission.SEMI
    parameters = {
        "notebook_id": {
            "type": "string",
            "description": "The ID of the ledger entry to read",
            "required": True,
        },
        "collection": {
            "type": "string",
            "enum": ["pages", "code_snippets", "research_notes"],
            "description": "Which collection to look in",
            "required": True,
        },
    }

    def __init__(self):
        self._memory = None
        self._db = None

    def set_memory(self, memory):
        self._memory = memory

    def set_ledger_db(self, db):
        self._db = db

    async def execute(self, notebook_id: str, collection: str, **kwargs) -> ToolResult:
        if self._db is None:
            return ToolResult(success=False, error="Agent Ledger not connected")

        try:
            _validate_collection(collection)
            coll = self._db[collection]
            doc = await coll.find_one({"_id": notebook_id})

            if not doc:
                return ToolResult(success=False, error=f"Entry '{notebook_id}' not found in {collection}")

            redis = getattr(self._memory, "redis", None)
            await _push_redis_ref(
                redis, "agent:aether", notebook_id,
                doc["title"], doc.get("summary", ""), collection, "opened"
            )

            # Convert datetime objects for JSON serialization
            result_doc = _serialize_doc(doc)
            return ToolResult(success=True, data=result_doc)
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to read ledger entry: {e}")


class LedgerUpdateTool(Tool):
    """Update an existing ledger entry. Increments version, pushes ref to Redis."""

    name = "ledger_update"
    description = (
        "Update an existing ledger entry. Can update content, title, tags, or status. "
        "Automatically increments version number."
    )
    permission = ToolPermission.SEMI
    parameters = {
        "notebook_id": {
            "type": "string",
            "description": "The ID of the entry to update",
            "required": True,
        },
        "collection": {
            "type": "string",
            "enum": ["pages", "code_snippets", "research_notes"],
            "description": "Which collection the entry is in",
            "required": True,
        },
        "content": {
            "type": "string",
            "description": "New content (replaces existing)",
            "required": False,
        },
        "title": {
            "type": "string",
            "description": "New title",
            "required": False,
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "New tags",
            "required": False,
        },
        "summary": {
            "type": "string",
            "description": "New summary",
            "required": False,
        },
        "status": {
            "type": "string",
            "enum": ["draft", "in_progress", "complete", "archived"],
            "description": "New status",
            "required": False,
        },
    }

    def __init__(self):
        self._memory = None
        self._db = None

    def set_memory(self, memory):
        self._memory = memory

    def set_ledger_db(self, db):
        self._db = db

    async def execute(self, notebook_id: str, collection: str,
                      content: Optional[str] = None, title: Optional[str] = None,
                      tags: Optional[List[str]] = None, summary: Optional[str] = None,
                      status: Optional[str] = None, **kwargs) -> ToolResult:
        if self._db is None:
            return ToolResult(success=False, error="Agent Ledger not connected")

        try:
            _validate_collection(collection)
            coll = self._db[collection]
            now = datetime.now(timezone.utc)

            update_fields: Dict[str, Any] = {"metadata.updated_at": now}
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
                changes.append(f"status -> {status}")

            result = await coll.find_one_and_update(
                {"_id": notebook_id},
                {
                    "$set": update_fields,
                    "$inc": {"metadata.version": 1},
                    "$push": {
                        "history": {
                            "timestamp": now,
                            "summary": "; ".join(changes) if changes else "Updated",
                            "changed_by": "agent:aether",
                        }
                    },
                },
                return_document=True,
            )

            if not result:
                return ToolResult(success=False, error=f"Entry '{notebook_id}' not found in {collection}")

            redis = getattr(self._memory, "redis", None)
            await _push_redis_ref(
                redis, "agent:aether", notebook_id,
                result["title"], result.get("summary", ""), collection, "updated"
            )

            return ToolResult(
                success=True,
                data={
                    "notebook_id": notebook_id,
                    "status": "updated",
                    "version": result["metadata"]["version"],
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to update ledger entry: {e}")


class LedgerSearchTool(Tool):
    """Search ledger entries by text query or tags. Returns summaries only."""

    name = "ledger_search"
    description = (
        "Search across ledger entries by text query or tags. "
        "Returns titles and summaries only (not full content) to keep context lean."
    )
    permission = ToolPermission.SEMI
    parameters = {
        "query": {
            "type": "string",
            "description": "Text search query",
            "required": True,
        },
        "collection": {
            "type": "string",
            "enum": ["pages", "code_snippets", "research_notes"],
            "description": "Limit search to specific collection (optional)",
            "required": False,
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Filter by tags",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Max results to return (default 10)",
            "required": False,
        },
    }

    def __init__(self):
        self._memory = None
        self._db = None

    def set_memory(self, memory):
        self._memory = memory

    def set_ledger_db(self, db):
        self._db = db

    async def execute(self, query: str, collection: Optional[str] = None,
                      tags: Optional[List[str]] = None,
                      limit: int = 10, **kwargs) -> ToolResult:
        if self._db is None:
            return ToolResult(success=False, error="Agent Ledger not connected")

        try:
            search_filter: Dict[str, Any] = {}
            if tags:
                search_filter["metadata.tags"] = {"$in": tags}
            if query:
                search_filter["$text"] = {"$search": query}

            collections_to_search = [collection] if collection else VALID_COLLECTIONS
            results = []

            for coll_name in collections_to_search:
                _validate_collection(coll_name)
                coll = self._db[coll_name]

                projection = {
                    "_id": 1, "title": 1, "summary": 1,
                    "metadata.tags": 1, "metadata.updated_at": 1,
                    "metadata.status": 1, "metadata.created_by": 1,
                    "metadata.word_count": 1,
                }

                cursor = coll.find(search_filter, projection).sort(
                    "metadata.updated_at", -1
                ).limit(limit)

                async for doc in cursor:
                    doc["_collection"] = coll_name
                    results.append(_serialize_doc(doc))

            results.sort(key=lambda x: x.get("metadata", {}).get("updated_at", ""), reverse=True)

            return ToolResult(
                success=True,
                data={"results": results[:limit], "total": len(results)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Ledger search failed: {e}")


class LedgerListTool(Tool):
    """List recent ledger entries. Returns summaries only."""

    name = "ledger_list"
    description = (
        "List recent ledger entries. Returns titles, summaries, and metadata "
        "(not full content). Use to see what's in the ledger."
    )
    permission = ToolPermission.SEMI
    parameters = {
        "collection": {
            "type": "string",
            "enum": ["pages", "code_snippets", "research_notes"],
            "description": "Filter by collection type (optional)",
            "required": False,
        },
        "limit": {
            "type": "integer",
            "description": "Max entries to return (default 10)",
            "required": False,
        },
        "status": {
            "type": "string",
            "enum": ["draft", "in_progress", "complete", "archived"],
            "description": "Filter by status (optional)",
            "required": False,
        },
    }

    def __init__(self):
        self._memory = None
        self._db = None

    def set_memory(self, memory):
        self._memory = memory

    def set_ledger_db(self, db):
        self._db = db

    async def execute(self, collection: Optional[str] = None,
                      limit: int = 10, status: Optional[str] = None, **kwargs) -> ToolResult:
        if self._db is None:
            return ToolResult(success=False, error="Agent Ledger not connected")

        try:
            search_filter: Dict[str, Any] = {}
            if status:
                search_filter["metadata.status"] = status

            collections_to_search = [collection] if collection else VALID_COLLECTIONS
            results = []

            for coll_name in collections_to_search:
                _validate_collection(coll_name)
                coll = self._db[coll_name]

                projection = {
                    "_id": 1, "title": 1, "summary": 1,
                    "metadata.tags": 1, "metadata.updated_at": 1,
                    "metadata.status": 1, "metadata.word_count": 1,
                }

                cursor = coll.find(search_filter, projection).sort(
                    "metadata.updated_at", -1
                ).limit(limit)

                async for doc in cursor:
                    doc["_collection"] = coll_name
                    results.append(_serialize_doc(doc))

            results.sort(key=lambda x: x.get("metadata", {}).get("updated_at", ""), reverse=True)

            return ToolResult(
                success=True,
                data={"entries": results[:limit], "total": len(results)},
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Ledger list failed: {e}")


class LedgerDeleteTool(Tool):
    """Delete a ledger entry by ID."""

    name = "ledger_delete"
    description = "Delete a ledger entry by ID. Removes from MongoDB and logs to Redis."
    permission = ToolPermission.SEMI
    parameters = {
        "notebook_id": {
            "type": "string",
            "description": "The ID of the entry to delete",
            "required": True,
        },
        "collection": {
            "type": "string",
            "enum": ["pages", "code_snippets", "research_notes"],
            "description": "Which collection the entry is in",
            "required": True,
        },
    }

    def __init__(self):
        self._memory = None
        self._db = None

    def set_memory(self, memory):
        self._memory = memory

    def set_ledger_db(self, db):
        self._db = db

    async def execute(self, notebook_id: str, collection: str, **kwargs) -> ToolResult:
        if self._db is None:
            return ToolResult(success=False, error="Agent Ledger not connected")

        try:
            _validate_collection(collection)
            coll = self._db[collection]
            result = await coll.delete_one({"_id": notebook_id})

            if result.deleted_count > 0:
                redis = getattr(self._memory, "redis", None)
                await _push_redis_ref(redis, "agent:aether", notebook_id, "", "", collection, "deleted")
                return ToolResult(success=True, data={"notebook_id": notebook_id, "status": "deleted"})

            return ToolResult(success=False, error=f"Entry '{notebook_id}' not found in {collection}")
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to delete ledger entry: {e}")


# ─── HELPERS ─────────────────────────────────────────────────────────────────


def _serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert MongoDB document to JSON-serializable dict."""
    result = {}
    for k, v in doc.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, dict):
            result[k] = _serialize_doc(v)
        elif isinstance(v, list):
            result[k] = [
                _serialize_doc(item) if isinstance(item, dict)
                else item.isoformat() if isinstance(item, datetime)
                else item
                for item in v
            ]
        else:
            result[k] = v
    return result


# ─── MODULE-LEVEL INSTANCES ──────────────────────────────────────────────────

ledger_create_tool = LedgerCreateTool()
ledger_read_tool = LedgerReadTool()
ledger_update_tool = LedgerUpdateTool()
ledger_search_tool = LedgerSearchTool()
ledger_list_tool = LedgerListTool()
ledger_delete_tool = LedgerDeleteTool()
