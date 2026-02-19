#!/usr/bin/env python3
"""
Seed Tool Registry — Populate MongoDB with all Aether tool definitions.

Usage:
    python seed_tool_registry.py [--mongo-url mongodb://localhost:27017]

This script is idempotent: it uses upsert to safely re-run without duplicates.
It reads the actual tool classes to extract name, description, parameters, and
permission — no manual duplication of metadata required.
"""

import asyncio
import argparse
import importlib
import os
import sys
from datetime import datetime, timezone

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(__file__))

from motor.motor_asyncio import AsyncIOMotorClient


# ─── Tool Definitions ────────────────────────────────────────────────────────
# Each entry: (handler_path, class_name, tier, tags)
# handler_path is the importable module, class_name is the Tool subclass.

TOOL_DEFINITIONS = [
    # ── Core tier (always loaded) ──
    ("aether.tools.core_tools", "TerminalExecTool", "core", ["system", "terminal"]),
    ("aether.tools.core_tools", "FileReadTool", "core", ["filesystem", "read"]),
    ("aether.tools.core_tools", "FileListTool", "core", ["filesystem", "browse"]),
    ("aether.tools.core_tools", "FileWriteTool", "core", ["filesystem", "write"]),
    ("aether.tools.core_tools", "CheckpointTool", "core", ["memory", "checkpoint"]),
    ("aether.tools.core_tools", "CheckpointAndContinueTool", "core", ["memory", "checkpoint", "episodic"]),
    ("aether.tools.core_tools", "SetModeTool", "core", ["system", "autonomy"]),

    # ── Extended tier (dynamically loaded) ──
    ("aether.tools.tavily_search", "TavilySearchTool", "extended", ["web", "search", "internet"]),
    ("aether.tools.url_read", "URLReadTool", "extended", ["web", "fetch", "url"]),
    ("aether.tools.core_tools", "SearchMemoryTool", "extended", ["memory", "search", "recall"]),
    ("aether.tools.core_tools", "SearchWorkspaceTool", "extended", ["filesystem", "search", "workspace"]),
    ("aether.tools.core_tools", "CompressContextTool", "extended", ["memory", "compress", "context"]),
    ("aether.tools.core_tools", "GetContextStatsTool", "extended", ["memory", "stats", "monitoring"]),
    ("aether.tools.core_tools", "ListCheckpointsTool", "extended", ["memory", "checkpoint", "list"]),
    ("aether.tools.core_tools", "ReadCheckpointTool", "extended", ["memory", "checkpoint", "read"]),
    ("aether.tools.core_tools", "RecallEpisodesTool", "extended", ["memory", "episodic", "recall"]),
    ("aether.tools.core_tools", "FileUploadTool", "extended", ["filesystem", "upload"]),

    # ── Ledger tools (extended tier) ──
    ("aether.ledger.tool", "LedgerCreateTool", "extended", ["ledger", "mongodb", "create", "document"]),
    ("aether.ledger.tool", "LedgerReadTool", "extended", ["ledger", "mongodb", "read", "document"]),
    ("aether.ledger.tool", "LedgerUpdateTool", "extended", ["ledger", "mongodb", "update", "document"]),
    ("aether.ledger.tool", "LedgerSearchTool", "extended", ["ledger", "mongodb", "search", "document"]),
    ("aether.ledger.tool", "LedgerListTool", "extended", ["ledger", "mongodb", "list", "document"]),
    ("aether.ledger.tool", "LedgerDeleteTool", "extended", ["ledger", "mongodb", "delete", "document"]),
]


def _extract_tool_meta(module_path: str, class_name: str) -> dict:
    """Import a tool class and extract its metadata."""
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)

    return {
        "name": cls.name,
        "description": cls.description,
        "permission": cls.permission.value if hasattr(cls.permission, "value") else str(cls.permission),
        "parameters": cls.parameters,
    }


async def seed(mongo_url: str) -> int:
    """Seed the MongoDB tools collection. Returns count of seeded tools."""
    client = AsyncIOMotorClient(mongo_url)
    db_name = os.getenv("MONGO_DB_NAME", "aether_agent")
    db = client[db_name]
    coll = db["tools"]

    # Create indexes for search
    await coll.create_index("name", unique=True)
    await coll.create_index("tags")
    await coll.create_index("tier")
    await coll.create_index([("name", "text"), ("description", "text")])

    count = 0
    for module_path, class_name, tier, tags in TOOL_DEFINITIONS:
        try:
            meta = _extract_tool_meta(module_path, class_name)

            doc = {
                "name": meta["name"],
                "description": meta["description"],
                "permission": meta["permission"],
                "parameters": meta["parameters"],
                "handler_path": f"{module_path}.{class_name}",
                "tags": tags,
                "tier": tier,
                "enabled": True,
                "seeded_at": datetime.now(timezone.utc),
            }

            result = await coll.update_one(
                {"name": meta["name"]},
                {"$set": doc},
                upsert=True,
            )
            action = "updated" if result.matched_count > 0 else "created"
            print(f"  ✓ {meta['name']:30s} [{tier:8s}] {action}")
            count += 1

        except Exception as e:
            print(f"  ✗ {module_path}.{class_name}: {e}")

    client.close()
    return count


def main():
    parser = argparse.ArgumentParser(description="Seed Aether tool registry in MongoDB")
    parser.add_argument(
        "--mongo-url",
        default=os.getenv("MONGO_URL", "mongodb://localhost:27017"),
        help="MongoDB connection URL (default: $MONGO_URL or mongodb://localhost:27017)",
    )
    args = parser.parse_args()

    print(f"Seeding tool registry → {args.mongo_url}")
    print("=" * 60)

    count = asyncio.run(seed(args.mongo_url))

    print("=" * 60)
    db_name = os.getenv("MONGO_DB_NAME", "aether_agent")
    print(f"✓ Seeded {count} tool definitions to MongoDB ({db_name}.tools)")


if __name__ == "__main__":
    main()
