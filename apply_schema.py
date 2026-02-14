
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
        
        # Read schema.sql
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                schema_sql = f.read()
            
            print(f"Applying schema from {schema_path}...")
            await conn.execute(schema_sql)
            print("Schema applied successfully!")
        else:
            print(f"Error: {schema_path} not found.")
            
        await conn.close()
    except Exception as e:
        print(f"Failed to apply schema: {e}")

if __name__ == "__main__":
    asyncio.run(apply_schema())
