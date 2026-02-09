"""
Real Tool Implementations

================================================================================
Actual tool execution (not simulated).
These tools are called by the LLM via native function calling.
================================================================================
"""

import asyncio
import json
import logging
import subprocess
import os
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# Terminal Tool
# =============================================================================

async def terminal_execute(command: str, timeout: int = 60) -> str:
    """
    Execute a terminal command.
    
    Args:
        command: Shell command to execute
        timeout: Maximum execution time in seconds
        
    Returns:
        Command output or error message
    """
    logger.info(f"Executing command: {command}")
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=os.getcwd()
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            return f"Error: Command timed out after {timeout} seconds"
        
        output = ""
        if stdout:
            output += stdout.decode('utf-8', errors='replace')
        if stderr:
            output += "\n[stderr]\n" + stderr.decode('utf-8', errors='replace')
        
        if process.returncode != 0:
            output += f"\n[Exit code: {process.returncode}]"
        
        return output[:5000]  # Truncate very long outputs
        
    except Exception as e:
        return f"Error executing command: {str(e)}"


# Schema for function calling
terminal_execute.__tool_schema__ = {
    "description": "Execute a terminal/shell command",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Maximum execution time in seconds (default: 60)",
                "default": 60
            }
        },
        "required": ["command"]
    }
}


# =============================================================================
# File Tools
# =============================================================================

async def file_read(path: str) -> str:
    """
    Read a file's contents.
    
    Args:
        path: Path to the file
        
    Returns:
        File contents or error message
    """
    logger.info(f"Reading file: {path}")
    
    try:
        file_path = Path(path)
        
        if not file_path.exists():
            return f"Error: File '{path}' not found"
        
        if not file_path.is_file():
            return f"Error: '{path}' is not a file"
        
        # Read file
        content = file_path.read_text(encoding='utf-8', errors='replace')
        
        # Truncate very large files
        if len(content) > 10000:
            content = content[:10000] + "\n\n[File truncated - too large]"
        
        return content
        
    except Exception as e:
        return f"Error reading file: {str(e)}"


file_read.__tool_schema__ = {
    "description": "Read the contents of a file",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to read"
            }
        },
        "required": ["path"]
    }
}


async def file_write(path: str, content: str, append: bool = False) -> str:
    """
    Write content to a file.
    
    Args:
        path: Path to the file
        content: Content to write
        append: If True, append to file instead of overwriting
        
    Returns:
        Success message or error
    """
    logger.info(f"Writing file: {path}")
    
    try:
        file_path = Path(path)
        
        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        mode = 'a' if append else 'w'
        with open(file_path, mode, encoding='utf-8') as f:
            f.write(content)
        
        action = "appended to" if append else "wrote"
        return f"Successfully {action} {path} ({len(content)} bytes)"
        
    except Exception as e:
        return f"Error writing file: {str(e)}"


file_write.__tool_schema__ = {
    "description": "Write or append content to a file",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file"
            },
            "content": {
                "type": "string",
                "description": "Content to write"
            },
            "append": {
                "type": "boolean",
                "description": "If true, append to file instead of overwriting",
                "default": False
            }
        },
        "required": ["path", "content"]
    }
}


async def file_list(directory: str = ".") -> str:
    """
    List files in a directory.
    
    Args:
        directory: Directory path (default: current directory)
        
    Returns:
        List of files or error message
    """
    logger.info(f"Listing directory: {directory}")
    
    try:
        dir_path = Path(directory)
        
        if not dir_path.exists():
            return f"Error: Directory '{directory}' not found"
        
        if not dir_path.is_dir():
            return f"Error: '{directory}' is not a directory"
        
        items = []
        for item in dir_path.iterdir():
            item_type = "📁" if item.is_dir() else "📄"
            size = ""
            if item.is_file():
                size_bytes = item.stat().st_size
                if size_bytes < 1024:
                    size = f" ({size_bytes} B)"
                elif size_bytes < 1024 * 1024:
                    size = f" ({size_bytes / 1024:.1f} KB)"
                else:
                    size = f" ({size_bytes / (1024 * 1024):.1f} MB)"
            
            items.append(f"{item_type} {item.name}{size}")
        
        if not items:
            return "Directory is empty"
        
        return "\n".join(sorted(items))
        
    except Exception as e:
        return f"Error listing directory: {str(e)}"


file_list.__tool_schema__ = {
    "description": "List files and directories",
    "parameters": {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "Directory path to list (default: current directory)",
                "default": "."
            }
        }
    }
}


# =============================================================================
# Python Execution Tool
# =============================================================================

async def python_execute(code: str) -> str:
    """
    Execute Python code.
    
    Args:
        code: Python code to execute
        
    Returns:
        Execution output or error
    """
    logger.info(f"Executing Python code: {code[:50]}...")
    
    # Write code to temp file
    temp_file = f"/tmp/aether_python_{os.getpid()}.py"
    
    try:
        with open(temp_file, 'w') as f:
            f.write(code)
        
        # Execute in subprocess
        process = await asyncio.create_subprocess_exec(
            'python3', temp_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30
        )
        
        output = ""
        if stdout:
            output += stdout.decode('utf-8', errors='replace')
        if stderr:
            output += "\n[stderr]\n" + stderr.decode('utf-8', errors='replace')
        
        return output[:5000] or "(No output)"
        
    except asyncio.TimeoutError:
        return "Error: Python execution timed out (30s limit)"
    except Exception as e:
        return f"Error executing Python: {str(e)}"
    finally:
        # Cleanup
        try:
            os.remove(temp_file)
        except:
            pass


python_execute.__tool_schema__ = {
    "description": "Execute Python code and return the output",
    "parameters": {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Python code to execute"
            }
        },
        "required": ["code"]
    }
}


# =============================================================================
# Browser Tool (Placeholder - requires Playwright)
# =============================================================================

async def browser_navigate(url: str) -> str:
    """
    Navigate to a URL in the browser.
    
    Args:
        url: URL to navigate to
        
    Returns:
        Page content or error
    """
    logger.info(f"Browser navigate: {url}")
    
    # This would integrate with the existing browser_websocket
    # For now, return placeholder
    return f"Browser navigation to {url} requested. Use the Browser panel to see results."


browser_navigate.__tool_schema__ = {
    "description": "Navigate the browser to a URL",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to navigate to"
            }
        },
        "required": ["url"]
    }
}


# =============================================================================
# Web Search Tool (Placeholder)
# =============================================================================

async def web_search(query: str, num_results: int = 5) -> str:
    """
    Search the web.
    
    Args:
        query: Search query
        num_results: Number of results to return
        
    Returns:
        Search results
    """
    logger.info(f"Web search: {query}")
    
    # This would integrate with Brave Search API or similar
    # For now, return placeholder
    return f"Web search for '{query}' would be performed here. (Requires search API integration)"


web_search.__tool_schema__ = {
    "description": "Search the web for information",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results (default: 5)",
                "default": 5
            }
        },
        "required": ["query"]
    }
}


# =============================================================================
# Tool Registry
# =============================================================================

def get_real_tools() -> Dict[str, Any]:
    """Get all real tool functions."""
    return {
        "terminal_execute": terminal_execute,
        "file_read": file_read,
        "file_write": file_write,
        "file_list": file_list,
        "python_execute": python_execute,
        "browser_navigate": browser_navigate,
        "web_search": web_search,
    }
