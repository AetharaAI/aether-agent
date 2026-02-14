"""
Aether Core Engine

================================================================================
ARCHITECTURE: Aether Core
================================================================================

This module contains the main Aether agent engine that orchestrates:
- Task planning and execution
- Memory management (via Memory Layer)
- Autonomy control (semi/auto modes with approval gates)
- Fleet integration (pod orchestration)
- Tool execution (via Tool Layer)

LAYER STACK:
  Identity Layer (aether_memory.py - identity/profile persistence)
       ↓
  Memory Layer (aether_memory.py - Redis Stack storage)
       ↓
  Context Layer (this module - context stats, compression, limits)
       ↓
  Provider Layer (aether/providers/ - LLM API abstraction) [STUB]
       ↓
  Tool Layer (aether/tools/ - agent-accessible operations) [NEW]

CLASSES:
- AetherCore: Main orchestration engine
- AutonomyController: Permission gates and mode switching
- FleetManager: Pod orchestration and health reporting

INTEGRATION POINTS:
- Uses NVIDIAKit for LLM completion (to be abstracted via Provider Layer)
- Uses AetherMemory for persistence
- Will use ToolRegistry for tool execution

================================================================================

Patent claim: System for hybrid human-AI autonomy with client-server fleet
orchestration, featuring semi/auto mode toggles and dynamic model switching.
"""

import os
import asyncio
import json
from datetime import datetime
from typing import Optional, Dict, List, Any, Literal
from dataclasses import dataclass, asdict
from pathlib import Path
import logging

from .aether_memory import AetherMemory, MemoryEntry
from .qdrant_adapter import QdrantMemory
from .nvidia_kit import NVIDIAKit, ModelResponse
from .browser_control import BrowserControl, BrowserToolIntegration
from .database import db  # Import the global db instance


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("aether")


@dataclass
class Task:
    """Task definition"""
    id: str
    description: str
    status: Literal["pending", "in_progress", "completed", "failed"]
    subtasks: List["Task"] = None
    result: Optional[str] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.subtasks is None:
            self.subtasks = []


@dataclass
class AgentConfig:
    """Aether agent configuration"""
    autonomy_mode: Literal["semi", "auto"] = "semi"
    workspace_path: str = os.getenv("WORKSPACE_PATH", "/workspace")
    redis_host: str = os.getenv("REDIS_HOST", "triad.aetherpro.tech")
    redis_port: int = int(os.getenv("REDIS_PORT", "6380"))
    nvidia_api_key: Optional[str] = None
    fleet_api_url: Optional[str] = None
    fleet_api_key: Optional[str] = None
    heartbeat_interval: int = 900  # 15 minutes in seconds


