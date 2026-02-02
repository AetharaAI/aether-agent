"""
Aether API Server

FastAPI server that exposes Aether agent capabilities via REST and WebSocket APIs.
Connects the web UI to the Aether core engine.
"""

import asyncio
import json
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from .aether_core import AetherCore, AgentConfig
from .aether_memory import MemoryEntry
from .nvidia_kit import NVIDIAKit


# Pydantic models for API
class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    mode: Optional[str] = "semi"  # semi or auto


class ChatResponse(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str


class ContextStats(BaseModel):
    usage_percent: float
    daily_logs_count: int
    longterm_memory_size: int
    checkpoints_count: int


class AgentStatus(BaseModel):
    running: bool
    mode: str  # semi or auto
    context_usage: float
    uptime: int


class CheckpointRequest(BaseModel):
    name: Optional[str] = None


class CheckpointResponse(BaseModel):
    id: str
    name: str
    timestamp: str


# Initialize FastAPI app
app = FastAPI(title="Aether API", version="1.0.0")

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Aether instance
aether: Optional[AetherCore] = None
active_connections: List[WebSocket] = []


@app.on_event("startup")
async def startup_event():
    """Initialize Aether agent on startup"""
    global aether
    
    config = AgentConfig(
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        nvidia_api_key=os.getenv("NVIDIA_API_KEY", ""),
        autonomy_mode="semi",
        fleet_api_url=os.getenv("FLEET_API_URL", ""),
        fleet_api_key=os.getenv("FLEET_API_KEY", ""),
    )
    
    aether = AetherCore(config)
    await aether.start()
    print("✓ Aether agent started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global aether
    if aether:
        await aether.stop()
    print("✓ Aether agent stopped")


# REST API Endpoints

@app.get("/api/status", response_model=AgentStatus)
async def get_status():
    """Get agent status"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    stats = await aether.memory.get_memory_stats()
    
    return AgentStatus(
        running=aether.running,
        mode=aether.autonomy.mode,
        context_usage=stats.get("context_usage_percent", 0),
        uptime=int((datetime.now() - aether.start_time).total_seconds()) if hasattr(aether, "start_time") else 0,
    )


@app.get("/api/context/stats", response_model=ContextStats)
async def get_context_stats():
    """Get context/memory statistics"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    stats = await aether.memory.get_memory_stats()
    
    return ContextStats(
        usage_percent=stats.get("context_usage_percent", 0),
        daily_logs_count=stats.get("daily_logs_count", 0),
        longterm_memory_size=stats.get("longterm_memory_size", 0),
        checkpoints_count=stats.get("checkpoints_count", 0),
    )


@app.post("/api/context/compress")
async def compress_context():
    """Compress context by migrating daily logs to long-term memory"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    # Trigger memory migration
    await aether.memory.migrate_daily_to_longterm()
    
    return {"status": "success", "message": "Context compressed"}


@app.post("/api/checkpoint", response_model=CheckpointResponse)
async def create_checkpoint(request: CheckpointRequest):
    """Create a memory checkpoint"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    checkpoint_id = await aether.memory.checkpoint_snapshot(request.name)
    
    return CheckpointResponse(
        id=checkpoint_id,
        name=request.name or "Unnamed checkpoint",
        timestamp=datetime.now().isoformat(),
    )


@app.post("/api/mode/{mode}")
async def set_mode(mode: str):
    """Set agent autonomy mode (semi or auto)"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if mode not in ["semi", "auto"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'semi' or 'auto'")
    
    aether.autonomy.mode = mode
    
    return {"status": "success", "mode": mode}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file for the agent to process"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    # Save file to temporary location
    upload_dir = Path("/tmp/aether_uploads")
    upload_dir.mkdir(exist_ok=True)
    
    file_path = upload_dir / file.filename
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {
        "status": "success",
        "filename": file.filename,
        "path": str(file_path),
        "size": len(content),
    }


# WebSocket endpoint for real-time chat

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with agent"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        # Send welcome message
        await websocket.send_json({
            "id": "welcome",
            "role": "agent",
            "content": "Hello! I'm Aether, your semi-autonomous AI assistant. How can I help you today?",
            "timestamp": datetime.now().isoformat(),
        })
        
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message = data.get("message", "")
            
            if not message:
                continue
            
            # Echo user message back
            await websocket.send_json({
                "id": f"user-{datetime.now().timestamp()}",
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat(),
            })
            
            # Process message with Aether
            if aether:
                try:
                    # Use LLM for response
                    response = await aether.nvidia.complete(
                        messages=[
                            {"role": "system", "content": "You are Aether, a helpful AI assistant."},
                            {"role": "user", "content": message},
                        ],
                        temperature=0.7,
                    )
                    
                    # Send agent response
                    await websocket.send_json({
                        "id": f"agent-{datetime.now().timestamp()}",
                        "role": "agent",
                        "content": response.content,
                        "timestamp": datetime.now().isoformat(),
                    })
                    
                    # Log to memory
                    await aether.memory.log_daily(
                        f"User: {message}\nAgent: {response.content}",
                        tags=["chat", "ui"],
                    )
                    
                except Exception as e:
                    await websocket.send_json({
                        "id": f"error-{datetime.now().timestamp()}",
                        "role": "agent",
                        "content": f"Sorry, I encountered an error: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    })
            else:
                await websocket.send_json({
                    "id": f"agent-{datetime.now().timestamp()}",
                    "role": "agent",
                    "content": "Agent not initialized. Please check server configuration.",
                    "timestamp": datetime.now().isoformat(),
                })
    
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
        if websocket in active_connections:
            active_connections.remove(websocket)


# Terminal command endpoint

@app.post("/api/terminal/execute")
async def execute_terminal_command(command: dict):
    """Execute a terminal command through Aether"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    cmd = command.get("command", "")
    
    if not cmd:
        raise HTTPException(status_code=400, detail="No command provided")
    
    # For demo, return simulated output
    # In production, this would execute actual commands via OpenClaw tools
    
    output = {
        "command": cmd,
        "output": f"Executed: {cmd}\n✓ Command completed successfully",
        "exit_code": 0,
        "timestamp": datetime.now().isoformat(),
    }
    
    return output


# Health check

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent_running": aether.running if aether else False,
        "timestamp": datetime.now().isoformat(),
    }


# Run server

def start_server(host: str = "0.0.0.0", port: int = 8000):
    """Start the API server"""
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    start_server()
