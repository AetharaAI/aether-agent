import sys
import os

# Ensure current directory is in path
sys.path.append(os.getcwd())

print("Attempting to import aether.api_server...")
try:
    from aether.api_server import app
    print("Successfully imported app")
except Exception as e:
    print(f"Failed to import app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

import uvicorn

if __name__ == "__main__":
    try:
        print("Starting uvicorn on port 8001...")
        uvicorn.run(app, host="0.0.0.0", port=8001)
    except Exception as e:
        print(f"Failed to run uvicorn: {e}")
        import traceback
        traceback.print_exc()
