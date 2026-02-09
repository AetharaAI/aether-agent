"""
OpenAI-Compatible Client for Persi AI
Unified client for LiteLLM and OpenRouter providers.

Uses OpenAI-compatible semantics:
- Always POST /v1/chat/completions
- OpenAI-compatible request/response schema
- No GET requests for inference
"""

import json
from typing import Any, Dict, List, Optional
import structlog
import aiohttp

logger = structlog.get_logger()


class OpenAICompatibleResponseHandler:
    """Handles responses from OpenAI-compatible APIs (LiteLLM, OpenRouter)."""

    def __init__(self):
        pass

    def parse_response(self, response: Any) -> Dict[str, Any]:
        """
        Parse response from OpenAI-compatible API.

        Response structure:
        {
            "id": "...",
            "object": "chat.completion",
            "created": timestamp,
            "model": "...",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "response text" or [...],
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
                    content = message.get("content", "")

                    # Handle content as string
                    if isinstance(content, str):
                        result["text_response"] = content
                    # Handle content as list (structured content)
                    elif isinstance(content, list):
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict):
                                block_type = block.get("type")
                                if block_type == "text":
                                    text_parts.append(block.get("text", ""))
                                elif block_type == "thinking":
                                    # Store thinking blocks for later use
                                    if "thinking" not in result:
                                        result["thinking"] = []
                                    result["thinking"].append(block.get("thinking", ""))
                            else:
                                text_parts.append(str(block))
                        result["text_response"] = "".join(text_parts)

                    # Get tool calls
                    tool_calls = message.get("tool_calls", [])
                    if tool_calls:
                        result["tool_uses"] = self._parse_tool_calls(tool_calls)
                        result["has_tool_calls"] = True

                    # Get usage
                    result["usage"] = response.get("usage", {})

            logger.debug("Parsed OpenAI-compatible response", text_length=len(result["text_response"]))

        except Exception as e:
            logger.error("Error parsing response", error=str(e))
            result["text_response"] = f"Error parsing response: {str(e)}"

        return result

    def _parse_tool_calls(self, tool_calls: List[Any]) -> List[Dict[str, Any]]:
        """Parse tool calls from the response."""
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
            except Exception as e:
                logger.error("Error parsing tool call", error=str(e))

        return parsed_tool_calls

    def format_response_for_display(
        self,
        text: str,
        usage: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format response for display."""
        return text


class OpenAICompatibleClient:
    """
    Unified OpenAI-compatible client for LiteLLM and OpenRouter.

    Provider semantics:
    - HTTP method: POST
    - Endpoint: /v1/chat/completions
    - Auth: Bearer token
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model_name: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7
    ):
        """
        Initialize OpenAI-compatible client.

        Args:
            api_key: API authentication key
            base_url: Base URL for the API (without /v1 prefix)
            model_name: Opaque model name (e.g., "gpt-4", "claude-3-opus")
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
        """
        self.api_key = api_key
        # Normalize base URL - remove trailing slashes and /v1 suffix
        self.base_url = base_url.rstrip("/").rstrip("/v1").rstrip("/")
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.session: Optional[aiohttp.ClientSession] = None

        logger.info(
            "Initialized OpenAI-compatible client",
            model=model_name,
            base_url=self.base_url,
            max_tokens=max_tokens,
            temperature=temperature
        )

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def _post_with_redirect(
        self,
        url: str,
        headers: Dict[str, str],
        payload: Dict[str, Any]
    ) -> aiohttp.ClientResponse:
        """Send POST request and manually handle redirects to preserve method."""
        if not self.session:
            raise RuntimeError("Client must be used as async context manager")

        response = await self.session.post(
            url,
            headers=headers,
            json=payload,
            allow_redirects=False
        )

        if response.status in {301, 302, 307, 308}:
            redirect_url = response.headers.get("Location")
            await response.release()
            if redirect_url:
                logger.warning(
                    "Received redirect, retrying POST",
                    from_url=url,
                    to_url=redirect_url,
                    status=response.status
                )
                response = await self.session.post(
                    redirect_url,
                    headers=headers,
                    json=payload,
                    allow_redirects=False
                )

        return response

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a chat completion using OpenAI-compatible API.

        Always uses POST /v1/chat/completions regardless of provider.

        Args:
            messages: List of message dicts with role and content
            tools: Optional list of tools for function calling
            **kwargs: Additional arguments to pass to the API

        Returns:
            API response as dict
        """
        if not self.session:
            raise RuntimeError("Client must be used as async context manager")

        url = f"{self.base_url}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature)
        }

        # Add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        logger.debug("Sending chat completion request", url=url, model=self.model_name)

        try:
            response = await self._post_with_redirect(url, headers, payload)
            async with response:
                if response.status == 200:
                    result = await response.json()
                    logger.debug("Received chat completion response", tokens_used=result.get("usage", {}))
                    return result
                else:
                    error_text = await response.text()
                    logger.error(
                        "Chat completion failed",
                        status=response.status,
                        error=error_text
                    )
                    raise Exception(f"API request failed with status {response.status}: {error_text}")

        except Exception as e:
            logger.error("Chat completion error", error=str(e))
            raise

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models."""
        if not self.session:
            raise RuntimeError("Client must be used as async context manager")

        url = f"{self.base_url}/v1/models"

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        logger.debug("Listing models", url=url)

        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("data", [])
                else:
                    error_text = await response.text()
                    logger.error(
                        "List models failed",
                        status=response.status,
                        error=error_text
                    )
                    raise Exception(f"API request failed with status {response.status}: {error_text}")

        except Exception as e:
            logger.error("List models error", error=str(e))
            raise

    async def health_check(self) -> bool:
        """Check if the API is healthy."""
        if not self.session:
            raise RuntimeError("Client must be used as async context manager")

        # Use chat completions endpoint for health check
        url = f"{self.base_url}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": "health check"}],
            "max_tokens": 1
        }

        logger.debug("Health check", url=url)

        try:
            response = await self._post_with_redirect(url, headers, payload)
            async with response:
                healthy = response.status == 200
                if healthy:
                    logger.info("Health check passed")
                else:
                    logger.warning("Health check failed", status=response.status)
                return healthy

        except Exception as e:
            logger.error("Health check error", error=str(e))
            return False


async def create_openai_compatible_client(
    api_key: str,
    base_url: str,
    model_name: str = "",
    **kwargs
) -> OpenAICompatibleClient:
    """
    Create and initialize an OpenAI-compatible client.

    Args:
        api_key: API authentication key
        base_url: Base URL for the API
        model_name: Model name to use
        **kwargs: Additional arguments

    Returns:
        Initialized OpenAICompatibleClient
    """
    client = OpenAICompatibleClient(
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
        **kwargs
    )

    # Test the connection
    async with client:
        healthy = await client.health_check()
        if not healthy:
            raise Exception("Failed to connect to OpenAI-compatible API")

    return client
