"""
Aether Browser Control Module

Integrates OpenClaw's browser tools with the configured model's vision capabilities
for intelligent web browsing and visual page understanding.

Patent claim: Novel integration of AI vision models with browser automation
for autonomous web navigation and information extraction.
"""

import asyncio
import base64
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import json

from .nvidia_kit import NVIDIAKit, ModelResponse


@dataclass
class BrowserState:
    """Current browser state"""
    url: str
    title: str
    screenshot_path: Optional[str] = None
    markdown_content: Optional[str] = None
    visible_elements: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.visible_elements is None:
            self.visible_elements = []


@dataclass
class BrowserAction:
    """Browser action to execute"""
    action_type: str  # navigate, click, input, scroll, etc.
    params: Dict[str, Any]
    reasoning: Optional[str] = None


class BrowserControl:
    """
    Browser control with vision-powered understanding.
    
    Integrates with OpenClaw's browser tools and uses the active model's
    vision capabilities to understand and interact with web pages.
    
    Patent claim: AI-powered browser automation with visual understanding
    for autonomous web navigation and data extraction.
    """
    
    def __init__(self, nvidia_kit: NVIDIAKit):
        """
        Initialize browser control.
        
        Args:
            nvidia_kit: NVIDIAKit instance for vision capabilities
        """
        self.nvidia = nvidia_kit
        self.current_state: Optional[BrowserState] = None
        self.history: List[BrowserState] = []
    
    async def navigate(
        self,
        url: str,
        intent: str = "informational",
        focus: Optional[str] = None
    ) -> BrowserState:
        """
        Navigate to URL with vision-based understanding.
        
        Args:
            url: URL to navigate to
            intent: Purpose (navigational, informational, transactional)
            focus: Specific topic or section to focus on
            
        Returns:
            BrowserState with page information
        """
        # In production, this would call OpenClaw's browser_navigate tool
        # For now, simulate the browser state
        
        state = BrowserState(
            url=url,
            title=f"Page at {url}",
            screenshot_path=f"/tmp/screenshot_{len(self.history)}.png",
            markdown_content="# Page Content\n\nSimulated content...",
            visible_elements=[
                {"index": 1, "tag": "button", "text": "Submit"},
                {"index": 2, "tag": "input", "text": "Search..."},
            ]
        )
        
        self.current_state = state
        self.history.append(state)
        
        return state
    
    async def understand_page(
        self,
        screenshot_path: str,
        markdown_content: str,
        question: Optional[str] = None
    ) -> str:
        """
        Use vision to understand page content.
        
        Args:
            screenshot_path: Path to page screenshot
            markdown_content: Extracted markdown content
            question: Optional specific question about the page
            
        Returns:
            Understanding of the page
        """
        prompt = f"""You are analyzing a web page. Here's what we know:

**Extracted Text Content:**
{markdown_content[:2000]}  # Limit to avoid token overflow

**Task:**
"""
        
        if question:
            prompt += f"Answer this question: {question}"
        else:
            prompt += "Provide a summary of what this page is about and what actions are available."
        
        # Use vision to understand the screenshot
        response = await self.nvidia.complete_with_vision(
            messages=[
                {
                    "role": "system",
                    "content": "You are a web page analyzer. Describe what you see and extract key information."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            images=[screenshot_path],
            thinking=True
        )
        
        return response.content
    
    async def find_element(
        self,
        description: str,
        screenshot_path: str,
        visible_elements: List[Dict[str, Any]]
    ) -> Optional[int]:
        """
        Find element on page using vision and description.
        
        Args:
            description: Description of element to find (e.g., "login button")
            screenshot_path: Path to page screenshot
            visible_elements: List of visible elements with indices
            
        Returns:
            Element index or None if not found
        """
        elements_text = "\n".join([
            f"{elem['index']}: {elem['tag']} - {elem.get('text', '')}"
            for elem in visible_elements
        ])
        
        prompt = f"""Looking at this web page screenshot, find the element that matches: "{description}"

Available elements:
{elements_text}

Return ONLY the index number of the matching element, or "NOT_FOUND" if no match.
"""
        
        response = await self.nvidia.complete_with_vision(
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise element locator. Return only the index number."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            images=[screenshot_path],
            temperature=0.1  # Low temperature for precise answers
        )
        
        try:
            index = int(response.content.strip())
            return index
        except ValueError:
            return None
    
    async def plan_interaction(
        self,
        goal: str,
        screenshot_path: str,
        markdown_content: str,
        visible_elements: List[Dict[str, Any]]
    ) -> List[BrowserAction]:
        """
        Plan sequence of actions to achieve goal.
        
        Args:
            goal: What to accomplish (e.g., "fill out contact form")
            screenshot_path: Current page screenshot
            markdown_content: Extracted text content
            visible_elements: Available interactive elements
            
        Returns:
            List of planned browser actions
        """
        elements_text = "\n".join([
            f"{elem['index']}: {elem['tag']} - {elem.get('text', '')}"
            for elem in visible_elements
        ])
        
        prompt = f"""You are planning browser interactions to achieve this goal: "{goal}"

**Current Page Content:**
{markdown_content[:1000]}

**Available Interactive Elements:**
{elements_text}

**Task:**
Plan a sequence of actions to achieve the goal. Return a JSON array of actions.

Each action should have:
- action_type: "click", "input", "scroll", "navigate"
- params: relevant parameters (e.g., {{"index": 1}} for click, {{"index": 2, "text": "search query"}} for input)
- reasoning: why this action is needed

Example:
[
  {{"action_type": "input", "params": {{"index": 2, "text": "contact info"}}, "reasoning": "Fill search field"}},
  {{"action_type": "click", "params": {{"index": 1}}, "reasoning": "Submit form"}}
]
"""
        
        response = await self.nvidia.complete_with_vision(
            messages=[
                {
                    "role": "system",
                    "content": "You are a browser automation planner. Return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            images=[screenshot_path],
            thinking=True,
            temperature=0.3
        )
        
        # Parse actions from response
        try:
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            actions_data = json.loads(content)
            
            actions = [
                BrowserAction(
                    action_type=a["action_type"],
                    params=a["params"],
                    reasoning=a.get("reasoning")
                )
                for a in actions_data
            ]
            
            return actions
        
        except Exception as e:
            # Fallback: return empty action list
            return []
    
    async def extract_information(
        self,
        query: str,
        screenshot_path: str,
        markdown_content: str
    ) -> Dict[str, Any]:
        """
        Extract specific information from page using vision.
        
        Args:
            query: What information to extract
            screenshot_path: Page screenshot
            markdown_content: Extracted text
            
        Returns:
            Extracted information as structured data
        """
        prompt = f"""Extract the following information from this web page: "{query}"

**Text Content:**
{markdown_content[:2000]}

Return the information in JSON format. Be specific and accurate.
"""
        
        response = await self.nvidia.complete_with_vision(
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise information extractor. Return valid JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            images=[screenshot_path],
            thinking=True,
            temperature=0.2
        )
        
        # Parse extracted information
        try:
            content = response.content.strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
        
        except Exception:
            return {"raw_response": response.content}
    
    async def verify_action_result(
        self,
        action: BrowserAction,
        before_screenshot: str,
        after_screenshot: str
    ) -> Tuple[bool, str]:
        """
        Verify if action had expected effect using vision.
        
        Args:
            action: Action that was executed
            before_screenshot: Screenshot before action
            after_screenshot: Screenshot after action
            
        Returns:
            (success, explanation) tuple
        """
        prompt = f"""Compare these two screenshots to verify if this action succeeded:

**Action:** {action.action_type}
**Parameters:** {json.dumps(action.params)}
**Expected:** {action.reasoning}

Did the action have the expected effect? Respond with:
- "SUCCESS: <explanation>" if it worked
- "FAILURE: <explanation>" if it didn't work
"""
        
        # For vision comparison, we'd need to send both images
        # For now, simplified version with after screenshot only
        response = await self.nvidia.complete_with_vision(
            messages=[
                {
                    "role": "system",
                    "content": "You are verifying browser action results. Be precise."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            images=[after_screenshot],
            temperature=0.1
        )
        
        content = response.content.strip()
        success = content.upper().startswith("SUCCESS")
        
        return success, content
    
    async def autonomous_browse(
        self,
        goal: str,
        starting_url: str,
        max_steps: int = 10
    ) -> Dict[str, Any]:
        """
        Autonomously browse to achieve a goal.
        
        Args:
            goal: What to accomplish
            starting_url: Where to start
            max_steps: Maximum number of actions
            
        Returns:
            Results of browsing session
        """
        results = {
            "goal": goal,
            "starting_url": starting_url,
            "steps": [],
            "success": False,
            "extracted_data": {}
        }
        
        # Navigate to starting URL
        state = await self.navigate(starting_url)
        
        for step in range(max_steps):
            # Understand current page
            understanding = await self.understand_page(
                state.screenshot_path,
                state.markdown_content,
                question=f"How can I achieve this goal: {goal}"
            )
            
            results["steps"].append({
                "step": step + 1,
                "url": state.url,
                "understanding": understanding
            })
            
            # Check if goal is achieved
            if "goal achieved" in understanding.lower() or "completed" in understanding.lower():
                results["success"] = True
                break
            
            # Plan next actions
            actions = await self.plan_interaction(
                goal,
                state.screenshot_path,
                state.markdown_content,
                state.visible_elements
            )
            
            if not actions:
                break
            
            # Execute first action (in production, would execute via OpenClaw tools)
            action = actions[0]
            results["steps"][-1]["action"] = {
                "type": action.action_type,
                "params": action.params,
                "reasoning": action.reasoning
            }
            
            # Simulate state update (in production, would get new state from browser)
            # For now, just continue loop
        
        return results


class BrowserToolIntegration:
    """
    Integration layer between Aether and OpenClaw browser tools.
    
    This class wraps OpenClaw's browser tools and adds vision-powered
    intelligence via the configured model.
    """
    
    def __init__(self, browser_control: BrowserControl):
        self.browser = browser_control
    
    async def smart_navigate(
        self,
        url: str,
        purpose: str
    ) -> Dict[str, Any]:
        """
        Navigate with intelligent purpose understanding.
        
        Args:
            url: URL to visit
            purpose: What you want to accomplish
            
        Returns:
            Navigation results with understanding
        """
        # Navigate
        state = await self.browser.navigate(url)
        
        # Understand page in context of purpose
        understanding = await self.browser.understand_page(
            state.screenshot_path,
            state.markdown_content,
            question=purpose
        )
        
        return {
            "url": state.url,
            "title": state.title,
            "understanding": understanding,
            "elements": state.visible_elements
        }
    
    async def smart_click(
        self,
        description: str,
        screenshot_path: str,
        visible_elements: List[Dict[str, Any]]
    ) -> Optional[int]:
        """
        Click element by description instead of index.
        
        Args:
            description: What to click (e.g., "submit button")
            screenshot_path: Current page screenshot
            visible_elements: Available elements
            
        Returns:
            Index of clicked element or None
        """
        index = await self.browser.find_element(
            description,
            screenshot_path,
            visible_elements
        )
        
        if index:
            # In production: call browser_click tool with index
            return index
        
        return None
    
    async def smart_extract(
        self,
        query: str,
        screenshot_path: str,
        markdown_content: str
    ) -> Dict[str, Any]:
        """
        Extract information intelligently.
        
        Args:
            query: What to extract
            screenshot_path: Page screenshot
            markdown_content: Page text
            
        Returns:
            Extracted data
        """
        return await self.browser.extract_information(
            query,
            screenshot_path,
            markdown_content
        )


# Example usage
if __name__ == "__main__":
    async def main():
        # Initialize
        nvidia = NVIDIAKit()
        browser = BrowserControl(nvidia)
        
        # Navigate and understand
        state = await browser.navigate("https://example.com")
        understanding = await browser.understand_page(
            state.screenshot_path,
            state.markdown_content
        )
        print(f"Page understanding: {understanding}")
        
        # Plan interaction
        actions = await browser.plan_interaction(
            goal="Find contact information",
            screenshot_path=state.screenshot_path,
            markdown_content=state.markdown_content,
            visible_elements=state.visible_elements
        )
        print(f"Planned actions: {len(actions)}")
        
        # Autonomous browsing
        results = await browser.autonomous_browse(
            goal="Find company contact email",
            starting_url="https://example.com"
        )
        print(f"Browsing results: {results}")
        
        await nvidia.close()
    
    asyncio.run(main())
