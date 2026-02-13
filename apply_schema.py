
import asyncio
import os
import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def apply_schema():
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        print("Error: POSTGRES_DSN not found in .env")
        return

    print(f"Connecting to database...")
    try:
        conn = await asyncpg.connect(dsn)
        
        print("Applying chat_messages schema...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
        """)
        
        print("Schema applied successfully!")
        await conn.close()
    except Exception as e:
        print(f"Failed to apply schema: {e}")

if __name__ == "__main__":
    asyncio.run(apply_schema())
