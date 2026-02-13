
import os
import logging
from typing import Dict, Optional
from .client import LSPClient

logger = logging.getLogger("aether.lsp")

class LSPManager:
    """
    Manages LSP clients for different languages.
    """
    
    SERVER_COMMANDS = {
        "python": ["python3", "-m", "pylsp"],
        # Add more later: "go": ["gopls"], "typescript": ["typescript-language-server", "--stdio"]
    }
    
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.clients: Dict[str, LSPClient] = {}
        
    def start_client(self, language: str):
        """Start an LSP client for a specific language."""
        if language in self.clients:
            return self.clients[language]
            
        cmd = self.SERVER_COMMANDS.get(language)
        if not cmd:
            logger.warning(f"No LSP server command configured for {language}")
            return None
            
        try:
            client = LSPClient(cmd, self.workspace_root)
            client.start()
            self.clients[language] = client
            logger.info(f"Started LSP client for {language}")
            return client
        except Exception as e:
            logger.error(f"Failed to start LSP for {language}: {e}")
            return None

    def get_client(self, ext: str) -> Optional[LSPClient]:
        """Get client based on file extension."""
        language = self._map_ext_to_lang(ext)
        if not language:
            return None
            
        if language not in self.clients:
            return self.start_client(language)
            
        return self.clients[language]
        
    def _map_ext_to_lang(self, ext: str) -> Optional[str]:
        if ext in [".py"]: return "python"
        if ext in [".js", ".ts", ".tsx"]: return "typescript"
        if ext in [".go"]: return "go"
        return None

    def stop_all(self):
        """Stop all running clients."""
        for lang, client in self.clients.items():
            logger.info(f"Stopping LSP for {lang}")
            client.stop()
        self.clients.clear()
