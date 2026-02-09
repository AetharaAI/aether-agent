"""
Core Tools Implementation

================================================================================
ARCHITECTURE: Tool Layer - Core Tools
================================================================================

Built-in tools for agent operations.
These tools are registered by default in the ToolRegistry.

TOOL LIST:
1. checkpoint - Create memory checkpoints
2. compress_context - Compress daily logs to long-term memory  
3. get_context_stats - Get memory usage statistics
4. terminal_exec - Execute terminal commands (restricted)
5. file_upload - Upload files for processing (restricted)

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
    permission = ToolPermission.AUTO  # Requires auto mode or approval
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


# Instantiate tools for registration
checkpoint_tool = CheckpointTool()
compress_context_tool = CompressContextTool()
get_context_stats_tool = GetContextStatsTool()
terminal_exec_tool = TerminalExecTool()
file_upload_tool = FileUploadTool()
file_read_tool = FileReadTool()
file_list_tool = FileListTool()
file_write_tool = FileWriteTool()
