"""
Aether API Server

================================================================================
ARCHITECTURE: API Gateway Layer
================================================================================

FastAPI server that exposes Aether agent capabilities via REST and WebSocket.
Serves as the bridge between the web UI and the Aether core engine.

EXPOSED LAYERS:
- Identity Layer: GET/POST /api/identity, /api/identity/user
- Memory Layer: POST /api/checkpoint
- Context Layer: GET /api/context/stats, POST /api/context/compress
- Provider Layer: (Future) /api/providers/* for model switching
- Tool Layer: POST /api/terminal/execute, /api/upload

ENDPOINTS:
REST:
  - /api/status              Agent status and health
  - /api/context/stats       Memory usage with byte-level breakdown
  - /api/context/compress    Trigger memory compression
  - /api/checkpoint          Create memory checkpoint
  - /api/mode/{mode}         Switch autonomy mode
  - /api/upload              File upload endpoint
  - /api/terminal/execute    Terminal command execution
  - /api/identity/*          Identity management

WebSocket:
  - /ws/agent/{session_id}   Event-driven agent runtime

STARTUP NOTES:
- Logs dev memory mode warning for production awareness
- Bootstraps identity from markdown files if Redis empty
- Maintains backward compatibility with existing clients
================================================================================
"""

import logging
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import FastAPI, WebSocket, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from .aether_core import AetherCore, AgentConfig


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
    # Byte-level breakdown
    short_term_bytes: int = 0
    long_term_bytes: int = 0
    checkpoint_bytes: int = 0
    total_bytes: int = 0
    # Token counts from LiteLLM
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


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

# API Routers will be included after imports (see end of file)

# Global Aether instance
aether: Optional[AetherCore] = None
tool_registry = None
last_litellm_request: Optional[Dict[str, Any]] = None


def _get_live_litellm_meta() -> Dict[str, Any]:
    """Read latest request metadata from NVIDIAKit/LiteLLM integration."""
    global last_litellm_request

    if aether and getattr(aether, "nvidia", None):
        getter = getattr(aether.nvidia, "get_last_request_meta", None)
        if callable(getter):
            meta = getter()
            if meta:
                return meta

    if last_litellm_request:
        return last_litellm_request

    current_model = (
        getattr(getattr(aether, "nvidia", None), "config", None).model
        if aether and getattr(aether, "nvidia", None)
        else "unknown"
    )
    model_group = "vision_reasoning" if any(
        marker in (current_model or "").lower() for marker in ("vision", "vl", "mm", "omni")
    ) else "text_reasoning"
    return {
        "app": "aether-ui",
        "model": current_model,
        "model_group": model_group,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "spend": 0.0,
        "request_id": "pending",
        "timestamp": datetime.now().isoformat(),
        "headers_sent": {
            "x-litellm-app": "aether-ui",
            "x-litellm-tags": "aether-pro,production",
            "Content-Type": "application/json",
        },
    }


