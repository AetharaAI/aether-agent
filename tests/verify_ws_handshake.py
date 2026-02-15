
import asyncio
import websockets
import json
import uuid

async def verify_handshake():
    session_id = str(uuid.uuid4())
    url = f"ws://localhost:16399/ws/agent/{session_id}"
    print(f"Connecting to {url}...")
    
    try:
        async with websockets.connect(url) as websocket:
            print("✓ WebSocket connection established!")
            
            # Wait for session_started event
            response = await websocket.recv()
            event = json.loads(response)
            print(f"Received event: {event.get('event_type')}")
            
            if event.get("event_type") == "session_started":
                print("✓ session_started event received successfully!")
                return True
            else:
                print(f"✗ Unexpected event type: {event.get('event_type')}")
                return False
                
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(verify_handshake())
    if success:
        print("\nVerification SUCCESSFUL")
        exit(0)
    else:
        print("\nVerification FAILED")
        exit(1)
