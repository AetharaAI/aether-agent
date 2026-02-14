import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from .database import db

logger = logging.getLogger("aether.fabric_registry")

class FabricRegistry:
    """
    Registry for Fabric Agents with Passport-IAM security.
    Manages the 'agent_registry' table in Postgres.
    """
    
    @staticmethod
    async def get_agent(agent_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve agent details by ID."""
        if not db.pool: return None
        
        query = "SELECT * FROM agent_registry WHERE id = $1"
        try:
            row = await db.pool.fetchrow(query, agent_id)
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get agent {agent_id}: {e}")
            return None

    @staticmethod
    async def register_agent(
        agent_id: str,
        name: str,
        owner_id: str,
        client_id: str,
        capabilities: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Register or update an agent in the secure registry.
        Usually called after Passport token validation.
        """
        if not db.pool: return False
        
        query = """
        INSERT INTO agent_registry (id, name, owner_id, client_id, capabilities, metadata, last_seen)
        VALUES ($1, $2, $3, $4, $5, $6, NOW())
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            owner_id = EXCLUDED.owner_id,
            client_id = EXCLUDED.client_id,
            capabilities = EXCLUDED.capabilities,
            metadata = agent_registry.metadata || EXCLUDED.metadata,
            last_seen = NOW()
        """
        try:
            await db.pool.execute(
                query, 
                agent_id, 
                name, 
                owner_id, 
                client_id, 
                capabilities or [], 
                json.dumps(metadata or {})
            )
            logger.info(f"Agent {agent_id} registered successfully (Owner: {owner_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to register agent {agent_id}: {e}")
            return False

    @staticmethod
    async def list_agents(security_level: str = None) -> List[Dict[str, Any]]:
        """List active agents, optionally filtered by security level."""
        if not db.pool: return []
        
        query = "SELECT * FROM agent_registry"
        params = []
        if security_level:
            query += " WHERE security_level = $1"
            params.append(security_level)
            
        query += " ORDER BY last_seen DESC"
        
        try:
            rows = await db.pool.fetch(query, *params)
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to list agents: {e}")
            return []

    @staticmethod
    async def update_status(agent_id: str, status: str):
        """Update agent's online status."""
        if not db.pool: return
        
        query = "UPDATE agent_registry SET status = $1, last_seen = NOW() WHERE id = $2"
        try:
            await db.pool.execute(query, status, agent_id)
        except Exception as e:
            logger.error(f"Failed to update status for {agent_id}: {e}")

    @staticmethod
    async def verify_passport_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a Passport-IAM JWT.
        Placeholder for real OIDC validation logic.
        """
        # In production, this would:
        # 1. Fetch JWKS from https://passport.aetherpro.us/auth/realms/aether/protocol/openid-connect/certs
        # 2. Verify signature, expiry, and audience.
        # 3. Extract 'sub' (User ID) and 'client_id' (Agent ID).
        
        # PROPOSED: For demo/mock phase, we accept standard JWT format or a dev secret
        if token == "dev-shared-secret":
            return {
                "sub": "dev-user-123",
                "client_id": "aether-agent-primary",
                "preferred_username": "cory",
                "roles": ["agent", "developer"]
            }
        
        # Real validation logic would go here
        return None

# Global instance
registry = FabricRegistry()