class AutonomyController:
    """
    Controls autonomy mode and approval gates.
    
    Patent claim: Novel hybrid human-AI autonomy system with configurable
    approval gates for risky actions.
    """
    
    RISKY_ACTIONS = [
        "send_email",
        "oauth_action",
        "file_delete",
        "api_call_external",
        "execute_code",
        "modify_system"
    ]
    
    def __init__(self, mode: Literal["semi", "auto"] = "semi"):
        self.mode = mode
        self.approval_queue: List[Dict[str, Any]] = []
    
    def check_approval_required(self, action: Dict[str, Any]) -> bool:
        """
        Check if action requires human approval.
        
        Args:
            action: Action dictionary with 'type' field
            
        Returns:
            True if approval required, False otherwise
        """
        if self.mode == "auto":
            return False
        
        action_type = action.get("type", "")
        return action_type in self.RISKY_ACTIONS
    
    async def request_approval(
        self,
        action: Dict[str, Any],
        context: str = ""
    ) -> bool:
        """
        Request approval for action via messaging channel.
        
        In production, this would integrate with OpenClaw's sessions_send
        to send approval requests via Telegram/Signal.
        
        Args:
            action: Action to approve
            context: Additional context for approval
            
        Returns:
            True if approved, False if denied
        """
        approval_id = f"approval_{len(self.approval_queue)}"
        
        approval_request = {
            "id": approval_id,
            "action": action,
            "context": context,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        
        self.approval_queue.append(approval_request)
        
        logger.info(f"Approval requested: {approval_id}")
        logger.info(f"Action: {action.get('type')} - {action.get('description')}")
        logger.info(f"Context: {context}")
        
        # TODO: Integrate with OpenClaw sessions_send
        # For now, simulate approval after delay
        await asyncio.sleep(2)
        
        # In production, wait for actual user response
        # For demo, auto-approve in semi mode for non-critical actions
        is_critical = action.get("critical", False)
        approved = not is_critical
        
        approval_request["status"] = "approved" if approved else "denied"
        
        logger.info(f"Approval {approval_id}: {'APPROVED' if approved else 'DENIED'}")
        
        return approved
    
    def toggle_mode(self) -> Literal["semi", "auto"]:
        """Toggle between semi and auto mode"""
        self.mode = "auto" if self.mode == "semi" else "semi"
        logger.info(f"Autonomy mode switched to: {self.mode}")
        return self.mode


class FleetManager:
    """
    Fleet Manager Control Plane (FMC) integration.
    
    Patent claim: Novel fleet-based pod orchestration with auto-failover
    and dynamic model switching.
    """
    
    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.api_url = api_url or os.getenv("FLEET_API_URL")
        self.api_key = api_key or os.getenv("FLEET_API_KEY")
        self.pod_id: Optional[str] = None
        self.health_stats = {
            "load": 0.0,
            "errors": 0,
            "cost": 0.0,
            "uptime": 0
        }
    
    async def register_pod(self, pod_config: Dict[str, Any]) -> str:
        """
        Register Aether as a pod in Fleet FMC.
        
        Args:
            pod_config: Pod configuration
            
        Returns:
            Pod ID
        """
        if not self.api_url:
            logger.info("Fleet API URL not configured, skipping registration (running in local pod mode)")
            self.pod_id = "local_pod"
            return self.pod_id
        
        # TODO: Implement actual Fleet API registration
        # For now, generate local pod ID
        self.pod_id = f"aether_pod_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info(f"Registered pod: {self.pod_id}")
        logger.info(f"Config: {json.dumps(pod_config, indent=2)}")
        
        return self.pod_id
    
    async def report_health(self, stats: Dict[str, Any]):
        """
        Report health stats to Fleet FMC.
        
        Args:
            stats: Health statistics
        """
        self.health_stats.update(stats)
        
        if not self.api_url:
            logger.debug(f"Health stats: {json.dumps(self.health_stats, indent=2)}")
            return
        
        # TODO: Implement actual Fleet API health reporting
        logger.info(f"Reporting health for pod {self.pod_id}")
    
    async def spawn_subpod(self, task: Dict[str, Any]) -> str:
        """
        Spawn sub-pod for task delegation.
        
        Args:
            task: Task to delegate
            
        Returns:
            Sub-pod ID
        """
        subpod_id = f"{self.pod_id}_sub_{len(self.health_stats.get('subpods', []))}"
        
        logger.info(f"Spawning sub-pod: {subpod_id}")
        logger.info(f"Task: {task.get('description')}")
        
        # TODO: Implement actual sub-pod spawning
        
        return subpod_id
    
    async def request_model_switch(self, target_model: str) -> bool:
        """
        Request model switch from Fleet FMC.
        
        Args:
            target_model: Target model identifier
            
        Returns:
            True if switch successful
        """
        logger.info(f"Requesting model switch to: {target_model}")
        
        # TODO: Implement actual model switching
        
        return True


class AetherCore:
    """
    Main Aether agent engine.
    
    Orchestrates task planning, execution, memory management, and Fleet integration.
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.memory = AetherMemory(
            redis_host=config.redis_host,
            redis_port=config.redis_port
        )
        self.vector_memory = QdrantMemory()
        self.nvidia = NVIDIAKit(api_key=config.nvidia_api_key)
        self.autonomy = AutonomyController(mode=config.autonomy_mode)
        self.fleet = FleetManager(
            api_url=config.fleet_api_url,
            api_key=config.fleet_api_key
        )
        self.browser = BrowserControl(self.nvidia)
        self.browser_tools = BrowserToolIntegration(self.browser)
        
        self.running = False
        self.heartbeat_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start Aether agent"""
        logger.info("Starting Aether agent...")
        
        # Connect to memory
        await self.memory.connect()
        await self.vector_memory.connect()

        # Connect to database
        await db.connect()
        
        # Register with Fleet
        await self.fleet.register_pod({
            "name": "aether",
            "version": "1.0.0",
            "autonomy_mode": self.autonomy.mode,
            "workspace": self.config.workspace_path
        })
        
        # Start heartbeat
        self.running = True
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        logger.info("Aether agent started successfully")
    
    async def stop(self):
        """Stop Aether agent"""
        logger.info("Stopping Aether agent...")
        
        self.running = False
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        await self.memory.close()
        await self.vector_memory.close()
        await self.nvidia.close()
        await db.close()
        
        logger.info("Aether agent stopped")
    
    async def _heartbeat_loop(self):
        """Periodic heartbeat checks"""
        while self.running:
            try:
                await self._perform_heartbeat()
                await asyncio.sleep(self.config.heartbeat_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                await asyncio.sleep(60)  # Retry after 1 minute
    
    async def _perform_heartbeat(self):
        """Perform heartbeat checks including context monitoring."""
        logger.info("Performing heartbeat...")
        
        # 1. Context Monitoring (Proactive Checkpointing)
        try:
            from .agent_websocket import get_agent_manager
            manager = get_agent_manager()
            
            for session_id, runtime in manager.active_runtimes.items():
                tokens = getattr(runtime, "_tokens_used", 0)
                limit = getattr(runtime, "_max_context_tokens", 32768)
                
                # If usage > 80%, trigger checkpoint
                if tokens > limit * 0.8:
                    logger.warning(
                        "Session %s context high (%d/%d tokens). Triggering proactive checkpoint.",
                        session_id, tokens, limit
                    )
                    # Use the first 50 chars of the most recent user message as objective
                    objective = "Context management checkpoint"
                    for msg in reversed(runtime.conversation_history):
                        if msg["role"] == "user":
                            objective = f"Continuing: {str(msg['content'])[:100]}..."
                            break
                            
                    asyncio.create_task(runtime.checkpoint(objective=objective))
        except Exception as e:
            logger.error(f"Context monitoring failed: {e}")

        # 2. Collect stats
        stats = {
            "timestamp": datetime.now().isoformat(),
            "autonomy_mode": self.autonomy.mode,
            "memory_stats": await self.memory.get_memory_stats()
        }
        
        # Report to Fleet
        await self.fleet.report_health(stats)
        
        # Log to memory
        await self.memory.log_daily(
            f"Heartbeat: {json.dumps(stats)}",
            source="system",
            tags=["heartbeat"]
        )
        
        logger.info("Heartbeat completed")
    
    async def plan_task(self, description: str) -> Task:
        """
        Plan task using the configured model with thinking mode.
        
        Args:
            description: Task description
            
        Returns:
            Task with subtasks
        """
        logger.info(f"Planning task: {description}")
        
        # Use thinking mode for task planning
        response = await self.nvidia.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You are Aether, an AI assistant. Break down tasks into executable subtasks."
                },
                {
                    "role": "user",
                    "content": f"Plan this task: {description}\n\nProvide a JSON array of subtasks with 'description' and 'type' fields."
                }
            ],
            thinking=True,
            temperature=0.3
        )
        
        logger.info(f"Planning thinking: {response.thinking}")
        
        # Parse subtasks from response
        try:
            # Extract JSON from response
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            subtasks_data = json.loads(content)
            
            subtasks = [
                Task(
                    id=f"subtask_{i}",
                    description=st.get("description", ""),
                    status="pending"
                )
                for i, st in enumerate(subtasks_data)
            ]
        except Exception as e:
            logger.error(f"Failed to parse subtasks: {e}")
            # Fallback: single subtask
            subtasks = [
                Task(
                    id="subtask_0",
                    description=description,
                    status="pending"
                )
            ]
        
        task = Task(
            id=f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            description=description,
            status="pending",
            subtasks=subtasks
        )
        
        logger.info(f"Planned {len(subtasks)} subtasks")
        
        return task
    
    async def execute_task(self, task: Task) -> Task:
        """
        Execute task with autonomy control.
        
        Args:
            task: Task to execute
            
        Returns:
            Completed task with results
        """
        logger.info(f"Executing task: {task.description}")
        
        task.status = "in_progress"
        
        # Execute subtasks
        for subtask in task.subtasks:
            try:
                # Check if approval required
                action = {
                    "type": "execute_subtask",
                    "description": subtask.description
                }
                
                if self.autonomy.check_approval_required(action):
                    approved = await self.autonomy.request_approval(
                        action,
                        context=f"Part of task: {task.description}"
                    )
                    
                    if not approved:
                        subtask.status = "failed"
                        subtask.error = "Approval denied"
                        logger.warning(f"Subtask denied: {subtask.description}")
                        continue
                
                # Execute subtask
                subtask.status = "in_progress"
                result = await self._execute_subtask(subtask)
                subtask.result = result
                subtask.status = "completed"
                
                logger.info(f"Subtask completed: {subtask.description}")
                
            except Exception as e:
                subtask.status = "failed"
                subtask.error = str(e)
                logger.error(f"Subtask failed: {subtask.description} - {e}")
        
        # Check overall task status
        if all(st.status == "completed" for st in task.subtasks):
            task.status = "completed"
            task.result = "All subtasks completed successfully"
        elif any(st.status == "failed" for st in task.subtasks):
            task.status = "failed"
            failed_count = sum(1 for st in task.subtasks if st.status == "failed")
            task.error = f"{failed_count} subtask(s) failed"
        
        # Log to memory
        await self.memory.log_daily(
            f"Task completed: {task.description} - Status: {task.status}",
            source="agent",
            tags=["task", task.status]
        )
        
        logger.info(f"Task execution finished: {task.status}")
        
        return task
    
    async def _execute_subtask(self, subtask: Task) -> str:
        """
        Execute individual subtask.
        
        This is a simplified version. In production, this would:
        - Use OpenClaw's tool system
        - Execute actual actions (file ops, API calls, etc.)
        - Handle errors and retries
        
        Args:
            subtask: Subtask to execute
            
        Returns:
            Result string
        """
        # Simulate execution with NVIDIA API
        response = await self.nvidia.complete(
            messages=[
                {
                    "role": "system",
                    "content": "You are Aether. Execute the given subtask and report results."
                },
                {
                    "role": "user",
                    "content": f"Execute: {subtask.description}"
                }
            ],
            temperature=0.5
        )
        
        return response.content
    
    async def process_message(self, message: str, session_id: str = "default") -> str:
        """
        Process incoming message and generate response.
        Uses dynamic system prompt built from Redis-stored identity.
        
        Args:
            message: User message
            session_id: Session ID for memory context
            
        Returns:
            Agent response
        """
        logger.info(f"Processing message: {message}")
        
        # Check for commands
        if message.startswith("/aether"):
            return await self._handle_command(message)
        
        # Build dynamic system prompt from Redis identity
        system_prompt = await self.memory.build_system_prompt()
        
        # Step 1: Semantic search in Redis memory
        redis_results = await self.memory.search_semantic(message, limit=3)
        
        # Step 2: Vector search in Qdrant (long-term memory)
        vector_results = await self.vector_memory.search(message, limit=3, session_id=session_id)
        
        memory_context = ""
        if redis_results:
            memory_context += "RECENT MEMORY:\n" + "\n".join([f"- {r.content}" for r in redis_results]) + "\n\n"
            
        if vector_results:
            memory_context += "LONG-TERM VECTORS:\n" + "\n".join([f"- {r.content}" for r in vector_results])
        
        # Combine system prompt with memory context
        full_system_prompt = f"{system_prompt}\n\n{memory_context}"
        
        # Generate response with dynamic identity and context
        response = await self.nvidia.complete(
            messages=[
                {
                    "role": "system",
                    "content": full_system_prompt
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            thinking=True
        )
        
        # Store interaction in both memories
        # 1. Redis daily memory
        await self.memory.log_daily(
            f"User: {message}\nAether: {response.content}",
            source="interaction"
        )
        
        # 2. Qdrant vector memory (store user and assistant messages separately)
        await self.vector_memory.add(
            content=message,
            role="user",
            session_id=session_id
        )
        await self.vector_memory.add(
            content=response.content,
            role="assistant",
            session_id=session_id
        )
        
        # Telemetry
        await db.log_api_call(
            session_id=session_id,
            provider="nvidia", # or litellm
            model=getattr(self.nvidia.config, "model", "unknown"),
            tokens={
                "prompt": 0, # TODO: Parse from response if available
                "completion": 0,
                "total": 0
            },
            cost=0.0
        )
        
        return response.content
    
    async def _handle_command(self, command: str) -> str:
        """Handle Aether commands"""
        parts = command.split()
        
        if len(parts) < 2:
            return "Usage: /aether <command> [args]"
        
        cmd = parts[1]
        
        if cmd == "toggle":
            if len(parts) > 2:
                mode = parts[2]
                if mode in ["auto", "semi"]:
                    self.autonomy.mode = mode
                    return f"Autonomy mode set to: {mode}"
            else:
                new_mode = self.autonomy.toggle_mode()
                return f"Autonomy mode toggled to: {new_mode}"
        
        elif cmd == "checkpoint":
            name = " ".join(parts[2:]) if len(parts) > 2 else None
            checkpoint_id = await self.memory.checkpoint_snapshot(name)
            return f"Checkpoint created: {checkpoint_id}"
        
        elif cmd == "rollback":
            if len(parts) < 3:
                return "Usage: /aether rollback <checkpoint_id>"
            checkpoint_id = parts[2]
            success = await self.memory.rollback_to(checkpoint_id)
            return f"Rollback {'successful' if success else 'failed'}"
        
        elif cmd == "fleet":
            if len(parts) > 2 and parts[2] == "status":
                stats = self.fleet.health_stats
                return f"Fleet status:\n{json.dumps(stats, indent=2)}"
        
        elif cmd == "heartbeat":
            await self._perform_heartbeat()
            return "Heartbeat completed"
        
        elif cmd == "stats":
            stats = await self.memory.get_memory_stats()
            return f"Memory stats:\n{json.dumps(stats, indent=2)}"
        
        elif cmd == "browse":
            if len(parts) < 3:
                return "Usage: /aether browse <url> [purpose]"
            url = parts[2]
            purpose = " ".join(parts[3:]) if len(parts) > 3 else "general browsing"
            result = await self.browser_tools.smart_navigate(url, purpose)
            return f"Browsed {url}:\n{result['understanding']}"
        
        return f"Unknown command: {cmd}"


# Example usage
if __name__ == "__main__":
    async def main():
        # Configure Aether
        config = AgentConfig(
            autonomy_mode="semi",
            workspace_path="/tmp/aether_test",
            nvidia_api_key=os.getenv("NVIDIA_API_KEY")
        )
        
        # Create and start agent
        aether = AetherCore(config)
        await aether.start()
        
        try:
            # Process a message
            response = await aether.process_message(
                "Schedule a meeting with the team next Monday at 2pm"
            )
            print(f"\nResponse: {response}")
            
            # Plan and execute a task
            task = await aether.plan_task(
                "Research competitors and create a summary report"
            )
            print(f"\nPlanned task with {len(task.subtasks)} subtasks")
            
            completed_task = await aether.execute_task(task)
            print(f"\nTask status: {completed_task.status}")
            
            # Create checkpoint
            checkpoint_id = await aether.memory.checkpoint_snapshot("after_demo")
            print(f"\nCheckpoint created: {checkpoint_id}")
            
        finally:
            await aether.stop()
    
    asyncio.run(main())
