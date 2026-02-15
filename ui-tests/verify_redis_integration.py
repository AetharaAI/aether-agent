import asyncio
import json
import os
from redis.asyncio import Redis
from pathlib import Path

async def verify_redis():
    results = []
    results.append("--- Redis Stack Integration Verification ---")
    
    # Connect to Redis
    redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port = int(os.getenv("REDIS_PORT", "6381"))
    
    results.append(f"Connecting to Redis at {redis_host}:{redis_port}...")
    r = Redis(host=redis_host, port=redis_port, decode_responses=True)
    
    try:
        # 1. Check Identity Files
        files = await r.hgetall("aether:identity:files")
        results.append(f"\n[Identity Files] Found {len(files)} files in Redis:")
        for name in files.keys():
            results.append(f"  - {name}")
            
        if not files:
            results.append("  ❌ ERROR: No identity files found in Redis. Bootstrap failed?")
        else:
            results.append("  ✅ SUCCESS: Identity files bootstrapped.")

        # 2. Check Identity Profile
        profile = await r.get("aether:identity")
        if profile:
            profile_data = json.loads(profile)
            results.append(f"\n[Identity Profile] Found primary profile:")
            results.append(f"  - Name: {profile_data.get('name')}")
            results.append(f"  - Emoji: {profile_data.get('emoji')}")
            results.append("  ✅ SUCCESS: Primary identity profile exists.")
        else:
            results.append("\n[Identity Profile] Primary profile MISSING.")

        # 3. Check System Flags
        bootstrap_complete = await r.get("aether:system:bootstrap_complete")
        results.append(f"\n[System Flags] bootstrap_complete: {bootstrap_complete}")
        if bootstrap_complete == "true":
             results.append("  ✅ SUCCESS: System marked bootstrap as complete.")

    except Exception as e:
        results.append(f"  ❌ ERROR: {e}")
    finally:
        await r.aclose()
        
    with open("ui-tests/verification_results.log", "w") as f:
        f.write("\n".join(results))

if __name__ == "__main__":
    asyncio.run(verify_redis())
