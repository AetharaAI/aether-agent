"""
Terminal WebSocket Handler

================================================================================
Provides real-time terminal access to sandboxed Docker containers.
Uses docker-compose exec for secure command execution.
================================================================================
"""

import asyncio
import json
import logging
import pty
import os
import struct
import fcntl
import termios
import select
from datetime import datetime
from typing import Dict, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class TerminalSession:
    """
    Manages a single terminal session in a sandboxed Docker container.
    Uses PTY for proper terminal emulation.
    """
    
    def __init__(self, session_id: str, workspace_dir: str = "/tmp/aether_workspace"):
        self.session_id = session_id
        self.workspace_dir = workspace_dir
        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.process: Optional[asyncio.subprocess.Process] = None
        self.websocket: Optional[WebSocket] = None
        self.running = False
        
    async def start(self, websocket: WebSocket):
        """Start the terminal session."""
        self.websocket = websocket
        
        # Create PTY
        self.master_fd, self.slave_fd = pty.openpty()
        
        # Set terminal size
        self._set_terminal_size(80, 24)
        
        # Start shell in sandboxed Docker container
        # This runs a shell inside the aether-api container for sandboxing
        self.process = await asyncio.create_subprocess_exec(
            "docker", "exec", "-i", "-t", "aether-api",
            "/bin/bash",
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            cwd=self.workspace_dir,
        )
        
        os.close(self.slave_fd)
        self.slave_fd = None
        self.running = True
        
        logger.info(f"Terminal session started: {self.session_id}")
        
        # Start output reader
        asyncio.create_task(self._read_output())
        
    def _set_terminal_size(self, cols: int, rows: int):
        """Set the terminal size."""
        if self.master_fd is None:
            return
            
        size = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, size)
        
    async def _read_output(self):
        """Read output from the PTY and send to WebSocket."""
        while self.running and self.master_fd:
            try:
                # Check if data is available
                readable, _, _ = select.select([self.master_fd], [], [], 0.1)
                
                if readable:
                    data = os.read(self.master_fd, 1024)
                    if data:
                        # Decode and send to WebSocket
                        text = data.decode("utf-8", errors="replace")
                        if self.websocket:
                            await self.websocket.send_json({
                                "type": "output",
                                "data": text,
                            })
                    else:
                        # EOF
                        break
                        
            except OSError:
                break
            except Exception as e:
                logger.error(f"Error reading terminal output: {e}")
                break
                
        self.running = False
        
    async def handle_input(self, data: str):
        """Handle input from the WebSocket."""
        if self.master_fd and self.running:
            try:
                os.write(self.master_fd, data.encode("utf-8"))
            except OSError as e:
                logger.error(f"Error writing to terminal: {e}")
                
    async def handle_resize(self, cols: int, rows: int):
        """Handle terminal resize."""
        self._set_terminal_size(cols, rows)
        
    async def stop(self):
        """Stop the terminal session."""
        self.running = False
        
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
            except Exception as e:
                logger.error(f"Error stopping terminal process: {e}")
                
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
                
        logger.info(f"Terminal session stopped: {self.session_id}")


class TerminalManager:
    """Manages all active terminal sessions."""
    
    def __init__(self):
        self.sessions: Dict[str, TerminalSession] = {}
        
    async def handle_terminal_session(self, websocket: WebSocket, session_id: str):
        """Handle a new terminal WebSocket connection."""
        await websocket.accept()
        
        # Create new session
        session = TerminalSession(session_id)
        self.sessions[session_id] = session
        
        try:
            await session.start(websocket)
            
            # Handle messages
            while session.running:
                try:
                    message = await websocket.receive_json()
                    msg_type = message.get("type")
                    
                    if msg_type == "input":
                        await session.handle_input(message.get("data", ""))
                    elif msg_type == "resize":
                        await session.handle_resize(
                            message.get("cols", 80),
                            message.get("rows", 24)
                        )
                        
                except Exception as e:
                    logger.error(f"Error handling terminal message: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Terminal session error: {e}")
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
            
        finally:
            await session.stop()
            if session_id in self.sessions:
                del self.sessions[session_id]
                
    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        """Get an active terminal session."""
        return self.sessions.get(session_id)


# Singleton instance
_manager: Optional[TerminalManager] = None


def get_terminal_manager() -> TerminalManager:
    """Get or create the global terminal manager."""
    global _manager
    if _manager is None:
        _manager = TerminalManager()
    return _manager
