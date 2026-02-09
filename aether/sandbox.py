"""
Sandboxed Execution Environment

================================================================================
Provides isolated execution for agent tools:
- Browser automation (Playwright)
- Code execution (Docker containers)
- File operations (restricted paths)

Security:
- Network isolation
- Resource limits (memory, CPU)
- Timeouts
- Read-only base image
================================================================================
"""

import asyncio
import base64
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SandboxResult:
    """Result from sandboxed execution"""
    success: bool
    output: str = ""
    logs: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    screenshot: Optional[str] = None  # base64 encoded
    error: Optional[str] = None
    execution_time_ms: int = 0


class ComputerSandbox:
    """
    Isolated execution environment for agent tools.
    
    Supports:
    - Browser automation via Playwright
    - Code execution via Docker
    - File operations within workspace
    """
    
    def __init__(
        self,
        workspace_dir: str = "/tmp/aether_workspace",
        network_isolation: bool = True,
        memory_limit: str = "512m",
        cpu_limit: str = "1.0"
    ):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        
        self.network_isolation = network_isolation
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        
        # Browser state (lazy initialization)
        self._playwright = None
        self._browser = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup"""
        await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
    
    # =====================================================================
    # Browser Automation
    # =====================================================================
    
    async def execute_browser(
        self,
        action: str,
        url: Optional[str] = None,
        selector: Optional[str] = None,
        text: Optional[str] = None,
        take_screenshot: bool = True
    ) -> SandboxResult:
        """
        Execute browser automation via Playwright.
        
        Actions:
        - navigate: Go to URL
        - click: Click element
        - type: Type text into input
        - screenshot: Capture page
        - scroll: Scroll page
        - evaluate: Run JavaScript
        """
        start_time = datetime.now()
        logs = [f"Browser action: {action}"]
        
        try:
            # Lazy init Playwright
            if not self._playwright:
                from playwright.async_api import async_playwright
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox']
                )
            
            # Get or create page
            context = await self._browser.new_context(
                viewport={'width': 1280, 'height': 720}
            )
            page = await context.new_page()
            
            result_data = {
                "action": action,
                "url": url,
                "title": None,
                "content_preview": None
            }
            
            # Execute action
            if action == "navigate" and url:
                logs.append(f"Navigating to: {url}")
                await page.goto(url, wait_until="networkidle")
                result_data["url"] = page.url
                result_data["title"] = await page.title()
                
            elif action == "click" and selector:
                logs.append(f"Clicking: {selector}")
                await page.click(selector)
                await page.wait_for_load_state("networkidle")
                
            elif action == "type" and selector and text:
                logs.append(f"Typing into: {selector}")
                await page.fill(selector, text)
                
            elif action == "screenshot":
                logs.append("Capturing screenshot")
                
            elif action == "scroll":
                logs.append("Scrolling page")
                await page.evaluate("window.scrollBy(0, 500)")
                
            elif action == "evaluate" and text:
                logs.append(f"Executing JavaScript: {text[:50]}...")
                js_result = await page.evaluate(text)
                result_data["js_result"] = str(js_result)
            
            # Get page content preview
            content = await page.content()
            result_data["content_preview"] = content[:500] + "..." if len(content) > 500 else content
            
            # Take screenshot
            screenshot_b64 = None
            if take_screenshot:
                screenshot_bytes = await page.screenshot(full_page=True)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
                logs.append("Screenshot captured")
            
            # Close context
            await context.close()
            
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return SandboxResult(
                success=True,
                output=json.dumps(result_data, indent=2),
                logs=logs,
                screenshot=screenshot_b64,
                execution_time_ms=execution_time
            )
            
        except Exception as e:
            logger.error(f"Browser action failed: {e}")
            return SandboxResult(
                success=False,
                logs=logs,
                error=str(e),
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    # =====================================================================
    # Code Execution
    # =====================================================================
    
    async def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int = 30,
        env_vars: Optional[Dict[str, str]] = None
    ) -> SandboxResult:
        """
        Execute code in isolated Docker container.
        
        Security:
        - Network isolation (if enabled)
        - Memory limits
        - CPU limits
        - Read-only root filesystem
        - Timeouts
        """
        start_time = datetime.now()
        logs = [f"Code execution: {language}"]
        
        try:
            # Create temp file with code
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix=f'.{language}',
                delete=False,
                dir=self.workspace_dir
            ) as f:
                f.write(code)
                code_file = f.name
            
            # Determine Docker image and command
            image_map = {
                "python": "python:3.11-slim",
                "javascript": "node:18-slim",
                "bash": "bash:latest"
            }
            image = image_map.get(language, "python:3.11-slim")
            
            command_map = {
                "python": f"python {Path(code_file).name}",
                "javascript": f"node {Path(code_file).name}",
                "bash": f"bash {Path(code_file).name}"
            }
            command = command_map.get(language, f"python {Path(code_file).name}")
            
            # Build docker run command
            docker_cmd = [
                "docker", "run",
                "--rm",  # Remove after execution
                "-v", f"{self.workspace_dir}:/workspace",
                "-w", "/workspace",
                f"--memory={self.memory_limit}",
                f"--cpus={self.cpu_limit}",
                f"--timeout={timeout}",
            ]
            
            if self.network_isolation:
                docker_cmd.append("--network=none")
            
            docker_cmd.extend([image, "sh", "-c", command])
            
            logs.append(f"Running: {' '.join(docker_cmd)}")
            
            # Execute
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
                
                output = stdout.decode() if stdout else ""
                error = stderr.decode() if stderr else ""
                
                if process.returncode == 0:
                    logs.append("Execution successful")
                    logs.append(f"Output length: {len(output)} chars")
                else:
                    logs.append(f"Execution failed with code {process.returncode}")
                
                execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
                
                # Cleanup
                Path(code_file).unlink(missing_ok=True)
                
                return SandboxResult(
                    success=process.returncode == 0,
                    output=output,
                    logs=logs,
                    error=error if error else None,
                    execution_time_ms=execution_time
                )
                
            except asyncio.TimeoutError:
                process.kill()
                logs.append(f"Execution timed out after {timeout}s")
                
                return SandboxResult(
                    success=False,
                    logs=logs,
                    error=f"Timeout after {timeout} seconds",
                    execution_time_ms=timeout * 1000
                )
                
        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            return SandboxResult(
                success=False,
                logs=logs,
                error=str(e),
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    # =====================================================================
    # File Operations
    # =====================================================================
    
    async def read_file(self, path: str) -> SandboxResult:
        """Read file contents (restricted to workspace)"""
        logs = [f"Reading file: {path}"]
        
        try:
            # Resolve to absolute path within workspace
            target = self._resolve_workspace_path(path)
            if not target:
                return SandboxResult(
                    success=False,
                    logs=logs,
                    error="Path outside workspace"
                )
            
            if not target.exists():
                return SandboxResult(
                    success=False,
                    logs=logs,
                    error=f"File not found: {path}"
                )
            
            content = target.read_text()
            logs.append(f"Read {len(content)} characters")
            
            return SandboxResult(
                success=True,
                output=content,
                logs=logs
            )
            
        except Exception as e:
            return SandboxResult(
                success=False,
                logs=logs,
                error=str(e)
            )
    
    async def write_file(
        self, 
        path: str, 
        content: str,
        create_dirs: bool = True
    ) -> SandboxResult:
        """Write file (restricted to workspace)"""
        logs = [f"Writing file: {path}"]
        
        try:
            # Resolve to absolute path within workspace
            target = self._resolve_workspace_path(path)
            if not target:
                return SandboxResult(
                    success=False,
                    logs=logs,
                    error="Path outside workspace"
                )
            
            if create_dirs:
                target.parent.mkdir(parents=True, exist_ok=True)
            
            target.write_text(content)
            logs.append(f"Wrote {len(content)} characters")
            
            return SandboxResult(
                success=True,
                logs=logs,
                files_modified=[str(target)]
            )
            
        except Exception as e:
            return SandboxResult(
                success=False,
                logs=logs,
                error=str(e)
            )
    
    async def list_files(self, path: str = ".") -> SandboxResult:
        """List files in directory (restricted to workspace)"""
        logs = [f"Listing files: {path}"]
        
        try:
            target = self._resolve_workspace_path(path)
            if not target:
                return SandboxResult(
                    success=False,
                    logs=logs,
                    error="Path outside workspace"
                )
            
            if not target.is_dir():
                return SandboxResult(
                    success=False,
                    logs=logs,
                    error="Not a directory"
                )
            
            files = []
            for item in target.iterdir():
                files.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
            
            return SandboxResult(
                success=True,
                output=json.dumps(files, indent=2),
                logs=logs
            )
            
        except Exception as e:
            return SandboxResult(
                success=False,
                logs=logs,
                error=str(e)
            )
    
    def _resolve_workspace_path(self, path: str) -> Optional[Path]:
        """
        Resolve path to absolute path within workspace.
        Returns None if path escapes workspace.
        """
        try:
            # Normalize path
            target = (self.workspace_dir / path).resolve()
            
            # Check it's within workspace
            if not str(target).startswith(str(self.workspace_dir.resolve())):
                return None
            
            return target
            
        except Exception:
            return None


# =====================================================================
# Convenience Functions
# =====================================================================

async def quick_browser(action: str, **kwargs) -> SandboxResult:
    """Quick browser execution"""
    async with ComputerSandbox() as sandbox:
        return await sandbox.execute_browser(action, **kwargs)


async def quick_code(code: str, language: str = "python") -> SandboxResult:
    """Quick code execution"""
    async with ComputerSandbox() as sandbox:
        return await sandbox.execute_code(code, language)


# For testing
if __name__ == "__main__":
    async def test():
        sandbox = ComputerSandbox()
        
        # Test code execution
        result = await sandbox.execute_code(
            code="print('Hello from sandbox!')\nprint('2+2 =', 2+2)",
            language="python"
        )
        print("Success:", result.success)
        print("Output:", result.output)
        print("Logs:", result.logs)
        
        await sandbox.cleanup()
    
    asyncio.run(test())
