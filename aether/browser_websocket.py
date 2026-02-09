"""
Browser WebSocket Handler

================================================================================
Provides real-time browser automation via Playwright.
Supports screenshot streaming, click actions, form input, and navigation.
================================================================================
"""

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import Dict, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# Try to import playwright
try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Browser automation disabled.")


class BrowserSession:
    """
    Manages a single browser session via Playwright.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.websocket: Optional[WebSocket] = None
        self.running = False
        
    async def start(self, websocket: WebSocket):
        """Start the browser session."""
        if not PLAYWRIGHT_AVAILABLE:
            await websocket.send_json({
                "type": "error",
                "message": "Playwright not installed. Run: pip install playwright && playwright install chromium"
            })
            return False
            
        self.websocket = websocket
        
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            self.page = await self.browser.new_page(
                viewport={'width': 1280, 'height': 720}
            )
            
            # Set up event listeners
            self.page.on("load", self._on_page_load)
            self.page.on("console", self._on_console)
            
            self.running = True
            logger.info(f"Browser session started: {self.session_id}")
            
            await self.websocket.send_json({
                "type": "log",
                "message": "Browser session started"
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
            await self.websocket.send_json({
                "type": "error",
                "message": f"Failed to start browser: {str(e)}"
            })
            return False
    
    async def _on_page_load(self, page):
        """Handle page load event."""
        if not self.websocket:
            return
            
        try:
            url = page.url
            title = await page.title()
            
            await self.websocket.send_json({
                "type": "page_info",
                "url": url,
                "title": title,
            })
            
            # Auto-capture screenshot on load
            await self.capture_screenshot()
            
        except Exception as e:
            logger.error(f"Error handling page load: {e}")
    
    async def _on_console(self, msg):
        """Handle console messages."""
        if not self.websocket:
            return
            
        try:
            text = msg.text
            await self.websocket.send_json({
                "type": "log",
                "message": f"[Console] {text[:100]}"
            })
        except Exception:
            pass
    
    async def navigate(self, url: str):
        """Navigate to a URL."""
        if not self.page:
            return
            
        try:
            await self.websocket.send_json({
                "type": "log",
                "message": f"Navigating to: {url}"
            })
            
            await self.page.goto(url, wait_until="networkidle")
            
            await self.websocket.send_json({
                "type": "action_complete",
                "action": "navigate"
            })
            
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            await self.websocket.send_json({
                "type": "error",
                "message": f"Navigation failed: {str(e)}"
            })
    
    async def click(self, x: int, y: int):
        """Click at coordinates (percentage-based)."""
        if not self.page:
            return
            
        try:
            viewport = self.page.viewport_size
            if viewport:
                px = int((x / 100) * viewport['width'])
                py = int((y / 100) * viewport['height'])
                
                await self.websocket.send_json({
                    "type": "log",
                    "message": f"Clicking at ({px}, {py})"
                })
                
                await self.page.mouse.click(px, py)
                await asyncio.sleep(0.5)  # Wait for any navigation
                
                await self.websocket.send_json({
                    "type": "action_complete",
                    "action": "click"
                })
                
                # Capture screenshot after click
                await self.capture_screenshot()
                
        except Exception as e:
            logger.error(f"Click error: {e}")
            await self.websocket.send_json({
                "type": "error",
                "message": f"Click failed: {str(e)}"
            })
    
    async def type_text(self, selector: str, text: str):
        """Type text into an element."""
        if not self.page:
            return
            
        try:
            await self.websocket.send_json({
                "type": "log",
                "message": f"Typing into {selector}"
            })
            
            await self.page.fill(selector, text)
            
            await self.websocket.send_json({
                "type": "action_complete",
                "action": "type"
            })
            
            await self.capture_screenshot()
            
        except Exception as e:
            logger.error(f"Type error: {e}")
            await self.websocket.send_json({
                "type": "error",
                "message": f"Type failed: {str(e)}"
            })
    
    async def scroll(self, direction: str = "down"):
        """Scroll the page."""
        if not self.page:
            return
            
        try:
            amount = 500 if direction == "down" else -500
            await self.page.evaluate(f"window.scrollBy(0, {amount})")
            await asyncio.sleep(0.3)
            await self.capture_screenshot()
            
        except Exception as e:
            logger.error(f"Scroll error: {e}")
    
    async def go_back(self):
        """Go back in browser history."""
        if not self.page:
            return
            
        try:
            await self.page.go_back(wait_until="networkidle")
            await self.websocket.send_json({
                "type": "action_complete",
                "action": "go_back"
            })
        except Exception as e:
            await self.websocket.send_json({
                "type": "error",
                "message": f"Go back failed: {str(e)}"
            })
    
    async def go_forward(self):
        """Go forward in browser history."""
        if not self.page:
            return
            
        try:
            await self.page.go_forward(wait_until="networkidle")
            await self.websocket.send_json({
                "type": "action_complete",
                "action": "go_forward"
            })
        except Exception as e:
            await self.websocket.send_json({
                "type": "error",
                "message": f"Go forward failed: {str(e)}"
            })
    
    async def refresh(self):
        """Refresh the page."""
        if not self.page:
            return
            
        try:
            await self.page.reload(wait_until="networkidle")
            await self.websocket.send_json({
                "type": "action_complete",
                "action": "refresh"
            })
        except Exception as e:
            await self.websocket.send_json({
                "type": "error",
                "message": f"Refresh failed: {str(e)}"
            })
    
    async def capture_screenshot(self):
        """Capture a screenshot of the current page."""
        if not self.page:
            return
            
        try:
            screenshot = await self.page.screenshot(
                type="png",
                full_page=False
            )
            
            # Encode to base64
            b64_screenshot = base64.b64encode(screenshot).decode()
            
            await self.websocket.send_json({
                "type": "screenshot",
                "data": b64_screenshot,
            })
            
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            await self.websocket.send_json({
                "type": "error",
                "message": f"Screenshot failed: {str(e)}"
            })
    
    async def get_page_content(self) -> str:
        """Get the text content of the page."""
        if not self.page:
            return ""
            
        try:
            # Extract visible text
            content = await self.page.evaluate("""
                () => {
                    const body = document.body;
                    return body.innerText.slice(0, 5000);
                }
            """)
            return content
        except Exception as e:
            logger.error(f"Get content error: {e}")
            return ""
    
    async def stop(self):
        """Stop the browser session."""
        self.running = False
        
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error stopping browser: {e}")
            
        logger.info(f"Browser session stopped: {self.session_id}")


class BrowserManager:
    """Manages all active browser sessions."""
    
    def __init__(self):
        self.sessions: Dict[str, BrowserSession] = {}
        
    async def handle_browser_session(self, websocket: WebSocket, session_id: str):
        """Handle a new browser WebSocket connection."""
        await websocket.accept()
        
        # Create new session
        session = BrowserSession(session_id)
        self.sessions[session_id] = session
        
        try:
            # Start browser
            if not await session.start(websocket):
                return
            
            # Handle messages
            while session.running:
                try:
                    message = await websocket.receive_json()
                    msg_type = message.get("type")
                    
                    if msg_type == "action":
                        action = message.get("action")
                        params = message.get("params", {})
                        
                        if action == "navigate":
                            await session.navigate(params.get("url", ""))
                        elif action == "click":
                            await session.click(params.get("x", 0), params.get("y", 0))
                        elif action == "type":
                            await session.type_text(
                                params.get("selector", ""),
                                params.get("text", "")
                            )
                        elif action == "scroll":
                            await session.scroll(params.get("direction", "down"))
                        elif action == "go_back":
                            await session.go_back()
                        elif action == "go_forward":
                            await session.go_forward()
                        elif action == "refresh":
                            await session.refresh()
                        elif action == "screenshot":
                            await session.capture_screenshot()
                            
                except Exception as e:
                    logger.error(f"Error handling browser message: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Browser session error: {e}")
            
        finally:
            await session.stop()
            if session_id in self.sessions:
                del self.sessions[session_id]
                
    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        """Get an active browser session."""
        return self.sessions.get(session_id)


# Singleton instance
_manager: Optional[BrowserManager] = None


def get_browser_manager() -> BrowserManager:
    """Get or create the global browser manager."""
    global _manager
    if _manager is None:
        _manager = BrowserManager()
    return _manager
