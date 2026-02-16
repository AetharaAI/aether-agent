
"""
aether/prototypes/demo_mongo_tools.py

Demonstrate dynamic tool loading with mocked MongoDB.
"""

import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock

# Add project root to path
sys.path.append(os.getcwd())

# Mock motor before import
sys.modules["motor"] = MagicMock()
sys.modules["motor.motor_asyncio"] = MagicMock()

# Mock tool classes so we don't need real dependencies
class MockFileWriteTool:
    name = "file_write"
    description = "Write content to a file"
    permission = "semi"
    parameters = {"path": {}, "content": {}}
    async def execute(self, **kwargs): return {"success": True}

class MockDockerRunTool:
    name = "docker_run"
    description = "Run a docker container"
    permission = "auto"
    parameters = {"image": {}, "command": {}}
    async def execute(self, **kwargs): return {"success": True}

# Inject mocks into sys.modules so importlib works
sys.modules["aether.tools.core_tools"] = MagicMock()
sys.modules["aether.tools.core_tools"].FileWriteTool = MockFileWriteTool
sys.modules["aether.tools.docker"] = MagicMock()
sys.modules["aether.tools.docker"].DockerRunTool = MockDockerRunTool

from aether.prototypes.mongo_registry import MongoToolRegistry, SearchToolsTool

async def main():
    print("Initializing MongoDB Tool Registry Prototype...")
    
    # 1. Setup Registry
    registry = MongoToolRegistry("mongodb://localhost:27017")
    
    # 2. Mock MongoDB Collection
    mock_collection = MagicMock() # Use MagicMock for the collection itself
    registry.collection = mock_collection
    
    # Mock Data in "Database"
    TOOLS_DB = [
        {
            "name": "file_write",
            "description": "Write content to a file",
            "permission": "semi",
            "parameters": {"path": "str", "content": "str"},
            "handler_path": "aether.tools.core_tools.FileWriteTool",
            "enabled": True,
            "tags": ["filesystem", "io"]
        },
        {
            "name": "docker_run",
            "description": "Run a docker container",
            "permission": "auto",
            "parameters": {"image": "str"},
            "handler_path": "aether.tools.docker.DockerRunTool",
            "enabled": True,
            "tags": ["docker", "container", "devops"]
        },
         {
            "name": "random_tool",
            "description": "Something unused",
            "permission": "internal",
            "parameters": {},
            "handler_path": "aether.tools.misc.RandomTool",
            "enabled": True,
            "tags": ["misc"]
        }
    ]
    
    # Setup Search Mock
    
    def mock_find(query, *args, **kwargs):
        # Determine matches based on query
        matches = []
        term = ""
        
        # Regex search simulation
        if "$or" in query:
             # Extract search term for demo purposes. 
            try:
                term = query['$or'][0]['name']['$regex']
                matches = [
                    t for t in TOOLS_DB 
                    if term.lower() in t["name"] or term.lower() in t["description"] or term.lower() in range(len(t["tags"])) and term.lower() in t["tags"]
                ]
                # Fix tag search logic for demo
                matches = [
                    t for t in TOOLS_DB 
                    if term.lower() in t["name"] or term.lower() in t["description"] or any(term.lower() in tag for tag in t["tags"])
                ]
            except:
                pass
        
        print(f"  [DB] Searching for '{term}'... found {len(matches)}")

        # Create the cursor mock chain
        # find() returns cursor -> cursor.limit() returns cursor -> cursor.to_list() returns [docs]
        # IMPORANT: find() is synchronous in Motor, but to_list is async.
        
        mock_cursor = MagicMock()
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=matches)
        
        return mock_cursor

    mock_collection.find.side_effect = mock_find
    
    # Mock find_one (Async in Motor)
    async def mock_find_one(query, *args, **kwargs):
        name = query.get("name")
        print(f"  [DB] Fetching tool definition: {name}")
        for t in TOOLS_DB:
            if t["name"] == name:
                return t
        return None
    mock_collection.find_one = AsyncMock(side_effect=mock_find_one)
    
    # 3. Create the Search Tool (this is the only tool the agent needs initially)
    search_tool = SearchToolsTool(registry)
    
    print("\n--- SCENARIO 1: Agent wants to manage files ---")
    print("Agent: 'I need to write a file. Checking tools...'")
    
    result = await search_tool.execute("file")
    print(f"Result: Found {result.data.get('found', 0)} tools")
    if result.data.get('tools'):
        for t in result.data['tools']:
            print(f"  - {t['name']}: {t['description']}")
        
    print("\n--- SCENARIO 2: Agent wants to run docker ---")
    print("Agent: 'I need to run a container. Checking tools...'")
    
    result = await search_tool.execute("container")
    print(f"Result: Found {result.data.get('found', 0)} tools")
    if result.data.get('tools'):
        for t in result.data['tools']:
            print(f"  - {t['name']}: {t['description']}")
        
    print("\n--- SCENARIO 3: Agent searches for something that doesn't exist ---")
    print("Agent: 'I need to fly a kite.'")
    
    result = await search_tool.execute("kite")
    print(f"Result: {result.data.get('message', 'No message')}")
    
    print("\n--- REGISTRY STATE Check ---")
    print(f"Tools loaded in memory: {len(registry._tools)}")
    print(f"Tools: {list(registry._tools.keys())}")

if __name__ == "__main__":
    asyncio.run(main())
