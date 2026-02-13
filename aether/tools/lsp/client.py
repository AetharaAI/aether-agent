
import os
import json
import logging
import subprocess
import threading
import time
from typing import Dict, Any, Optional, List, Union

logger = logging.getLogger("aether.lsp")

class LSPClient:
    """
    A simple JSON-RPC client for Language Server Protocol (LSP).
    Communicates via stdio with the language server process.
    """
    
    def __init__(self, command: List[str], workspace_path: str):
        self.command = command
        self.workspace_path = os.path.abspath(workspace_path)
        self.process: Optional[subprocess.Popen] = None
        self._seq = 1
        self._lock = threading.Lock()
        self._responses: Dict[int, Any] = {}
        self._notifications: List[Dict[str, Any]] = []
        self._running = False
        self._reader_thread: Optional[threading.Thread] = None

    def start(self):
        """Start the LSP server process."""
        logger.info(f"Starting LSP server: {' '.join(self.command)}")
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False, # Use bytes for protocol robustness
                bufsize=0   # Unbuffered
            )
            self._running = True
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()
            
            # Initialize lifecycle
            self.initialize()
            
        except Exception as e:
            logger.error(f"Failed to start LSP server: {e}")
            raise

    def stop(self):
        """Stop the LSP server."""
        self._running = False
        if self.process:
            try:
                self.shutdown()
                self.exit()
            except:
                pass
            self.process.terminate()
            self.process = None

    def initialize(self):
        """Send initialize request."""
        params = {
            "processId": os.getpid(),
            "rootUri": f"file://{self.workspace_path}",
            "capabilities": {
                "textDocument": {
                    "synchronization": {
                        "dynamicRegistration": True,
                        "willSave": True,
                        "didSave": True,
                        "didClose": True
                    },
                    "completion": {"dynamicRegistration": True},
                    "hover": {"dynamicRegistration": True},
                    "signatureHelp": {"dynamicRegistration": True},
                    "definition": {"dynamicRegistration": True},
                    "references": {"dynamicRegistration": True},
                    "documentHighlight": {"dynamicRegistration": True},
                    "documentSymbol": {"dynamicRegistration": True},
                    "formatting": {"dynamicRegistration": True}
                },
                "workspace": {
                    "symbol": {"dynamicRegistration": True},
                    "configuration": True
                }
            }
        }
        
        # Initialize request
        result = self.call("initialize", params)
        
        # Initialized notification
        self.notify("initialized", {})
        
        return result

    def shutdown(self):
        """Send shutdown request."""
        return self.call("shutdown", {})

    def exit(self):
        """Send exit notification."""
        self.notify("exit", {})

    def open_file(self, path: str, content: str):
        """Notify server that a file was opened/created."""
        uri = f"file://{os.path.abspath(path)}"
        params = {
            "textDocument": {
                "uri": uri,
                "languageId": "python", # TODO: Detect language
                "version": 1,
                "text": content
            }
        }
        self.notify("textDocument/didOpen", params)

    def did_change(self, path: str, content: str, version: int):
        """Notify server of file changes."""
        uri = f"file://{os.path.abspath(path)}"
        params = {
            "textDocument": {
                "uri": uri,
                "version": version
            },
            "contentChanges": [{"text": content}]
        }
        self.notify("textDocument/didChange", params)

    def get_definition(self, path: str, line: int, character: int):
        """Get definition location."""
        return self._make_request("textDocument/definition", path, line, character)

    def get_references(self, path: str, line: int, character: int):
        """Get references."""
        return self._make_request("textDocument/references", path, line, character, extra={"context": {"includeDeclaration": True}})

    def get_hover(self, path: str, line: int, character: int):
        """Get hover info."""
        return self._make_request("textDocument/hover", path, line, character)

    def get_document_symbols(self, path: str):
        """Get symbols in document."""
        uri = f"file://{os.path.abspath(path)}"
        return self.call("textDocument/documentSymbol", {"textDocument": {"uri": uri}})

    def _make_request(self, method: str, path: str, line: int, character: int, extra: dict = None):
        """Helper for standard position-based requests."""
        uri = f"file://{os.path.abspath(path)}"
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character}
        }
        if extra:
            params.update(extra)
        return self.call(method, params)

    def call(self, method: str, params: Any, timeout: float = 10.0) -> Any:
        """Send a request and wait for response."""
        req_id = self._send_json(method, params, is_request=True)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self._lock:
                if req_id in self._responses:
                    response = self._responses.pop(req_id)
                    if "error" in response:
                        raise Exception(f"LSP Error: {response['error']}")
                    return response.get("result")
            time.sleep(0.01)
        
        raise TimeoutError(f"Init request {method} timed out")

    def notify(self, method: str, params: Any):
        """Send a notification (no response expected)."""
        self._send_json(method, params, is_request=False)

    def _send_json(self, method: str, params: Any, is_request: bool = True) -> Optional[int]:
        """Send JSON-RPC message."""
        with self._lock:
            msg = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params
            }
            req_id = None
            if is_request:
                req_id = self._seq
                msg["id"] = req_id
                self._seq += 1
            
            json_str = json.dumps(msg)
            content = json_str.encode('utf-8')
            header = f"Content-Length: {len(content)}\r\n\r\n".encode('ascii')
            
            try:
                self.process.stdin.write(header + content)
                self.process.stdin.flush()
                # logger.debug(f"SENT: {msg}")
            except Exception as e:
                logger.error(f"Failed to send RPC: {e}")
                
            return req_id

    def _read_loop(self):
        """Read stdout from the LSP server."""
        while self._running and self.process:
            try:
                # Read Content-Length header
                header = b""
                while b"\r\n\r\n" not in header:
                    chunk = self.process.stdout.read(1)
                    if not chunk:
                        self._running = False
                        break
                    header += chunk
                
                if not self._running: break
                
                # Parse Content-Length
                headers = header.decode('ascii').split('\r\n')
                content_len = 0
                for h in headers:
                    if h.startswith("Content-Length:"):
                        content_len = int(h.split(":")[1].strip())
                        break
                
                if content_len > 0:
                    content = self.process.stdout.read(content_len)
                    msg = json.loads(content)
                    
                    if "id" in msg:
                        with self._lock:
                            self._responses[msg["id"]] = msg
                    else:
                        # Notification
                        self._notifications.append(msg)
                        
            except Exception as e:
                logger.error(f"LSP Read Error: {e}")
                break
