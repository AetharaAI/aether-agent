import sys
import os

# Add current directory to path so we can import aether
sys.path.append(os.getcwd())

from aether.api_server import app

print("Registered Routes:")
for route in app.routes:
    methods = ", ".join(route.methods) if hasattr(route, "methods") else "None"
    print(f"{methods} {route.path}")
