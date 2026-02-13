
import sys
import os
sys.path.append(os.getcwd())

try:
    from aether.tools.registry import Tool, ToolPermission, ToolRegistry, Capability
    from aether.tools.lsp.manager import LSPManager
    from aether.tools.lsp_tools import LSPToolIntegration
    
    print("Imports successful")
    
    # Mock workspace
    manager = LSPManager(".")
    integration = LSPToolIntegration(manager)
    registry = ToolRegistry()
    
    print("Registering tools...")
    integration.register_tools(registry)
    print("Registration successful")
    
    for tool in registry.list_tools():
        print(f"Registered tool: {tool['name']}")

except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Error: {e}")
