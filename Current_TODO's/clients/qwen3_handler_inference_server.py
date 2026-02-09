"""
Qwen3 Model Client for Persi
Handles communication with Qwen3 models via OpenAI-compatible API.
"""

from typing import Any, Dict, List, Optional, Union
import structlog
import json
from datetime import datetime

logger = structlog.get_logger()


class Qwen3ResponseHandler:
    """
    Handles Qwen3 responses from OpenAI-compatible API.
    """

    def __init__(self):
        self.responses: List[str] = []
        self.tool_uses: List[Dict[str, Any]] = []
        self.final_response: str = ""

    def parse_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse Qwen3 response from OpenAI-compatible API.

        OpenAI API response structure:
        {
            "id": "...",
            "object": "chat.completion",
            "created": timestamp,
            "model": "qwen3_local",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "response text",
                    "tool_calls": [...]
                },
                "finish_reason": "stop"
            }],
            "usage": {...}
        }
        """
        result = {
            "text_response": "",
            "tool_uses": [],
            "has_tool_calls": False,
            "usage": {},
            "raw_response": response
        }

        try:
            # Handle dict response (from direct HTTP client)
            if isinstance(response, dict):
                choices = response.get("choices", [])
                if choices and len(choices) > 0:
                    choice = choices[0]
                    message = choice.get("message", {})

                    # Get text content
                    content = message.get("content", "")
                    if content:
                        result["text_response"] = content

                    # Get tool calls
                    tool_calls = message.get("tool_calls", [])
                    if tool_calls:
                        result["tool_uses"] = self._parse_tool_calls(tool_calls)
                        result["has_tool_calls"] = True

                    # Get usage
                    result["usage"] = response.get("usage", {})

            # Handle object response (from SDK)
            elif hasattr(response, 'choices') and response.choices:
                choice = response.choices[0]
                message = choice.message

                # Get text content
                content = getattr(message, 'content', '')
                if content:
                    result["text_response"] = content

                # Get tool calls
                tool_calls = getattr(message, 'tool_calls', None)
                if tool_calls:
                    result["tool_uses"] = self._parse_tool_calls(tool_calls)
                    result["has_tool_calls"] = True

                # Get usage
                if hasattr(response, 'usage'):
                    result["usage"] = response.usage

            logger.debug("Parsed Qwen3 response", text_length=len(result["text_response"]))

        except Exception as e:
            logger.error("Error parsing Qwen3 response", error=str(e))
            result["text_response"] = f"Error parsing response: {str(e)}"

        return result

    def _parse_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """
        Parse tool calls from the response.

        Args:
            tool_calls: List of tool call objects

        Returns:
            List of parsed tool calls
        """
        parsed_tool_calls = []

        for tool_call in tool_calls:
            try:
                # Handle dict format
                if isinstance(tool_call, dict):
                    parsed_tool_calls.append({
                        "id": tool_call.get("id"),
                        "name": tool_call.get("function", {}).get("name"),
                        "input": json.loads(tool_call.get("function", {}).get("arguments", "{}"))
                    })
                # Handle object format
                elif hasattr(tool_call, 'id'):
                    parsed_tool_calls.append({
                        "id": tool_call.id,
                        "name": tool_call.function.name if hasattr(tool_call, 'function') else None,
                        "input": json.loads(tool_call.function.arguments) if hasattr(tool_call, 'function') else {}
                    })
            except Exception as e:
                logger.error("Error parsing tool call", error=str(e))

        return parsed_tool_calls

    def format_response_for_display(
        self,
        text: str,
        usage: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Format Qwen3 response for display.

        Args:
            text: Text response from the model
            usage: Optional usage statistics

        Returns:
            Formatted response text
        """
        response = text

        # Add usage info if available (for debugging)
        # Note: structlog handles this differently, so we log it separately
        if usage:
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
            logger.debug(
                "Token usage",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )

        return response


def create_openai_messages(
    conversation_history: List[Dict[str, Any]],
    current_message: str,
    tool_results: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Create properly formatted messages for OpenAI-compatible API.

    Args:
        conversation_history: Previous messages
        current_message: Current user message
        tool_results: Optional tool execution results

    Returns:
        Formatted messages list
    """
    messages = []

    # Add conversation history
    for msg in conversation_history:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # Add current message or tool results
    if tool_results:
        # Create tool results message
        content = []
        for result in tool_results:
            if result.get("is_error"):
                content.append({
                    "role": "tool",
                    "tool_call_id": result["id"],
                    "content": f"Error: {result.get('error', 'Unknown error')}"
                })
            else:
                content.append({
                    "role": "tool",
                    "tool_call_id": result["id"],
                    "content": str(result.get("result", "Success"))
                })

        messages.append({
            "role": "user",
            "content": content
        })
    else:
        # Regular user message
        messages.append({
            "role": "user",
            "content": current_message
        })

    return messages


def create_openai_tools(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format tools for OpenAI-compatible API.

    OpenAI expects tools in this format:
    {
        "type": "function",
        "function": {
            "name": "tool_name",
            "description": "...",
            "parameters": {...}
        }
    }

    Args:
        tools: List of tool definitions

    Returns:
        Formatted tools for OpenAI API
    """
    formatted_tools = []

    for tool in tools:
        formatted_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {})
            }
        })

    return formatted_tools