@app.on_event("startup")
async def startup_event():
    """Initialize Aether agent on startup"""
    global aether, tool_registry
    
    # Log memory mode warning for production awareness
    print("=" * 60)
    print("Aether Agent Starting...")
    print("=" * 60)
    print("⚠️  Running in dev memory mode — production requires vm.overcommit_memory=1")
    print("   To fix: echo 1 | sudo tee /proc/sys/vm/overcommit_memory")
    print("-" * 60)
    
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

    # Initialize tool registry and wire it into Agent Runtime V2 sessions
    from .tools import get_registry
    from .agent_websocket import get_agent_manager

    tool_registry = get_registry(memory=aether.memory)
    tool_registry.set_autonomy_mode(aether.autonomy.mode)
    print(f"  → Tool registry initialized with {len(tool_registry.list_tools())} tools")

    agent_manager = get_agent_manager()
    agent_manager.set_tool_registry(tool_registry)
    print(f"  → Agent Runtime V2 wired with {len(tool_registry.list_tools())} tools")

    # Initialize LSP Integration
    try:
        from aether.tools.lsp.manager import LSPManager
        from aether.tools.lsp_tools import LSPToolIntegration
        
        # Use project root as workspace
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        lsp_manager = LSPManager(project_root)
        lsp_integration = LSPToolIntegration(lsp_manager)
        lsp_integration.register_tools(tool_registry)
        print(f"  → LSP Integration initialized (Workspace: {project_root})")
    except Exception as e:
        print(f"  ⚠️  LSP Integration failed: {e}")
    
    # Dynamic Fabric Tool Discovery
    try:
        from .fabric_client import FabricClient
        from .tools.fabric_adapter import FabricTool
        
        print("  → Discovering Fabric MCP tools...")
        # Use a short timeout for discovery to not block startup if Fabric is down
        async with FabricClient() as client:
            try:
                # We need a list_tools capability on the Fabric side
                # Assuming 'fabric.tool.list' or similar exists as per fabric_client implementation
                fabric_tools_response = await client.list_tools()
                
                # Handle different potential response shapes
                tool_list = []
                if isinstance(fabric_tools_response, list):
                    tool_list = fabric_tools_response
                elif isinstance(fabric_tools_response, dict):
                    tool_list = fabric_tools_response.get("tools", [])
                
                count = 0
                for t_def in tool_list:
                    # Avoid duplicates
                    if not tool_registry.get(t_def.get("id")):
                        tool_registry.register(FabricTool(t_def))
                        count += 1
                
                print(f"  → Registered {count} Fabric tools dynamically")
                
            except Exception as e:
                error_msg = str(e)
                if "Unknown tool" in error_msg or "BAD_INPUT" in error_msg:
                    print(f"  ℹ️  Dynamic Fabric tool discovery not supported by server (using standard set)")
                else:
                    print(f"  ⚠️  Fabric tool discovery failed: {e}")
                
                print("  → Falling back to standard tool set...")
                # Fallback: Register known standard tools
                standard_tools = [
                    {"id": "web.brave_search", "description": "Search the web using Brave", "capabilities": ["search"], "parameters": {"type": "object", "properties": {"query": {"type": "string"}}}},
                    {"id": "io.read_file", "description": "Read file contents", "capabilities": ["read"], "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}},
                    {"id": "io.write_file", "description": "Write to file", "capabilities": ["write"], "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}},
                    {"id": "math.calculate", "description": "Evaluate math expression", "capabilities": ["eval"], "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}}},
                ]
                count = 0
                for t_def in standard_tools:
                    if not tool_registry.get(t_def["id"]):
                        tool_registry.register(FabricTool(t_def))
                        count += 1
                print(f"  → Registered {count} standard Fabric tools")
                
    except Exception as e:
        print(f"  ⚠️  Fabric integration skipped: {e}")

    print("=" * 60)
    print("✓ Aether agent started successfully")
    print(f"✓ Identity: {await aether.memory.get_identity_profile() or 'Using defaults'}")
    
    # Fetch models from LiteLLM
    models = await _fetch_models_from_litellm()
    if models and aether and getattr(aether, "nvidia", None):
        available_ids = {m.id for m in models}
        current_model = getattr(aether.nvidia.config, "model", "")
        if current_model and current_model not in available_ids:
            replacement = models[0].id
            for candidate in models:
                aether.nvidia.config.model = candidate.id
                if await aether.nvidia.health_check():
                    replacement = candidate.id
                    break
            print(
                f"⚠️  Active model '{current_model}' not present on LiteLLM; "
                f"switching to '{replacement}'"
            )
            aether.nvidia.config.model = replacement

    print(f"✓ Available models: {len(models)}")
    for m in models:
        print(f"  - {m.id} ({m.model_group})")
    
    print("=" * 60)


def _parse_user_profile_from_markdown(content: str) -> Dict[str, Any]:
    """
    Parse AETHER_USER.md to extract comprehensive user profile.
    
    Extracts all relevant details including titles, background, projects,
    working style, and preferences from the markdown content.
    """
    user = {
        "name": "CJ",
        "timezone": "America/Indianapolis",
        "bootstrap_source": "AETHER_USER.md",
    }
    
    # Extract title
    title_match = content.split("**Title:**")
    if len(title_match) > 1:
        title_line = title_match[1].split("\n")[0].strip()
        user["title"] = title_line
    else:
        user["title"] = "Founder, Owner, CEO, CTO — AetherPro Technologies"
    
    # Extract pronouns
    pronouns_match = content.split("**Pronouns:**")
    if len(pronouns_match) > 1:
        pronouns = pronouns_match[1].split("\n")[0].strip()
        user["pronouns"] = pronouns
    
    # Extract timezone
    tz_match = content.split("**Timezone:**")
    if len(tz_match) > 1:
        tz_line = tz_match[1].split("\n")[0].strip()
        user["timezone"] = tz_line.split("(")[0].strip()
        # Extract location if available
        if "(" in tz_line and ")" in tz_line:
            location = tz_line.split("(")[1].split(")")[0].strip()
            user["location"] = location
    
    # Extract background
    background_section = content.split("**Background:**")
    if len(background_section) > 1:
        background_lines = []
        for line in background_section[1].split("\n"):
            if line.strip().startswith("-"):
                background_lines.append(line.strip()[1:].strip())
            elif line.strip() and not line.strip().startswith("#"):
                continue
            else:
                break
        user["background"] = background_lines
    
    # Extract projects from Active Projects section
    projects = []
    projects_section = content.split("## Active Projects")
    if len(projects_section) > 1:
        # Look for project names (### headings)
        for line in projects_section[1].split("\n"):
            if line.strip().startswith("###"):
                project_name = line.strip().replace("###", "").strip().split("🔐")[0].split("🧠")[0].split("📊")[0].split("🖥️")[0].strip()
                if project_name:
                    projects.append(project_name)
    user["projects"] = projects if projects else [
        "Passport IAM",
        "Triad Intelligence",
        "CMC (Context & Memory Control)",
        "Aether Desktop"
    ]
    
    # Extract communication preferences
    comm_section = content.split("## Communication Preferences")
    if len(comm_section) > 1:
        comm_text = comm_section[1].split("##")[0]
        user["communication_preferences"] = {
            "address_as": "CJ",
            "style": "Direct, technical, efficient",
            "detail_level": "Deep when requested, summaries by default"
        }
    
    # Extract working style preferences
    working_section = content.split("## Working Style")
    if len(working_section) > 1:
        appreciates = []
        appreciates_section = working_section[1].split("**Appreciates:**")
        if len(appreciates_section) > 1:
            for line in appreciates_section[1].split("\n"):
                if line.strip().startswith("-"):
                    appreciates.append(line.strip()[1:].strip())
                elif line.strip().startswith("**"):
                    break
        user["appreciates"] = appreciates
    
    # Extract strategic goals
    goals_section = content.split("## Strategic Goals")
    if len(goals_section) > 1:
        goals = []
        for line in goals_section[1].split("\n"):
            if line.strip().startswith("\d."):
                goal = line.strip()[2:].strip()
                goals.append(goal)
        user["strategic_goals"] = goals
    
    return user


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
            content = user_path.read_text()
            user = _parse_user_profile_from_markdown(content)
            user["bootstrapped_at"] = datetime.now().isoformat()
            await aether.memory.save_user_profile(user)
            print(f"  → User profile bootstrapped from AETHER_USER.md")
            print(f"    Name: {user.get('name')}")
            print(f"    Title: {user.get('title')}")
            print(f"    Background: {', '.join(user.get('background', [])[:2])}...")
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


@app.get("/api/debug/payload")
async def get_last_payload():
    """Get the last JSON payload sent to the LLM (for debugging)"""
    if not aether or not aether.nvidia:
        raise HTTPException(status_code=503, detail="Agent/LLM not initialized")
    
    payload = getattr(aether.nvidia, "_last_payload", None)
    if not payload:
        return {"message": "No requests made yet"}
        
    return payload


@app.get("/api/context/stats", response_model=ContextStats)
async def get_context_stats():
    """Get context/memory statistics with real byte-level breakdown"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    stats = await aether.memory.get_memory_stats()

    # Pull live usage from latest model request metadata.
    litellm_meta = _get_live_litellm_meta()
    prompt_tokens = int(litellm_meta.get("prompt_tokens", 0) or 0)
    completion_tokens = int(litellm_meta.get("completion_tokens", 0) or 0)
    total_tokens = int(litellm_meta.get("total_tokens", 0) or 0)
    
    # Calculate percentage based on tokens (128k context window)
    max_tokens = 128000
    usage_percent = min((total_tokens / max_tokens) * 100, 100) if total_tokens > 0 else 0
    
    return ContextStats(
        usage_percent=usage_percent,
        daily_logs_count=stats.get("daily_logs_count", 0),
        longterm_memory_size=stats.get("longterm_size", 0),
        checkpoints_count=stats.get("checkpoints", 0),
        # Byte-level breakdown
        short_term_bytes=stats.get("short_term_bytes", 0),
        long_term_bytes=stats.get("long_term_bytes", 0),
        checkpoint_bytes=stats.get("checkpoint_bytes", 0),
        total_bytes=stats.get("total_bytes", 0),
        # Token counts
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
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
    global tool_registry
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    if mode not in ["semi", "auto"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'semi' or 'auto'")
    
    aether.autonomy.mode = mode
    if tool_registry:
        tool_registry.set_autonomy_mode(mode)
    
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
    
    # Detect mime type from content type or filename
    mime_type = file.content_type
    if not mime_type:
        # Guess from filename extension
        ext = Path(file.filename).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".json": "application/json",
            ".csv": "text/csv",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")
    
    return {
        "status": "success",
        "filename": file.filename,
        "path": str(file_path),
        "size": len(content),
        "mimeType": mime_type,
    }


# ==============================================================================
# NEW AGENT RUNTIME WEBSOCKET (Event-driven state machine)
# ==============================================================================

from .agent_websocket import get_agent_manager
from .file_api import router as file_router
from .tools_api import router as tools_router
from .agent_fleet_api import router as fleet_router
from .speechmatics_api import router as voice_router

# Include API routers (after imports)
app.include_router(file_router)
app.include_router(tools_router)
app.include_router(fleet_router)
app.include_router(voice_router)

@app.websocket("/ws/agent/{session_id}")
async def agent_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for Agent Runtime V2.

    Streams lifecycle and tool-execution events from the runtime:
    - state_changed
    - thinking_start
    - tool_call_start/tool_call_complete/tool_call_failed
    - response_chunk/response_complete
    """
    manager = get_agent_manager()
    await manager.handle_agent_session(websocket, session_id, aether.nvidia if aether else None)


@app.post("/ws/agent/{session_id}/approve")
async def approve_agent_action(session_id: str, approval: dict):
    """
    Legacy endpoint retained for backward compatibility.

    Agent Runtime V2 is model-directed and does not pause for manual approvals.
    """
    manager = get_agent_manager()
    approved = approval.get("approved", False)
    await manager.handle_approval(session_id, approved)
    
    return {
        "status": "success",
        "session_id": session_id,
        "approved": approved,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/ws/agent/{session_id}/state")
async def get_agent_state(session_id: str):
    """Get current state of agent runtime"""
    manager = get_agent_manager()
    runtime = manager.active_runtimes.get(session_id)
    
    if not runtime:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "state": runtime.state.value,
        "conversation_length": len(runtime.conversation_history),
        "queued_events": runtime.event_queue.qsize(),
        "timestamp": datetime.now().isoformat()
    }


# ==============================================================================
# Terminal WebSocket (Real-time sandboxed terminal)
# ==============================================================================

from .terminal_websocket import get_terminal_manager

@app.websocket("/ws/terminal/{session_id}")
async def terminal_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time terminal access.
    
    Provides a sandboxed bash shell inside a Docker container.
    Supports PTY for proper terminal emulation.
    """
    manager = get_terminal_manager()
    await manager.handle_terminal_session(websocket, session_id)


# ==============================================================================
# Browser WebSocket (Real-time browser automation)
# ==============================================================================

from .browser_websocket import get_browser_manager

@app.websocket("/ws/browser/{session_id}")
async def browser_websocket(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time browser automation.
    
    Provides Playwright-based browser control with:
    - Live screenshot streaming
    - Click navigation
    - Form input
    - Page navigation (back/forward/refresh)
    """
    manager = get_browser_manager()
    await manager.handle_browser_session(websocket, session_id)


# ==============================================================================
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


@app.get("/api/history")
async def get_history_list(limit: int = 20, offset: int = 0):
    """List past agent sessions."""
    from .database import db
    if not db.pool:
         return {"sessions": []}
         
    query = """
        SELECT session_id, start_time, metadata 
        FROM agent_sessions 
        ORDER BY start_time DESC 
        LIMIT $1 OFFSET $2
    """
    rows = await db.pool.fetch(query, limit, offset)
    rows = await db.pool.fetch(query, limit, offset)
    
    sessions = []
    for r in rows:
        meta = r["metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        if not isinstance(meta, dict):
            meta = {}
            
        sessions.append({
            "id": r["session_id"],
            "timestamp": r["start_time"].isoformat() if r["start_time"] else None,
            "title": meta.get("title", f"Session {r['session_id'][:8]}")
        })

    return {"sessions": sessions}

@app.get("/api/history/{session_id}")
async def get_history_detail(session_id: str):
    """Get details for a specific session."""
    from .database import db
    messages = await db.get_messages(session_id)
    return {
        "session_id": session_id,
        "messages": messages
    }


# Chat Session Management Endpoints

class ChatSession(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    is_active: bool = True


class ChatMessageEntry(BaseModel):
    id: str
    role: str
    content: str
    thinking: Optional[str] = None
    timestamp: str
    attachments: Optional[List[Dict]] = None


@app.get("/api/chat/sessions")
async def list_chat_sessions(limit: int = 50, offset: int = 0):
    """List all chat sessions with pagination."""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    sessions = await aether.memory.get_chat_sessions(limit=limit, offset=offset)
    return {
        "sessions": sessions,
        "total": len(sessions),
        "limit": limit,
        "offset": offset
    }


@app.post("/api/chat/sessions")
async def create_chat_session(title: Optional[str] = None):
    """Create a new chat session."""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    session_id = await aether.memory.create_chat_session(title or "New Chat")
    return {
        "id": session_id,
        "title": title or "New Chat",
        "created_at": datetime.now().isoformat(),
        "status": "created"
    }


@app.get("/api/chat/sessions/{session_id}")
async def get_chat_session(session_id: str):
    """Get a specific chat session with its messages."""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    session = await aether.memory.get_chat_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session


@app.get("/api/chat/sessions/{session_id}/messages")
async def get_chat_messages(session_id: str, limit: int = 100, offset: int = 0):
    """Get messages for a specific chat session."""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    messages = await aether.memory.get_chat_messages(session_id, limit=limit, offset=offset)
    return {
        "session_id": session_id,
        "messages": messages,
        "total": len(messages),
        "limit": limit,
        "offset": offset
    }


@app.post("/api/chat/sessions/{session_id}/messages")
async def add_chat_message(session_id: str, message: ChatMessageEntry):
    """Add a message to a chat session."""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    await aether.memory.add_chat_message(session_id, message.dict())
    return {"status": "success", "message_id": message.id}


@app.delete("/api/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session and all its messages."""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    await aether.memory.delete_chat_session(session_id)
    return {"status": "success", "message": f"Session {session_id} deleted"}


@app.post("/api/chat/search")
async def search_chat_history(query: str, limit: int = 20):
    """Search through all chat history for specific content."""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    results = await aether.memory.search_chat_history(query, limit=limit)
    return {
        "query": query,
        "results": results,
        "total": len(results)
    }


# Tool discovery endpoints

@app.get("/api/tools")
async def list_tools():
    """List all available tools with their metadata"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    from .tools import get_registry
    registry = get_registry(memory=aether.memory)
    tools = registry.list_tools()
    
    return {
        "tools": tools,
        "count": len(tools),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/tools/{tool_name}")
async def get_tool(tool_name: str):
    """Get details for a specific tool"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    from .tools import get_registry
    registry = get_registry(memory=aether.memory)
    tool = registry.get(tool_name)
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_name}")
    
    return {
        "tool": tool.to_dict(),
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/tools/execute/{tool_name}")
async def execute_tool(tool_name: str, params: Dict[str, Any]):
    """Execute a tool with given parameters"""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    from .tools import get_registry
    registry = get_registry(memory=aether.memory)
    
    # Get autonomy mode
    autonomy_mode = aether.autonomy.mode
    
    # Execute tool
    result = await registry.execute(
        tool_name,
        autonomy_mode=autonomy_mode,
        **params
    )
    
    return {
        "result": result.to_dict(),
        "timestamp": datetime.now().isoformat()
    }


# Models endpoint - fetch from LiteLLM

class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    model_group: str
    healthy: bool = True


class ModelSelectionRequest(BaseModel):
    model_id: str


# Cache for models fetched from LiteLLM
_available_models: List[ModelInfo] = []

async def _fetch_models_from_litellm() -> List[ModelInfo]:
    """Fetch available models from LiteLLM v1/models endpoint."""
    global _available_models
    
    try:
        import aiohttp
        
        litellm_base = os.getenv("LITELLM_MODEL_BASE_URL", "http://aether-gateway:4000")
        litellm_key = os.getenv("LITELLM_API_KEY", "")
        
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {litellm_key}",
                "x-litellm-app": "aether-ui",
                "x-litellm-tags": "aether-pro,production"
            }
            
            # Ensure we don't duplicate /v1 in the URL
            base_url = litellm_base.rstrip('/')
            if base_url.endswith('/v1'):
                models_url = f"{base_url}/models"
            else:
                models_url = f"{base_url}/v1/models"
            
            async with session.get(
                models_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    models = []
                    
                    for model in data.get("data", []):
                        model_id = model.get("id", "")
                        # Determine model group from id
                        model_group = "text_reasoning"
                        if "vision" in model_id.lower() or "vl" in model_id.lower():
                            model_group = "vision_reasoning"
                        elif "ocr" in model_id.lower():
                            model_group = "ocr_utility"
                        
                        models.append(ModelInfo(
                            id=model_id,
                            name=model.get("name", model_id),
                            provider="LiteLLM",
                            model_group=model_group,
                            healthy=True
                        ))
                    
                    _available_models = models
                    logger.info(f"Fetched {len(models)} models from LiteLLM")
                    return models
                else:
                    logger.warning(f"Failed to fetch models: {response.status}")
                    return _available_models
    
    except Exception as e:
        logger.error(f"Error fetching models from LiteLLM: {e}")
        # Return cached models or active runtime model as fallback
        if not _available_models:
            fallback_id = (
                os.getenv("LITELLM_MODEL_NAME")
                or (
                    getattr(getattr(aether, "nvidia", None), "config", None).model
                    if aether and getattr(aether, "nvidia", None)
                    else "unknown-model"
                )
            )
            fallback_group = (
                "vision_reasoning"
                if any(tag in fallback_id.lower() for tag in ("vision", "vl", "mm", "omni"))
                else "text_reasoning"
            )
            _available_models = [
                ModelInfo(
                    id=fallback_id,
                    name=fallback_id,
                    provider="LiteLLM",
                    model_group=fallback_group,
                ),
            ]
        return _available_models


async def _fetch_litellm_json(path_candidates: List[str]) -> Dict[str, Any]:
    """Fetch from the first LiteLLM metadata endpoint that responds successfully."""
    import aiohttp

    litellm_base = os.getenv("LITELLM_MODEL_BASE_URL", "").rstrip("/")
    litellm_key = os.getenv("LITELLM_API_KEY", "")
    if not litellm_base:
        return {"ok": False, "error": "LITELLM_MODEL_BASE_URL is not set"}

    headers = {
        "Authorization": f"Bearer {litellm_key}",
        "x-litellm-app": "aether-ui",
        "x-litellm-tags": "aether-pro,production",
    }

    attempted: List[Dict[str, Any]] = []

    async with aiohttp.ClientSession() as session:
        for raw_path in path_candidates:
            path = raw_path if raw_path.startswith("/") else f"/{raw_path}"
            candidates = [f"{litellm_base}{path}"]

            # If base already ends with /v1, try the root variant too for admin endpoints.
            if litellm_base.endswith("/v1"):
                root_base = litellm_base[: -len("/v1")]
                candidates.append(f"{root_base}{path}")

            for url in candidates:
                try:
                    async with session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10),
                    ) as response:
                        body_text = await response.text()
                        if response.status < 400:
                            try:
                                payload = json.loads(body_text) if body_text else {}
                            except json.JSONDecodeError:
                                payload = {"raw": body_text}
                            return {"ok": True, "url": url, "status": response.status, "data": payload}
                        attempted.append(
                            {"url": url, "status": response.status, "error": body_text[:500]}
                        )
                except Exception as exc:
                    attempted.append({"url": url, "status": 0, "error": str(exc)})

    return {"ok": False, "attempted": attempted}


@app.get("/api/models", response_model=List[ModelInfo])
async def list_models():
    """List available models from LiteLLM."""
    models = await _fetch_models_from_litellm()
    return models


@app.get("/api/litellm/meta")
async def get_litellm_meta():
    """
    Fetch live LiteLLM metadata from common admin/user endpoints.
    This is intended for runtime observability and UI diagnostics.
    """
    models_meta = await _fetch_litellm_json(["/models", "/v1/models"])
    user_meta = await _fetch_litellm_json(["/user/info", "/v1/user/info"])
    usage_meta = await _fetch_litellm_json(
        ["/global/spend", "/spend/logs", "/v1/spend/logs", "/usage", "/v1/usage"]
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "models": models_meta,
        "user": user_meta,
        "usage": usage_meta,
    }


@app.get("/api/models/current")
async def get_current_model():
    """Get the currently active model used by the backend runtime."""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    active_model = getattr(aether.nvidia.config, "model", "unknown")
    return {
        "model_id": active_model,
        "provider": getattr(aether.nvidia.config, "provider", "unknown"),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/models/select")
async def select_model(request: ModelSelectionRequest):
    """Select active model for subsequent runtime requests."""
    if not aether:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    models = await _fetch_models_from_litellm()
    model_ids = {m.id for m in models}
    if request.model_id not in model_ids:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Model '{request.model_id}' is not currently available on LiteLLM. "
                "Call /api/models to refresh the active list."
            ),
        )

    previous_model = getattr(aether.nvidia.config, "model", "unknown")
    aether.nvidia.config.model = request.model_id
    is_healthy = await aether.nvidia.health_check()
    logger.info("Active model switched: %s -> %s", previous_model, request.model_id)

    return {
        "status": "success",
        "previous_model": previous_model,
        "active_model": request.model_id,
        "healthy": is_healthy,
        "timestamp": datetime.now().isoformat(),
    }


# Debug/LiteLLM metadata endpoint

class LiteLLMDebugInfo(BaseModel):
    app: str
    provider: str
    model: str
    model_group: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    spend: float
    request_id: str
    timestamp: str
    headers_sent: Dict[str, str]
    error: Optional[str] = None

@app.get("/api/debug/litellm", response_model=LiteLLMDebugInfo)
async def get_litellm_debug_info():
    """
    Get debug information about the last LiteLLM request.
    Shows metadata including headers sent, model used, tokens consumed, and spend.
    """
    litellm_meta = _get_live_litellm_meta()

    return LiteLLMDebugInfo(
        app=litellm_meta.get("app", "aether-ui"),
        provider=litellm_meta.get("provider", getattr(getattr(aether, "nvidia", None), "config", None).provider if aether and getattr(aether, "nvidia", None) else "unknown"),
        model=litellm_meta.get("model", "unknown"),
        model_group=litellm_meta.get("model_group", "unknown"),
        prompt_tokens=int(litellm_meta.get("prompt_tokens", 0) or 0),
        completion_tokens=int(litellm_meta.get("completion_tokens", 0) or 0),
        total_tokens=int(litellm_meta.get("total_tokens", 0) or 0),
        spend=float(litellm_meta.get("spend", 0.0) or 0.0),
        request_id=litellm_meta.get("request_id", "unknown"),
        timestamp=litellm_meta.get("timestamp", datetime.now().isoformat()),
        headers_sent=litellm_meta.get("headers_sent", {}),
        error=litellm_meta.get("error"),
    )


@app.post("/api/debug/litellm/update")
async def update_litellm_debug_info(info: Dict[str, Any]):
    """
    Update the debug info with actual LiteLLM response metadata.
    Called internally after each LLM request.
    """
    global last_litellm_request
    last_litellm_request = {
        **info,
        "timestamp": datetime.now().isoformat(),
        "headers_sent": {
            "x-litellm-app": "aether-ui",
            "x-litellm-tags": "aether-pro,production",
            "Content-Type": "application/json"
        }
    }
    return {"status": "updated"}


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
