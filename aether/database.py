import os
import asyncpg
import logging
from typing import Optional
import json

logger = logging.getLogger("aether.db")

class AetherDatabase:
    """
    Postgres database manager for AetherOS telemetry and state.
    """
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.dsn = os.getenv("POSTGRES_DSN")
        
    async def connect(self):
        """Initialize connection pool."""
        if not self.dsn:
            logger.warning("POSTGRES_DSN not set. Database features disabled.")
            return

        try:
            self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=10)
            logger.info("Connected to Postgres.")
            await self._init_schema()
        except Exception as e:
            logger.error(f"Failed to connect to Postgres: {e}")
            
    async def close(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Closed Postgres connection.")

    async def _init_schema(self):
        """Initialize database schema from init.sql if needed."""
        # For now, we assume schema is managed manually or via migration tools.
        # This is just a placeholder for future auto-migration logic.
        pass

    async def log_tool_call(self, session_id: str, tool_name: str, arguments: dict, result: dict, duration_ms: int, error: str = None):
        """Log a tool execution."""
        if not self.pool: return
        
        query = """
        INSERT INTO tool_calls (session_id, tool_name, arguments, result, error, duration_ms)
        VALUES ($1, $2, $3, $4, $5, $6)
        """
        try:
            await self.pool.execute(query, session_id, tool_name, 
                                    json.dumps(arguments), json.dumps(result), 
                                    error, duration_ms)
        except Exception as e:
            logger.error(f"Failed to log tool call: {e}")

    async def log_api_call(self, session_id: str, provider: str, model: str, tokens: dict, cost: float, endpoint: str = ""):
        """Log an LLM API call."""
        if not self.pool: return

        query = """
        INSERT INTO api_calls (session_id, provider, model, prompt_tokens, completion_tokens, total_tokens, cost, endpoint)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        try:
            await self.pool.execute(query, session_id, provider, model, 
                                    tokens.get("prompt", 0), tokens.get("completion", 0), tokens.get("total", 0),
                                    cost, endpoint)
        except Exception as e:
            logger.error(f"Failed to log API call: {e}")

    async def create_session(self, session_id: str, user_id: str = "default", metadata: dict = None):
        """Create a new agent session."""
        if not self.pool: return

        query = """
        INSERT INTO agent_sessions (session_id, user_id, metadata)
        VALUES ($1, $2, $3)
        ON CONFLICT (session_id) DO NOTHING
        """
        try:
            await self.pool.execute(query, session_id, user_id, json.dumps(metadata or {}))
        except Exception as e:
            logger.error(f"Failed to create session: {e}")

    async def save_message(self, session_id: str, role: str, content: str):
        if not self.pool:
            return
        try:
            await self.pool.execute(
                """
                INSERT INTO chat_messages (session_id, role, content)
                VALUES ($1, $2, $3)
                """,
                session_id, role, content
            )
        except Exception as e:
            logger.error(f"Failed to save message: {e}")

    async def get_messages(self, session_id: str) -> list[dict]:
        if not self.pool:
            return []
        try:
            rows = await self.pool.fetch(
                """
                SELECT role, content, timestamp 
                FROM chat_messages 
                WHERE session_id = $1 
                ORDER BY timestamp ASC
                """,
                session_id
            )
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []

    async def update_session_title(self, session_id: str, title: str):
        """Update a session's title in its metadata."""
        if not self.pool:
            return
        try:
            # Read current metadata, merge in the title, write back
            row = await self.pool.fetchrow(
                "SELECT metadata FROM agent_sessions WHERE session_id = $1",
                session_id
            )
            meta = {}
            if row and row["metadata"]:
                raw = row["metadata"]
                if isinstance(raw, str):
                    try:
                        meta = json.loads(raw)
                    except Exception:
                        meta = {}
                elif isinstance(raw, dict):
                    meta = raw
            meta["title"] = title
            await self.pool.execute(
                "UPDATE agent_sessions SET metadata = $1 WHERE session_id = $2",
                json.dumps(meta), session_id
            )
        except Exception as e:
            logger.error(f"Failed to update session title: {e}")

# Helper for JSON serialization if needed, though asyncpg handles dicts with jsonb automatically if connection is configured correctly,
# but usually requires set_type_codec. For simplicity in this snippet, we'll rely on asyncpg's default behavior or explicit casting if needed.
# Actually, asyncpg requires explicitly wrapping dicts in `asyncpg.types.Json` or setting a codec.
# Let's add a helper class.



# Global instance
db = AetherDatabase()
