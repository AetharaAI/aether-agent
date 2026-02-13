
import asyncio
import os
import sys
from pprint import pprint

# Add project root to path
sys.path.append(os.getcwd())

import importlib.util
spec = importlib.util.spec_from_file_location("fabric_client", os.path.join(os.getcwd(), "aether/fabric_client.py"))
fabric_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fabric_client)
FabricClient = fabric_client.FabricClient
FabricConfig = fabric_client.FabricConfig

async def test_fabric_integration():
    print("Testing Fabric Integration...")
    
    # Check config
    config = FabricConfig.from_env()
    print(f"URL: {config.base_url}")
    print(f"Auth Token set: {'Yes' if config.auth_token else 'No'}")
    
    try:
        async with FabricClient(config) as client:
            # 1. Health Check
            print("\n1. Health Check:")
            try:
                health = await client.health_check()
                print(f"   Status: {health}")
            except Exception as e:
                print(f"   Failed: {e}")
            
            # 2. List Tools
            print("\n2. Listing Tools:")
            try:
                tools_response = await client.list_tools()
                # Handle response shape
                tools = []
                if isinstance(tools_response, list):
                    tools = tools_response
                elif isinstance(tools_response, dict):
                    tools = tools_response.get("tools", [])
                
                print(f"   Found {len(tools)} tools")
                for tool in tools:
                    print(f"   - {tool.get('id', 'unknown')}: {tool.get('description', '')[:50]}...")
            except Exception as e:
                print(f"   Failed: {e}")

            # 3. Test Math (if available)
            print("\n3. Testing Math Tool (Calculate):")
            try:
                result = await client.calculate("5 + 5")
                print(f"   5 + 5 = {result}")
            except Exception as e:
                print(f"   Failed: {e}")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_fabric_integration())
