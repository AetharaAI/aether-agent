"""
Core Tools Implementation

================================================================================
ARCHITECTURE: Tool Layer - Core Tools
================================================================================

Built-in tools for agent operations.
These tools are registered by default in the ToolRegistry.

TOOL LIST:
1. checkpoint - Create memory checkpoints
2. checkpoint_and_continue - Checkpoint and reset loop for long tasks
3. compress_context - Compress daily logs to long-term memory
4. get_context_stats - Get memory usage statistics
5. terminal_exec - Execute terminal commands (restricted)
6. file_upload - Upload files for processing (restricted)

FUTURE TOOLS:
- file_read, file_write (from OpenClaw patterns)
- git_diff, git_commit
- rollback_checkpoint
- redis_inspect
================================================================================
"""

import subprocess
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

from .registry import Tool, ToolResult, ToolPermission


class CheckpointTool(Tool):
    """
    Create a memory checkpoint for rollback capability.
    
    Captures current state of daily logs and long-term memory.
    Useful before risky operations.
    """
    
    name = "checkpoint"
    description = "Create a snapshot of current memory state for rollback"
    permission = ToolPermission.INTERNAL
    parameters = {
        "name": {
            "type": "string",
            "description": "Optional name for the checkpoint",
            "required": False
        }
    }
    
    def __init__(self, memory=None):
        self._memory = memory
    
    async def execute(self, name: Optional[str] = None) -> ToolResult:
        try:
            if not self._memory:
                return ToolResult(
                    success=False,
                    error="Memory system not available"
                )
            
            checkpoint_id = await self._memory.checkpoint_snapshot(name)
            
            return ToolResult(
                success=True,
                data={
                    "checkpoint_id": checkpoint_id,
                    "name": name or "Unnamed checkpoint",
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to create checkpoint: {str(e)}"
            )
    
    def set_memory(self, memory):
        """Set memory reference"""
        self._memory = memory


class CheckpointAndContinueTool(Tool):
    """
    Checkpoint current context and reset the tool loop for long-running tasks.

    This implements episodic execution:
    - Saves current progress to a checkpoint
    - Clears working memory to free up context
    - Resets the tool call counter
    - Allows the agent to continue with fresh context

    Use this when you need to do long multi-step tasks that would exceed
    the normal tool call limit.
    """

    name = "checkpoint_and_continue"
    description = "Create a checkpoint and reset the tool loop to continue long-running tasks. Use when you need more than 30 tool calls for a complex multi-step objective."
    permission = ToolPermission.INTERNAL
    parameters = {
        "objective": {
            "type": "string",
            "description": "Brief description of what you're trying to accomplish (for checkpoint context)",
            "required": True
        },
        "progress_summary": {
            "type": "string",
            "description": "Summary of what has been accomplished so far",
            "required": False
        }
    }

    def __init__(self, runtime=None):
        self._runtime = runtime

    async def execute(
        self,
        objective: str,
        progress_summary: Optional[str] = None
    ) -> ToolResult:
        try:
            if not self._runtime:
                return ToolResult(
                    success=False,
                    error="Runtime not available"
                )

            # Create checkpoint with the current state
            checkpoint_objective = f"{objective}\n\nProgress so far: {progress_summary or 'Checkpoint triggered'}"
            success = await self._runtime.checkpoint(objective=checkpoint_objective)

            if not success:
                return ToolResult(
                    success=False,
                    error="Failed to create checkpoint"
                )

            # Signal to the runtime that we want to reset the loop
            # This will be picked up by the runtime to reset round_count
            return ToolResult(
                success=True,
                data={
                    "checkpoint_created": True,
                    "context_reset": True,
                    "message": "Checkpoint created. Context will reset for next episode. Continue your work.",
                    "objective": objective,
                    "timestamp": datetime.now().isoformat(),
                    "_reset_loop": True  # Special flag for runtime
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to checkpoint and continue: {str(e)}"
            )

    def set_runtime(self, runtime):
        """Set runtime reference"""
        self._runtime = runtime


class CompressContextTool(Tool):
    """
    Compress context by migrating daily logs to long-term memory.
    
    Reduces memory pressure by compressing older daily entries.
    Preserves important entries based on tags and scoring.
    """
    
    name = "compress_context"
    description = "Compress daily memory by migrating to long-term storage"
    permission = ToolPermission.INTERNAL
    parameters = {
        "date": {
            "type": "string",
            "description": "Specific date to compress (YYYY-MM-DD, default: 7 days ago)",
            "required": False
        }
    }
    
    def __init__(self, memory=None):
        self._memory = memory
    
    async def execute(self, date: Optional[str] = None) -> ToolResult:
        try:
            if not self._memory:
                return ToolResult(
                    success=False,
                    error="Memory system not available"
                )
            
            # Default to 7 days ago if no date specified
            if not date:
                from datetime import timedelta
                date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            
            await self._memory.migrate_daily_to_longterm(date)
            
            return ToolResult(
                success=True,
                data={
                    "date": date,
                    "message": f"Compressed daily memory for {date}"
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to compress context: {str(e)}"
            )
    
    def set_memory(self, memory):
        """Set memory reference"""
        self._memory = memory


class GetContextStatsTool(Tool):
    """
    Get detailed memory usage statistics.
    
    Returns breakdown of short-term, long-term, and checkpoint storage.
    """
    
    name = "get_context_stats"
    description = "Get memory usage statistics and breakdown"
    permission = ToolPermission.INTERNAL
    parameters = {}
    
    def __init__(self, memory=None):
        self._memory = memory
    
    async def execute(self) -> ToolResult:
        try:
            if not self._memory:
                return ToolResult(
                    success=False,
                    error="Memory system not available"
                )
            
            stats = await self._memory.get_memory_stats()
            
            return ToolResult(
                success=True,
                data=stats
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get context stats: {str(e)}"
            )
    
    def set_memory(self, memory):
        """Set memory reference"""
        self._memory = memory


class TerminalExecTool(Tool):
    """
    Execute terminal commands.
    
    WARNING: Restricted permission - requires auto mode or explicit approval.
    Use with caution.
    """
    
    name = "terminal_exec"
    description = "Execute a terminal command"
    permission = ToolPermission.RESTRICTED
    parameters = {
        "command": {
            "type": "string",
            "description": "Command to execute",
            "required": True
        },
        "cwd": {
            "type": "string",
            "description": "Working directory (default: current)",
            "required": False
        },
        "timeout": {
            "type": "integer",
            "description": "Timeout in seconds (default: 30)",
            "required": False
        }
    }
    
    async def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30
    ) -> ToolResult:
        try:
            # Security: Basic command validation
            dangerous_commands = ["rm -rf /", ":(){ :|:& };:", "> /dev/sda"]
            for danger in dangerous_commands:
                if danger in command:
                    return ToolResult(
                        success=False,
                        error=f"Command contains dangerous pattern: {danger}"
                    )
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=timeout
            )
            
            return ToolResult(
                success=result.returncode == 0,
                data={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode
                },
                error=result.stderr if result.returncode != 0 else None
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout} seconds"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to execute command: {str(e)}"
            )


