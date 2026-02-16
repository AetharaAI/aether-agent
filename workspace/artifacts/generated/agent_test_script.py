#!/usr/bin/env python3
"""
Agent Test Script

This script demonstrates agent capabilities:
- Printing agent identity
- Writing to a file
- Simulating memory storage
- Logging execution timestamp
"""

import json
import os
import datetime
import redis

def main():
    # Print agent identity
    print("=== AGENT IDENTITY ===")
    print("Agent: Aether 7.0")
    print("Provider: AetherPro Technologies")
    print("Role: Autonomous execution engine\n")

    # Write to a file
    print("=== FILE WRITE OPERATION ===")
    test_file = "/workspace/artifacts/generated/test_write.txt"
    content = f"Test written by Aether agent at {datetime.datetime.now()}\n"
    
    try:
        with open(test_file, 'w') as f:
            f.write(content)
        print(f"Successfully wrote to {test_file}")
    except Exception as e:
        print(f"Error writing to file: {e}")

    # Simulate memory storage (Redis)
    print("\n=== MEMORY STORAGE SIMULATION ===")
    try:
        # Connect to Redis (assuming local instance)
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        # Store agent identity and timestamp
        memory_key = "agent:test:identity"
        memory_value = {
            "agent_id": "Aether-7.0-134a8f2",
            "timestamp": datetime.datetime.now().isoformat(),
            "operation": "test_script_execution"
        }
        
        r.set(memory_key, json.dumps(memory_value))
        print(f"Successfully stored memory key: {memory_key}")
        
        # Verify storage
        retrieved = r.get(memory_key)
        if retrieved:
            print(f"Memory retrieved successfully: {retrieved[:100]}...")
        
    except Exception as e:
        print(f"Error with Redis memory storage: {e}")
        print("Note: Redis may not be available in this environment")

    # Log execution timestamp
    print("\n=== EXECUTION LOG ===")
    log_entry = f"Agent execution completed at {datetime.datetime.now().isoformat()}\n"
    
    # Append to execution log
    log_file = "/workspace/artifacts/generated/execution_log.log"
    try:
        with open(log_file, 'a') as f:
            f.write(log_entry)
        print(f"Logged execution timestamp to {log_file}")
    except Exception as e:
        print(f"Error writing to log file: {e}")

    print("\n=== TEST COMPLETED ===")

if __name__ == "__main__":
    main()