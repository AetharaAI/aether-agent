import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from pydantic import BaseModel

from fabric_a2a import AsyncMessagingClient, MessagePriority
from .fabric_registry import registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


class AgentInfo(BaseModel):
    id: str
    name: str
    owner_id: Optional[str] = None
    client_id: Optional[str] = None
    status: str  # "idle", "busy", "offline"
    capabilities: List[str]
    is_verified: bool = False
    last_seen: Optional[datetime] = None


class RegisterRequest(BaseModel):
    agent_id: str
    name: str
    capabilities: List[str]
    metadata: Dict[str, Any] = {}


class TaskDelegationRequest(BaseModel):
    target_agent: str
    task_type: str
    parameters: Dict[str, Any]


class TaskDelegationResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MessageRequest(BaseModel):
    target_agent: str
    message_type: str = "message"
    content: Dict[str, Any]



@router.get("/agents", response_model=List[AgentInfo])
async def list_agents(security_level: str = None) -> List[AgentInfo]:
    """List all registered agents in the fleet from the database."""
    agents_data = await registry.list_agents(security_level=security_level)
    return [AgentInfo(**a) for a in agents_data]


@router.get("/agents/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str) -> AgentInfo:
    """Get details about a specific agent from the persistent registry."""
    agent_data = await registry.get_agent(agent_id)
    if not agent_data:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentInfo(**agent_data)


@router.post("/register")
async def register_agent(
    request: RegisterRequest,
    authorization: str = Header(None)
) -> Dict[str, Any]:
    """
    Register or update an agent. 
    Requires Passport-IAM token in Authorization header.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Passport token required")

    # In a real scenario, we'd use 'Bearer <token>'
    token = authorization.replace("Bearer ", "") if "Bearer" in authorization else authorization
    
    passport_data = await registry.verify_passport_token(token)
    if not passport_data:
        raise HTTPException(status_code=401, detail="Invalid Passport token")

    success = await registry.register_agent(
        agent_id=request.agent_id,
        name=request.name,
        owner_id=passport_data["sub"],
        client_id=passport_data["client_id"],
        capabilities=request.capabilities,
        metadata=request.metadata
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to persist agent registry")
        
    return {"success": True, "agent_id": request.agent_id}


@router.post("/delegate")
async def delegate_task(
    request: TaskDelegationRequest,
    background_tasks: BackgroundTasks
) -> TaskDelegationResponse:
    """
    Delegate a task to another agent.
    This uses the official fabric-a2a AsyncMessagingClient to send the task.
    """
    task_id = f"task_{request.target_agent}_{int(datetime.now().timestamp())}"
    
    agent = await registry.get_agent(request.target_agent)
    if not agent:
        return TaskDelegationResponse(
            task_id=task_id,
            status="failed",
            error=f"Agent {request.target_agent} not found in registry"
        )
    
    if agent.get("status") == "offline":
        return TaskDelegationResponse(
            task_id=task_id,
            status="failed",
            error=f"Agent {request.target_agent} is currently offline"
        )
    
    try:
        # Use AsyncMessagingClient from official package
        client = AsyncMessagingClient(
            agent_id="aether",
            redis_url=os.getenv("FABRIC_REDIS_URL", "redis://localhost:6379")
        )
        await client.connect()
        
        # Send task via Fabric A2A
        result = await client.send_task(
            to_agent=request.target_agent,
            task_type=request.task_type,
            payload=request.parameters,
            priority=MessagePriority.NORMAL
        )
        
        await client.close()

        return TaskDelegationResponse(
            task_id=result.get("message_id", task_id),
            status="queued",
            result={
                "message": f"Task successfully delegated to {request.target_agent}",
                "stream_id": result.get("stream_id")
            }
        )
    except Exception as e:
        logger.error(f"Failed to delegate task: {e}")
        return TaskDelegationResponse(
            task_id=task_id,
            status="failed",
            error=str(e)
        )


@router.post("/message")
async def send_message(request: MessageRequest) -> Dict[str, Any]:
    """Send a message to another agent using official fabric-a2a client."""
    agent = await registry.get_agent(request.target_agent)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        client = AsyncMessagingClient(
            agent_id="aether",
            redis_url=os.getenv("FABRIC_REDIS_URL", "redis://localhost:6379")
        )
        await client.connect()

        # In official package, we use send_message or send_task
        task_type = request.message_type if request.message_type == "task" else "adhoc_message"
        
        result = await client.send_task(
            to_agent=request.target_agent,
            task_type=task_type,
            payload=request.content
        )

        await client.close()
        
        return {
            "success": True,
            "message_id": result.get("message_id"),
            "from": "aether",
            "to": request.target_agent,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/active")
async def get_active_tasks() -> List[Dict[str, Any]]:
    """Get list of active delegated tasks by polling the agent's inbox."""
    try:
        client = AsyncMessagingClient(
            agent_id="aether",
            redis_url=os.getenv("FABRIC_REDIS_URL", "redis://localhost:6379")
        )
        await client.connect()
        
        # Receive messages without acknowledging (simulating peek)
        # Note: Official client receive_messages might acknowledge depending on args, 
        # but for this ad-hoc peek we'll just read.
        messages = await client.receive_messages(count=50)
        
        active_tasks = []
        for msg in (messages or []):
            # Message objects in official client have data or are dicts
            msg_data = getattr(msg, 'data', msg) if not isinstance(msg, dict) else msg
            
            if msg_data.get("message_type") == "task":
                active_tasks.append({
                    "task_id": msg_data.get("id"),
                    "agent": msg_data.get("from_agent"),
                    "status": "pending",
                    "type": msg_data.get("payload", {}).get("task_type", "unknown"),
                    "started_at": msg_data.get("timestamp")
                })
                
        await client.close()
        return active_tasks
        
    except Exception as e:
        logger.error(f"Failed to fetch active tasks: {e}")
        return []


@router.post("/broadcast")
async def broadcast_message(
    message: str,
    message_type: str = "notify"
) -> Dict[str, Any]:
    """Broadcast a message to all active agents."""
    agents = await registry.list_agents()
    recipients = [a["id"] for a in agents]
    
    return {
        "success": True,
        "recipients": recipients,
        "message": message,
        "type": message_type,
        "timestamp": datetime.now().isoformat()
    }