class FileUploadTool(Tool):
    """
    Upload and process files.
    
    Saves uploaded files to temporary storage for agent processing.
    """
    
    name = "file_upload"
    description = "Upload a file for agent processing"
    permission = ToolPermission.SEMI
    parameters = {
        "filename": {
            "type": "string",
            "description": "Name of the file",
            "required": True
        },
        "content": {
            "type": "string",
            "description": "File content (base64 encoded)",
            "required": True
        },
        "mime_type": {
            "type": "string",
            "description": "MIME type of the file",
            "required": False
        }
    }
    
    def __init__(self, upload_dir: str = "/tmp/aether_uploads"):
        self._upload_dir = Path(upload_dir)
        self._upload_dir.mkdir(parents=True, exist_ok=True)
    
    async def execute(
        self,
        filename: str,
        content: str,
        mime_type: Optional[str] = None
    ) -> ToolResult:
        try:
            import base64
            
            # Decode content
            file_data = base64.b64decode(content)
            
            # Sanitize filename
            safe_filename = Path(filename).name
            filepath = self._upload_dir / safe_filename
            
            # Write file
            with open(filepath, "wb") as f:
                f.write(file_data)
            
            return ToolResult(
                success=True,
                data={
                    "filename": safe_filename,
                    "path": str(filepath),
                    "size": len(file_data),
                    "mime_type": mime_type
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to upload file: {str(e)}"
            )


class FileReadTool(Tool):
    """
    Read file contents from the filesystem.
    
    Allows Aether to read files in the workspace and system.
    """
    
    name = "file_read"
    description = "Read the contents of a file from the filesystem"
    permission = ToolPermission.SEMI
    parameters = {
        "path": {
            "type": "string",
            "description": "Absolute or relative path to the file",
            "required": True
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of lines to read (default: all)",
            "required": False
        },
        "offset": {
            "type": "integer",
            "description": "Line offset to start reading from (default: 0)",
            "required": False
        }
    }
    
    async def execute(
        self,
        path: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> ToolResult:
        try:
            filepath = Path(path).resolve()
            
            # Security: Check for path traversal
            if not filepath.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {path}"
                )
            
            if not filepath.is_file():
                return ToolResult(
                    success=False,
                    error=f"Path is not a file: {path}"
                )
            
            # Read file
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            
            # Apply offset and limit
            start = offset
            end = offset + limit if limit else len(lines)
            selected_lines = lines[start:end]
            
            content = "".join(selected_lines)
            
            return ToolResult(
                success=True,
                data={
                    "path": str(filepath),
                    "content": content,
                    "total_lines": len(lines),
                    "returned_lines": len(selected_lines),
                    "size_bytes": filepath.stat().st_size
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to read file: {str(e)}"
            )


class FileListTool(Tool):
    """
    List directory contents.
    
    Allows Aether to browse the filesystem.
    """
    
    name = "file_list"
    description = "List files and directories at a given path"
    permission = ToolPermission.SEMI
    parameters = {
        "path": {
            "type": "string",
            "description": "Directory path to list (default: current directory)",
            "required": False
        },
        "recursive": {
            "type": "boolean",
            "description": "List recursively (default: false)",
            "required": False
        },
        "pattern": {
            "type": "string",
            "description": "Glob pattern to filter files (e.g., '*.py')",
            "required": False
        }
    }
    
    async def execute(
        self,
        path: str = ".",
        recursive: bool = False,
        pattern: Optional[str] = None
    ) -> ToolResult:
        try:
            dirpath = Path(path).resolve()
            
            if not dirpath.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {path}"
                )
            
            if not dirpath.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Path is not a directory: {path}"
                )
            
            # List contents
            items = []
            
            if recursive:
                glob_pattern = pattern or "*"
                paths = dirpath.rglob(glob_pattern)
            else:
                paths = dirpath.glob(pattern or "*")
            
            for p in sorted(paths):
                try:
                    stat = p.stat()
                    items.append({
                        "name": p.name,
                        "path": str(p),
                        "type": "directory" if p.is_dir() else "file",
                        "size": stat.st_size if p.is_file() else None,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except (OSError, PermissionError):
                    # Skip files we can't stat
                    continue
            
            return ToolResult(
                success=True,
                data={
                    "path": str(dirpath),
                    "items": items,
                    "count": len(items)
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to list directory: {str(e)}"
            )


class FileWriteTool(Tool):
    """
    Write content to a file.
    
    Allows Aether to create or modify files.
    """
    
    name = "file_write"
    description = "Write content to a file (creates or overwrites)"
    permission = ToolPermission.SEMI  # Safe: has path guards for system directories
    parameters = {
        "path": {
            "type": "string",
            "description": "Path to the file",
            "required": True
        },
        "content": {
            "type": "string",
            "description": "Content to write",
            "required": True
        },
        "append": {
            "type": "boolean",
            "description": "Append to file instead of overwrite (default: false)",
            "required": False
        }
    }
    
    async def execute(
        self,
        path: str,
        content: str,
        append: bool = False
    ) -> ToolResult:
        try:
            filepath = Path(path).resolve()
            
            # Security: Don't allow writing to system directories
            dangerous_paths = ["/etc", "/usr", "/bin", "/sbin", "/lib"]
            for danger in dangerous_paths:
                if str(filepath).startswith(danger):
                    return ToolResult(
                        success=False,
                        error=f"Cannot write to system directory: {danger}"
                    )
            
            # Create parent directories if needed
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            mode = "a" if append else "w"
            with open(filepath, mode, encoding="utf-8") as f:
                f.write(content)
            
            return ToolResult(
                success=True,
                data={
                    "path": str(filepath),
                    "bytes_written": len(content.encode("utf-8")),
                    "mode": "append" if append else "write"
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to write file: {str(e)}"
            )


class SetModeTool(Tool):
    """
    Allow the agent to change its own autonomy mode.
    
    Like Kilocode's mode switching — the model can escalate to 'auto'
    when it needs to write files or execute commands, then drop back
    to 'semi' when the risky operations are complete.
    
    Modes:
      - semi: Read/search tools work freely; write/execute need approval
      - auto: All tools execute immediately with logged accountability
    """
    
    name = "set_mode"
    description = "Switch the agent's autonomy mode (semi or auto). Use 'auto' when you need to write files or execute commands, 'semi' when done."
    permission = ToolPermission.INTERNAL  # Always callable regardless of current mode
    parameters = {
        "mode": {
            "type": "string",
            "description": "Target autonomy mode: 'semi' (cautious) or 'auto' (full access)",
            "required": True
        },
        "reason": {
            "type": "string",
            "description": "Brief reason for the mode change (for audit logging)",
            "required": False
        }
    }
    
    def __init__(self, registry=None):
        self._registry = registry
    
    def set_registry(self, registry):
        """Set registry reference (called after registration)."""
        self._registry = registry
    
    async def execute(self, mode: str, reason: str = "") -> ToolResult:
        valid_modes = ("semi", "auto")
        if mode not in valid_modes:
            return ToolResult(
                success=False,
                error=f"Invalid mode '{mode}'. Must be one of: {valid_modes}"
            )
        
        if not self._registry:
            return ToolResult(
                success=False,
                error="No registry reference — cannot change mode"
            )
        
        old_mode = self._registry._autonomy_mode
        self._registry.set_autonomy_mode(mode)
        
        return ToolResult(
            success=True,
            data={
                "previous_mode": old_mode,
                "new_mode": mode,
                "reason": reason or "Agent-initiated mode switch",
            }
        )


class SearchMemoryTool(Tool):
    """
    Search the agent's Redis-backed memory (daily logs + long-term storage).

    Use this to recall past conversations, decisions, tool results, and
    anything the agent has previously encountered. This is how you remember.
    """

    name = "search_memory"
    description = "Search your memory (daily logs and long-term storage) by keyword. Use this to recall past events, decisions, and context."
    permission = ToolPermission.INTERNAL
    parameters = {
        "query": {
            "type": "string",
            "description": "Search query (keyword or phrase)",
            "required": True
        },
        "source_filter": {
            "type": "string",
            "description": "Filter by source: 'user', 'system', or 'agent' (default: all)",
            "required": False
        },
        "limit": {
            "type": "integer",
            "description": "Max results to return (default: 10)",
            "required": False
        }
    }

    def __init__(self, memory=None):
        self._memory = memory

    async def execute(
        self,
        query: str,
        source_filter: Optional[str] = None,
        limit: int = 10
    ) -> ToolResult:
        try:
            if not self._memory:
                return ToolResult(success=False, error="Memory system not available")

            results = await self._memory.search_semantic(
                query=query,
                limit=limit,
                source_filter=source_filter
            )

            entries = []
            for r in results:
                entries.append({
                    "content": r.content[:500],
                    "score": r.score,
                    "source": r.source,
                    "timestamp": r.timestamp,
                    "key": r.key,
                })

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "results": entries,
                    "count": len(entries),
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Memory search failed: {e}")

    def set_memory(self, memory):
        self._memory = memory


class ListCheckpointsTool(Tool):
    """
    List all available memory checkpoints with their metadata.

    Use this to see what snapshots exist before reading one back.
    """

    name = "list_checkpoints"
    description = "List all memory checkpoints (name, UUID, timestamp). Use before read_checkpoint to find the right one."
    permission = ToolPermission.INTERNAL
    parameters = {}

    def __init__(self, memory=None):
        self._memory = memory

    async def execute(self) -> ToolResult:
        try:
            if not self._memory:
                return ToolResult(success=False, error="Memory system not available")

            checkpoints = await self._memory.list_checkpoints()

            return ToolResult(
                success=True,
                data={
                    "checkpoints": checkpoints,
                    "count": len(checkpoints),
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to list checkpoints: {e}")

    def set_memory(self, memory):
        self._memory = memory


class ReadCheckpointTool(Tool):
    """
    Read the full contents of a memory checkpoint by UUID.

    Checkpoints are stored in Redis, not the filesystem.
    Use list_checkpoints first to get the UUID.
    """

    name = "read_checkpoint"
    description = "Read a checkpoint's contents by UUID. Checkpoints are in Redis — use list_checkpoints to find UUIDs."
    permission = ToolPermission.INTERNAL
    parameters = {
        "uuid": {
            "type": "string",
            "description": "Checkpoint UUID (from list_checkpoints)",
            "required": True
        }
    }

    def __init__(self, memory=None):
        self._memory = memory

    async def execute(self, uuid: str) -> ToolResult:
        try:
            if not self._memory:
                return ToolResult(success=False, error="Memory system not available")

            data = await self._memory.read_checkpoint(uuid)
            if not data:
                return ToolResult(
                    success=False,
                    error=f"Checkpoint not found: {uuid}"
                )

            # Truncate large checkpoint data to avoid context bloat
            import json as _json
            serialized = _json.dumps(data, indent=2)
            if len(serialized) > 4000:
                summary = {
                    "uuid": data.get("uuid"),
                    "name": data.get("name"),
                    "timestamp": data.get("timestamp"),
                    "daily_dates": list(data.get("daily", {}).keys()),
                    "longterm_keys": list(data.get("longterm", {}).keys()) if isinstance(data.get("longterm"), dict) else [],
                    "truncated": True,
                    "full_size_chars": len(serialized),
                    "data_preview": serialized[:3500],
                }
                return ToolResult(success=True, data=summary)

            return ToolResult(success=True, data=data)
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to read checkpoint: {e}")

    def set_memory(self, memory):
        self._memory = memory


class RecallEpisodesTool(Tool):
    """
    Read episodic memory — compressed session summaries and context checkpoints.

    After context compression, critical facts are saved as episodes.
    Use this to recover context from earlier in the session or past sessions.
    """

    name = "recall_episodes"
    description = "Recall episodic memory (compressed context summaries, tool call history). Use after context compression to recover what you were doing."
    permission = ToolPermission.INTERNAL
    parameters = {
        "session_id": {
            "type": "string",
            "description": "Session ID to recall from (default: current session)",
            "required": False
        },
        "limit": {
            "type": "integer",
            "description": "Max episodes to return (default: 10)",
            "required": False
        }
    }

    def __init__(self, memory=None, runtime=None):
        self._memory = memory
        self._runtime = runtime

    async def execute(
        self,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> ToolResult:
        try:
            if not self._memory:
                return ToolResult(success=False, error="Memory system not available")

            sid = session_id
            if not sid and self._runtime:
                sid = self._runtime.session_id
            if not sid:
                return ToolResult(
                    success=False,
                    error="No session_id provided and no runtime available"
                )

            episodes = await self._memory.get_episodes(sid, limit=limit)

            return ToolResult(
                success=True,
                data={
                    "session_id": sid,
                    "episodes": episodes,
                    "count": len(episodes),
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to recall episodes: {e}")

    def set_memory(self, memory):
        self._memory = memory

    def set_runtime(self, runtime):
        self._runtime = runtime


class SearchWorkspaceTool(Tool):
    """
    Search through workspace files by keyword.

    Use this to find relevant skills, documentation, extensions, and
    configuration files in /workspace/skills/ and /workspace/openclaw-docs/.
    """

    name = "search_workspace"
    description = "Search workspace files (skills, docs, extensions) by keyword. Returns matching file paths and snippets."
    permission = ToolPermission.SEMI
    parameters = {
        "query": {
            "type": "string",
            "description": "Search keyword or phrase",
            "required": True
        },
        "path": {
            "type": "string",
            "description": "Directory to search (default: /workspace)",
            "required": False
        },
        "pattern": {
            "type": "string",
            "description": "File glob pattern to filter (e.g., '*.md', '*.ts')",
            "required": False
        }
    }

    async def execute(
        self,
        query: str,
        path: str = "/workspace",
        pattern: Optional[str] = None
    ) -> ToolResult:
        try:
            if pattern:
                cmd = ["grep", "-rl", "--include", pattern, "-m", "3", query, path]
            else:
                cmd = ["grep", "-rl", "-m", "3", query, path]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            matching_files = [f for f in result.stdout.strip().split("\n") if f][:20]

            snippets = []
            for filepath in matching_files[:5]:
                try:
                    snippet_result = subprocess.run(
                        ["grep", "-n", "-m", "3", "-C", "1", query, filepath],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if snippet_result.stdout:
                        snippets.append({
                            "file": filepath,
                            "matches": snippet_result.stdout[:500]
                        })
                except Exception:
                    snippets.append({"file": filepath, "matches": "(preview unavailable)"})

            return ToolResult(
                success=True,
                data={
                    "query": query,
                    "matching_files": matching_files,
                    "file_count": len(matching_files),
                    "snippets": snippets,
                }
            )
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Search timed out after 10 seconds")
        except Exception as e:
            return ToolResult(success=False, error=f"Workspace search failed: {e}")


# Instantiate tools for registration
checkpoint_tool = CheckpointTool()
checkpoint_and_continue_tool = CheckpointAndContinueTool()
compress_context_tool = CompressContextTool()
get_context_stats_tool = GetContextStatsTool()
terminal_exec_tool = TerminalExecTool()
file_upload_tool = FileUploadTool()
file_read_tool = FileReadTool()
file_list_tool = FileListTool()
file_write_tool = FileWriteTool()
set_mode_tool = SetModeTool()
search_memory_tool = SearchMemoryTool()
list_checkpoints_tool = ListCheckpointsTool()
read_checkpoint_tool = ReadCheckpointTool()
recall_episodes_tool = RecallEpisodesTool()
search_workspace_tool = SearchWorkspaceTool()

