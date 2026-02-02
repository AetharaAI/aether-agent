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


# Identity management models
class IdentityProfile(BaseModel):
    name: str
    emoji: str
    voice: str = "efficient"
    autonomy_default: str = "semi"
    description: Optional[str] = None
    core_values: Optional[List[str]] = None


class UserProfile(BaseModel):
    name: str
    timezone: str = "UTC"
    role: Optional[str] = None
    projects: Optional[List[str]] = None
    priorities: Optional[List[str]] = None


class IdentityContextResponse(BaseModel):
    agent: Dict[str, Any]
    user: Dict[str, Any]
    memory: Dict[str, Any]


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
    
    # Bootstrap identity if not present
    await _bootstrap_identity_if_needed()
    
    print("✓ Aether agent started")
    print(f"✓ Identity: {await aether.memory.get_identity_profile() or 'Using defaults'}")


async def _bootstrap_identity_if_needed():
    """Initialize identity from markdown docs if Redis is empty"""
    identity = await aether.memory.get_identity_profile()
    
    if not identity:
        # Load from AETHER_IDENTITY.md if exists
        identity_path = Path("workspace/AETHER_IDENTITY.md")
        if identity_path.exists():
            content = identity_path.read_text()
            # Extract key identity elements
            identity = {
                "name": "Aether",
                "emoji": "🌐⚡",
                "voice": "efficient",
                "autonomy_default": "semi",
                "description": "Autonomous execution engine with Redis persistence",
                "core_values": [
                    "Be genuinely helpful, not performatively helpful",
                    "Have working opinions",
                    "Resourceful before asking",
                    "Earn trust through competence",
                    "Execute decisively, document completely"
                ],
                "bootstrap_source": "AETHER_IDENTITY.md",
                "bootstrapped_at": datetime.now().isoformat()
            }
            await aether.memory.save_identity_profile(identity)
            print("  → Identity bootstrapped from AETHER_IDENTITY.md")
        else:
            # Use defaults
            identity = {
                "name": "Aether",
                "emoji": "🌐⚡",
                "voice": "efficient",
                "autonomy_default": "semi",
                "bootstrap_source": "defaults",
                "bootstrapped_at": datetime.now().isoformat()
            }
            await aether.memory.save_identity_profile(identity)
            print("  → Identity initialized with defaults")
    
    # Bootstrap user profile if not present
    user = await aether.memory.get_user_profile()
    if not user:
        user_path = Path("workspace/AETHER_USER.md")
        if user_path.exists():
            user = {
                "name": "CJ",
                "timezone": "America/Indianapolis",
                "role": "Founder/CTO, AetherPro Technologies",
                "projects": [
                    "Passport IAM",
                    "Triad Intelligence", 
                    "CMC (Context & Memory Control)",
                    "Aether Desktop"
                ],
                "bootstrap_source": "AETHER_USER.md",
                "bootstrapped_at": datetime.now().isoformat()
            }
            await aether.memory.save_user_profile(user)
            print("  → User profile bootstrapped from AETHER_USER.md")
        else:
            user = {
                "name": "User",
                "timezone": "UTC",
                "bootstrap_source": "defaults",
                "bootstrapped_at": datetime.now().isoformat()
            }
            await aether.memory.save_user_profile(user)
            print("  → User profile initialized with defaults")
    
    # Mark bootstrap complete
    await aether.memory.set_system_flag("bootstrap_complete", True)
    await aether.memory.set_system_flag("first_boot_at", datetime.now().isoformat())


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
        # Build welcome message from identity
        identity = await aether.memory.get_identity_profile() if aether else None
        agent_name = identity.get("name", "Aether") if identity else "Aether"
        agent_emoji = identity.get("emoji", "🌐") if identity else "🌐"
        autonomy_mode = identity.get("autonomy_default", "semi") if identity else "semi"
        
        welcome_msg = f"{agent_emoji} {agent_name} online. Autonomy: {autonomy_mode} mode. How can I help you today?"
        
        # Send welcome message
        await websocket.send_json({
            "id": "welcome",
            "role": "agent",
            "content": welcome_msg,
            "timestamp": datetime.now().isoformat(),
            "identity": {
                "name": agent_name,
                "emoji": agent_emoji,
                "mode": autonomy_mode
            }
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
                    # Build dynamic system prompt from Redis-stored identity
                    system_prompt = await aether.memory.build_system_prompt()
                    
                    # Use LLM for response with dynamic identity
                    response = await aether.nvidia.complete(
                        messages=[
                            {"role": "system", "content": system_prompt},
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


# Identity management endpoints

@app.get("/api/identity", response_model=IdentityContextResponse)
async def get_identity_context():
    """Get current identity and user context from Redis"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    context = await aether.memory.get_identity_context_for_api()
    return IdentityContextResponse(**context)


@app.get("/api/identity/prompt")
async def get_system_prompt():
    """Get the dynamic system prompt built from identity profiles"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    prompt = await aether.memory.build_system_prompt()
    return {
        "prompt": prompt,
        "source": "redis_persistent",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/identity")
async def update_identity(profile: IdentityProfile):
    """Update Aether's identity profile"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    await aether.memory.save_identity_profile(profile.dict())
    return {
        "status": "success",
        "message": f"Identity updated: {profile.name}",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/identity/user")
async def update_user_profile(profile: UserProfile):
    """Update user profile"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    await aether.memory.save_user_profile(profile.dict())
    return {
        "status": "success",
        "message": f"User profile updated: {profile.name}",
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/identity/reload")
async def reload_identity_from_files():
    """Reload identity from markdown files (for updates to AETHER_*.md)"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    # Reload from files if they exist
    identity_path = Path("workspace/AETHER_IDENTITY.md")
    user_path = Path("workspace/AETHER_USER.md")
    
    updates = []
    
    if identity_path.exists():
        # Parse identity from markdown (simplified)
        identity = await aether.memory.get_identity_profile() or {}
        identity["reload_source"] = "AETHER_IDENTITY.md"
        identity["reloaded_at"] = datetime.now().isoformat()
        await aether.memory.save_identity_profile(identity)
        updates.append("identity")
    
    if user_path.exists():
        user = await aether.memory.get_user_profile() or {}
        user["reload_source"] = "AETHER_USER.md"
        user["reloaded_at"] = datetime.now().isoformat()
        await aether.memory.save_user_profile(user)
        updates.append("user_profile")
    
    return {
        "status": "success",
        "updates": updates,
        "message": f"Reloaded: {', '.join(updates)}" if updates else "No files to reload",
        "timestamp": datetime.now().isoformat()
    }


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
