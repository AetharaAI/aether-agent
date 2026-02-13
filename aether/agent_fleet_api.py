"""
Agent Fleet API - Multi-Agent Coordination

================================================================================
REST API for managing multiple agents and delegating tasks.
Uses Fabric messaging for A2A communication.
================================================================================
"""

import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from .fabric_messaging import FabricMessaging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/fleet", tags=["fleet"])


class AgentInfo(BaseModel):
    id: str
    name: str
    status: str  # "idle", "busy", "offline"
    capabilities: List[str]
    last_seen: Optional[str] = None


class TaskDelegationRequest(BaseModel):
    target_agent: str
    task_type: str
    parameters: Dict[str, Any]
    timeout_seconds: int = 300


class TaskDelegationResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MessageRequest(BaseModel):
    target_agent: str
    message_type: str  # "task", "query", "notify"
    content: Dict[str, Any]


# Simulated fleet registry - in production this would be in Redis
AGENT_REGISTRY: Dict[str, AgentInfo] = {
    "aether": AgentInfo(
        id="aether",
        name="Aether",
        status="idle",
        capabilities=["chat", "code", "terminal", "browser", "files"],
    ),
    "percy": AgentInfo(
        id="percy",
        name="Percy",
        status="idle",
        capabilities=["analytics", "data_processing", "research"],
    ),
}


@router.get("/agents")
async def list_agents() -> List[AgentInfo]:
    """List all registered agents in the fleet."""
    return list(AGENT_REGISTRY.values())


@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str) -> AgentInfo:
    """Get details about a specific agent."""
    if agent_id not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AGENT_REGISTRY[agent_id]


@router.post("/delegate")
async def delegate_task(
    request: TaskDelegationRequest,
    background_tasks: BackgroundTasks
) -> TaskDelegationResponse:
    """
    Delegate a task to another agent.
    
    This uses Fabric messaging to send the task and wait for completion.
    """
    task_id = f"task_{request.target_agent}_{hash(str(request.parameters))}"
    
    if request.target_agent not in AGENT_REGISTRY:
        return TaskDelegationResponse(
            task_id=task_id,
            status="failed",
            error=f"Agent {request.target_agent} not found"
        )
    
    agent = AGENT_REGISTRY[request.target_agent]
    if agent.status == "offline":
        return TaskDelegationResponse(
            task_id=task_id,
            status="failed",
            error=f"Agent {request.target_agent} is offline"
        )
    
    # Use FabricMessaging to send the task
    try:
        from .api_server import aether # Late import
        if not aether or not aether.config:
            raise HTTPException(status_code=503, detail="Agent runtime not initialized")

        messaging = FabricMessaging(
            agent_id="aether",
            redis_url=f"redis://{aether.config.redis_host}:{aether.config.redis_port}"
        )
        await messaging.start()
        
        # Send task via Fabric
        result = await messaging.send_task(
            to_agent=request.target_agent,
            task_type=request.task_type,
            payload=request.parameters
        )
        
        await messaging.stop()

        return TaskDelegationResponse(
            task_id=result["message_id"],
            status="queued",
            result={
                "message": f"Task delegated to {request.target_agent}",
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
    """Send a message to another agent."""
    if request.target_agent not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        from .api_server import aether # Late import to avoid circular dependency
        if not aether or not aether.config:
            raise HTTPException(status_code=503, detail="Agent runtime not initialized")

        messaging = FabricMessaging(
            agent_id="aether",
            redis_url=f"redis://{aether.config.redis_host}:{aether.config.redis_port}"
        )
        await messaging.start()

        if request.message_type == "task":
            result = await messaging.send_task(
                to_agent=request.target_agent,
                task_type="adhoc_message",
                payload=request.content
            )
        else:
            # Generic message (treated as task or response depending on context)
             result = await messaging.send_task(
                to_agent=request.target_agent,
                task_type="message",
                payload=request.content
            )

        await messaging.stop()
        
        return {
            "success": True,
            "message_id": result["message_id"],
            "from": "aether",
            "to": request.target_agent,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/active")
async def get_active_tasks() -> List[Dict[str, Any]]:
    """Get list of active delegated tasks."""
    try:
        if not aether or not aether.config: # Check if runtime initialized
             return []
             
        # Use FabricMessaging to inspect inbox (Redis Streams)
        messaging = FabricMessaging(
            agent_id="aether",
            redis_url=f"redis://{aether.config.redis_host}:{aether.config.redis_port}"
        )
        await messaging.start()
        
        # Read pending messages without ack'ing
        messages = await messaging.receive_messages(count=50, block_ms=100)
        
        active_tasks = []
        for msg in messages:
            if msg.get("message_type") == "task":
                active_tasks.append({
                    "task_id": msg.get("id"),
                    "agent": msg.get("from_agent"),
                    "status": "pending",
                    "type": msg.get("payload", {}).get("task_type", "unknown"),
                    "started_at": msg.get("timestamp")
                })
                
        await messaging.stop()
        return active_tasks
        
    except Exception as e:
        logger.error(f"Failed to fetch active tasks: {e}")
        return []


@router.post("/broadcast")
async def broadcast_message(
    message: str,
    message_type: str = "notify"
) -> Dict[str, Any]:
    """Broadcast a message to all agents in the fleet."""
    return {
        "success": True,
        "recipients": list(AGENT_REGISTRY.keys()),
        "message": message,
        "type": message_type
    }
