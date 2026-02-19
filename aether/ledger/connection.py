"""
Agent Ledger — MongoDB Connection Manager

Async MongoDB connection using Motor for AetherOS's async-first architecture.
Database: agent_ledger

Collections:
  - pages: Long-form documents (proposals, reports, plans)
  - code_snippets: Code the agent writes or references
  - research_notes: Web research, findings, references
"""

import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional

logger = logging.getLogger("aether.ledger")


class LedgerDB:
    """MongoDB connection manager for Agent Ledger."""

    _client: Optional[AsyncIOMotorClient] = None
    _db = None

    @classmethod
    async def connect(cls):
        """Initialize MongoDB connection and create indexes. Call once at app startup."""
        mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
        cls._client = AsyncIOMotorClient(mongo_url)
        cls._db = cls._client[os.getenv("MONGO_LEDGER_DB_NAME", "agent_ledger")]

        # Create indexes for fast lookups
        try:
            # Pages collection
            await cls._db.pages.create_index("metadata.created_by")
            await cls._db.pages.create_index("metadata.tags")
            await cls._db.pages.create_index([("metadata.updated_at", -1)])
            await cls._db.pages.create_index(
                [("title", "text"), ("content", "text")],
                name="pages_text_idx",
            )

            # Code snippets collection
            await cls._db.code_snippets.create_index("metadata.language")
            await cls._db.code_snippets.create_index("metadata.created_by")
            await cls._db.code_snippets.create_index(
                [("title", "text"), ("code", "text")],
                name="snippets_text_idx",
            )

            # Research notes collection
            await cls._db.research_notes.create_index("metadata.source_url")
            await cls._db.research_notes.create_index("metadata.created_by")
            await cls._db.research_notes.create_index(
                [("title", "text"), ("content", "text")],
                name="research_text_idx",
            )

            ledger_db = os.getenv("MONGO_LEDGER_DB_NAME", "agent_ledger")
            logger.info(f"LedgerDB connected to {ledger_db} at {mongo_url}")
        except Exception as e:
            logger.warning(f"LedgerDB index creation warning (may already exist): {e}")

        return cls._db

    @classmethod
    def get_db(cls):
        """Get the database instance. Raises if not connected."""
        if cls._db is None:
            raise RuntimeError("LedgerDB not connected. Call await LedgerDB.connect() first.")
        return cls._db

    @classmethod
    async def disconnect(cls):
        """Clean shutdown."""
        if cls._client:
            cls._client.close()
            cls._client = None
            cls._db = None
            logger.info("LedgerDB disconnected")
