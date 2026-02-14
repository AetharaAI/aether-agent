import asyncio
import os
import json
import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

AGENTS = [
    {
        "id": "aether",
        "name": "Aether Principal",
        "owner_id": "cory-user-001",
        "client_id": "aether-client-id",
        "status": "idle",
        "capabilities": ["orchestration", "messaging", "checkpointing", "mcp"],
        "security_level": "trusted",
        "is_verified": True,
        "metadata": {"version": "2.1.0", "region": "us-east-1"}
    },
    {
        "id": "percy",
        "name": "Percy Analyst",
        "owner_id": "cory-user-001",
        "client_id": "percy-client-id",
        "status": "busy",
        "capabilities": ["analytics", "data_processing", "research"],
        "security_level": "verified",
        "is_verified": True,
        "metadata": {"specialty": "financial_data"}
    },
     {
        "id": "nexus",
        "name": "Nexus Gateway",
        "owner_id": "dev-user-789",
        "client_id": "nexus-client-id",
        "status": "idle",
        "capabilities": ["routing", "load_balancing", "mcp_proxy"],
        "security_level": "standard",
        "is_verified": False,
        "metadata": {"uptime_goal": "99.99%"}
    }
]

async def seed_registry():
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        print("Error: POSTGRES_DSN not found in .env")
        return

    print(f"Connecting to database to seed agents...")
    try:
        conn = await asyncpg.connect(dsn)
        
        for agent in AGENTS:
            print(f"Seeding agent: {agent['id']}...")
            await conn.execute("""
                INSERT INTO agent_registry (id, name, owner_id, client_id, status, capabilities, security_level, is_verified, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    status = EXCLUDED.status,
                    capabilities = EXCLUDED.capabilities,
                    security_level = EXCLUDED.security_level,
                    is_verified = EXCLUDED.is_verified,
                    metadata = EXCLUDED.metadata,
                    last_seen = NOW()
            """, 
            agent['id'], agent['name'], agent['owner_id'], agent['client_id'], 
            agent['status'], agent['capabilities'], agent['security_level'], 
            agent['is_verified'], json.dumps(agent['metadata']))
        
        print("Seeding completed successfully!")
        await conn.close()
    except Exception as e:
        print(f"Failed to seed registry: {e}")

if __name__ == "__main__":
    asyncio.run(seed_registry())
