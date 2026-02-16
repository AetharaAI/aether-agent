
"""
aether/prototypes/mongo_registry.py

Prototype implementation of a MongoDB-backed Tool Registry.
This allows tools to be dynamically loaded from a database, reducing context window usage.
"""

import asyncio
import importlib
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

# Mocking motor for prototype if not installed, but designed for motor
try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    class MockClient:
        def __init__(self, url): pass
        def __getitem__(self, key): return self
    AsyncIOMotorClient = MockClient

from aether.tools.registry import ToolRegistry, Tool, ToolPermission, ToolResult

logger = logging.getLogger("aether.tools.mongo")

@dataclass
class MongoToolDefinition:
    """Represents a tool stored in MongoDB"""
    name: str
    description: str
    permission: str
    parameters: Dict[str, Any]
    handler_path: str  # e.g., "aether.tools.core_tools.FileWriteTool"
    enabled: bool = True
    tags: List[str] = field(default_factory=list)

class MongoToolRegistry(ToolRegistry):
    """
    Registry that loads tools from MongoDB on demand.
    
    Hybrid Approach:
    - Core tools (internal) are always loaded in memory.
    - Extended tools are searched and loaded dynamically for specific turns.
    """
    
    def __init__(self, mongo_url: str, db_name: str = "aether_agent", collection: str = "tools", memory=None):
        super().__init__(memory=memory)
        self.mongo_url = mongo_url
        self.db_name = db_name
        self.collection_name = collection
        self.client = None
        self.db = None
        self.collection = None
        
    async def connect(self):
        """Connect to MongoDB"""
        if AsyncIOMotorClient:
            self.client = AsyncIOMotorClient(self.mongo_url)
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            logger.info(f"Connected to MongoDB: {self.db_name}.{self.collection_name}")
        else:
            logger.warning("Motor not installed, running in mock mode")

    async def search_tools(self, query: str, limit: int = 5) -> List[MongoToolDefinition]:
        """
        Search for tools in MongoDB using text search or regex.
        This allows the agent to 'find' tools it needs.
        """
        if not self.collection:
            return []
            
        # Text search (requires index) or regex fallback
        try:
            # Prototype note: using regex for simplicity without index setup
            cursor = self.collection.find(
                {
                    "$or": [
                        {"name": {"$regex": query, "$options": "i"}},
                        {"description": {"$regex": query, "$options": "i"}},
                        {"tags": {"$in": [query]}}
                    ],
                    "enabled": True
                }
            ).limit(limit)
            results = await cursor.to_list(length=limit)
        except Exception as e:
            logger.error(f"Search failed: {e}")
            results = []
            
        tools = []
        for doc in results:
            tools.append(MongoToolDefinition(
                name=doc["name"],
                description=doc["description"],
                permission=doc["permission"],
                parameters=doc["parameters"],
                handler_path=doc["handler_path"],
                enabled=doc["enabled"],
                tags=doc.get("tags", [])
            ))
        return tools

    async def load_tool_from_definition(self, definition: MongoToolDefinition) -> Optional[Tool]:
        """
        Dynamically import and instantiate a tool from its definition.
        """
        try:
            module_name, class_name = definition.handler_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            tool_class = getattr(module, class_name)
            
            # Instantiate tool
            # Note: Complex tools might need dependency injection (memory, runtime)
            # This prototype assumes simple init or factory pattern would be needed
            # For prototype, assume no-arg init or skip injection
            tool_instance = tool_class() 
            
            return tool_instance
        except Exception as e:
            logger.error(f"Failed to load tool {definition.name}: {e}")
            return None

    async def register_dynamic_tool(self, tool_name: str) -> bool:
        """
        Load a specific tool from Mongo by name and register it to memory.
        """
        if not self.collection:
            return False
            
        doc = await self.collection.find_one({"name": tool_name, "enabled": True})
        if not doc:
            return False
            
        def_ = MongoToolDefinition(
            name=doc["name"],
            description=doc["description"],
            permission=doc["permission"],
            parameters=doc["parameters"],
            handler_path=doc["handler_path"]
        )
        
        tool = await self.load_tool_from_definition(def_)
        if tool:
            self.register(tool)
            return True
        return False

# ==========================================
# Agent Tool Exposing the Registry
# ==========================================

class SearchToolsTool(Tool):
    """
    The meta-tool that allows the agent to find other tools.
    """
    name = "search_tools"
    description = "Search for available tools to help with your task. Use this when you don't have a tool for what you need."
    permission = ToolPermission.INTERNAL
    parameters = {
        "query": {
            "type": "string",
            "description": "What you want to do (e.g., 'edit file', 'search web', 'manage docker')",
            "required": True
        }
    }
    
    def __init__(self, mongo_registry: MongoToolRegistry):
        self._registry = mongo_registry # Fixed attribute name to match standard pattern

    async def execute(self, query: str) -> ToolResult:
        tools = await self._registry.search_tools(query)
        
        if not tools:
            return ToolResult(success=True, data={"message": "No tools found matching query.", "tools": []})
            
        return ToolResult(
            success=True,
            data={
                "found": len(tools),
                "tools": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "permission": t.permission,
                        "parameters": t.parameters
                    }
                    for t in tools
                ],
                "instruction": "To use these tools, just ask to use them. I will load them for you."
            }
        )
