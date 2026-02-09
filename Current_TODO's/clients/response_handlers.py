"""
Response handlers for OpenAI-compatible API responses.
"""

from typing import Any, Dict, List, Optional
import structlog
import json

logger = structlog.get_logger()


class OpenAIResponseHandler:
    """Handles standard OpenAI-compatible API responses."""

    def __init__(self):
        pass

    def parse_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse response from OpenAI-compatible API.

        Args:
            response: API response (dict or object)

        Returns:
            Parsed response dict with text_response, tool_uses, has_tool_calls, usage
        """
        result = {
            "text_response": "",
            "tool_uses": [],
            "has_tool_calls": False,
            "usage": {},
            "raw_response": response
        }

        try:
            if isinstance(response, dict):
                choices = response.get("choices", [])
                if choices and len(choices) > 0:
                    choice = choices[0]
                    message = choice.get("message", {})
                    content = message.get("content", "")

                    # Handle string content
                    if isinstance(content, str):
                        result["text_response"] = content
                    # Handle list content (structured)
                    elif isinstance(content, list):
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict):
                                if block.get("type") == "text":
                                    text_parts.append(block.get("text", ""))
                            else:
                                text_parts.append(str(block))
                        result["text_response"] = "".join(text_parts)

                    # Get tool calls
                    tool_calls = message.get("tool_calls", [])
                    if tool_calls:
                        result["tool_uses"] = self._parse_tool_calls(tool_calls)
                        result["has_tool_calls"] = True

                    result["usage"] = response.get("usage", {})

        except Exception as e:
            logger.error("Error parsing response", error=str(e))
            result["text_response"] = f"Error: {str(e)}"

        return result

    def _parse_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """Parse tool calls from response."""
        parsed = []
        for tool_call in tool_calls:
            try:
                if isinstance(tool_call, dict):
                    parsed.append({
                        "id": tool_call.get("id"),
                        "name": tool_call.get("function", {}).get("name"),
                        "input": json.loads(tool_call.get("function", {}).get("arguments", "{}"))
                    })
            except Exception as e:
                logger.error("Error parsing tool call", error=str(e))
        return parsed

    def format_response_for_display(self, text: str, usage: Optional[Dict] = None) -> str:
        """Format response for display."""
        return text
