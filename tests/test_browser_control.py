"""
Unit tests for browser control module
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from aether.browser_control import BrowserControl, BrowserToolIntegration, BrowserState, BrowserAction
from aether.nvidia_kit import NVIDIAKit, ModelResponse


@pytest.fixture
def mock_nvidia():
    """Mock NVIDIA Kit"""
    nvidia = MagicMock(spec=NVIDIAKit)
    nvidia.complete_with_vision = AsyncMock()
    return nvidia


@pytest.fixture
def browser_control(mock_nvidia):
    """Create BrowserControl instance with mocked NVIDIA"""
    return BrowserControl(mock_nvidia)


@pytest.mark.asyncio
async def test_navigate(browser_control):
    """Test navigation"""
    state = await browser_control.navigate("https://example.com")
    
    assert isinstance(state, BrowserState)
    assert state.url == "https://example.com"
    assert browser_control.current_state == state
    assert len(browser_control.history) == 1


@pytest.mark.asyncio
async def test_understand_page(browser_control, mock_nvidia):
    """Test page understanding with vision"""
    mock_nvidia.complete_with_vision.return_value = ModelResponse(
        content="This page is about example content with a contact form.",
        thinking="Analyzing the page structure..."
    )
    
    understanding = await browser_control.understand_page(
        screenshot_path="/tmp/test.png",
        markdown_content="# Example Page\n\nContact us here.",
        question="What is this page about?"
    )
    
    assert "example content" in understanding.lower()
    mock_nvidia.complete_with_vision.assert_called_once()


@pytest.mark.asyncio
async def test_find_element(browser_control, mock_nvidia):
    """Test finding element by description"""
    mock_nvidia.complete_with_vision.return_value = ModelResponse(
        content="1"
    )
    
    elements = [
        {"index": 1, "tag": "button", "text": "Submit"},
        {"index": 2, "tag": "input", "text": "Search"},
    ]
    
    index = await browser_control.find_element(
        description="submit button",
        screenshot_path="/tmp/test.png",
        visible_elements=elements
    )
    
    assert index == 1


@pytest.mark.asyncio
async def test_plan_interaction(browser_control, mock_nvidia):
    """Test interaction planning"""
    mock_nvidia.complete_with_vision.return_value = ModelResponse(
        content='''[
            {"action_type": "input", "params": {"index": 2, "text": "test"}, "reasoning": "Fill form"},
            {"action_type": "click", "params": {"index": 1}, "reasoning": "Submit"}
        ]''',
        thinking="Planning the interaction steps..."
    )
    
    actions = await browser_control.plan_interaction(
        goal="Fill and submit form",
        screenshot_path="/tmp/test.png",
        markdown_content="Form content",
        visible_elements=[
            {"index": 1, "tag": "button", "text": "Submit"},
            {"index": 2, "tag": "input", "text": "Name"},
        ]
    )
    
    assert len(actions) == 2
    assert isinstance(actions[0], BrowserAction)
    assert actions[0].action_type == "input"
    assert actions[1].action_type == "click"


@pytest.mark.asyncio
async def test_extract_information(browser_control, mock_nvidia):
    """Test information extraction"""
    mock_nvidia.complete_with_vision.return_value = ModelResponse(
        content='{"email": "contact@example.com", "phone": "555-1234"}'
    )
    
    info = await browser_control.extract_information(
        query="Find contact information",
        screenshot_path="/tmp/test.png",
        markdown_content="Contact: contact@example.com, Phone: 555-1234"
    )
    
    assert "email" in info
    assert info["email"] == "contact@example.com"


@pytest.mark.asyncio
async def test_verify_action_result(browser_control, mock_nvidia):
    """Test action verification"""
    mock_nvidia.complete_with_vision.return_value = ModelResponse(
        content="SUCCESS: Form was submitted successfully"
    )
    
    action = BrowserAction(
        action_type="click",
        params={"index": 1},
        reasoning="Submit form"
    )
    
    success, explanation = await browser_control.verify_action_result(
        action,
        before_screenshot="/tmp/before.png",
        after_screenshot="/tmp/after.png"
    )
    
    assert success is True
    assert "SUCCESS" in explanation


@pytest.mark.asyncio
async def test_browser_tool_integration(mock_nvidia):
    """Test browser tool integration"""
    browser = BrowserControl(mock_nvidia)
    tools = BrowserToolIntegration(browser)
    
    mock_nvidia.complete_with_vision.return_value = ModelResponse(
        content="This is an example website homepage."
    )
    
    result = await tools.smart_navigate(
        url="https://example.com",
        purpose="Find contact information"
    )
    
    assert "url" in result
    assert "understanding" in result
    assert result["url"] == "https://example.com"


@pytest.mark.asyncio
async def test_autonomous_browse(browser_control, mock_nvidia):
    """Test autonomous browsing"""
    mock_nvidia.complete_with_vision.side_effect = [
        ModelResponse(content="This is the homepage. Click 'Contact' to find contact info."),
        ModelResponse(content='[{"action_type": "click", "params": {"index": 1}, "reasoning": "Go to contact page"}]'),
    ]
    
    results = await browser_control.autonomous_browse(
        goal="Find contact information",
        starting_url="https://example.com",
        max_steps=2
    )
    
    assert results["goal"] == "Find contact information"
    assert results["starting_url"] == "https://example.com"
    assert len(results["steps"]) > 0
