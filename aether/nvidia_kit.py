"""
LLM Provider Wrapper Module

Secure, streaming-capable interface to NVIDIA Research Tier API with:
- OAuth authentication with token refresh
- Streaming response handling
- Rate limiting and retry logic
- Chain-of-thought reasoning support
- Multimodal prompts (text + images)
- Fallback to alternative providers
"""

import os
import asyncio
import base64
import json
import logging
from datetime import datetime

from typing import Optional, Dict, List, Any, AsyncIterator, Literal
from dataclasses import dataclass
from pathlib import Path
import aiohttp
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

logger = logging.getLogger(__name__)


class LLMRequestError(RuntimeError):
    """Raised when upstream LLM endpoint returns a non-success response."""

    def __init__(self, message: str, request_id: Optional[str] = None):
        super().__init__(message)
        self.request_id = request_id

@dataclass
class LLMConfig:
    """Configuration for LLM API (NVIDIA or LiteLLM)"""
    api_key: str
    base_url: str = ""
    model: str = ""
    timeout: int = 120
    max_retries: int = 3
    rate_limit_per_minute: int = 60
    provider: str = "nvidia"  # "nvidia" or "litellm"


@dataclass
class ModelResponse:
    """Structured response from model"""
    content: str
    thinking: Optional[str] = None
    model: str = ""
    usage: Optional[Dict[str, int]] = None
    finish_reason: str = "stop"


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, rate_per_minute: int):
        self.rate = rate_per_minute
        self.tokens = rate_per_minute
        self.last_update = asyncio.get_event_loop().time()
        self.lock = asyncio.Lock()
    
    async def acquire(self):
        """Acquire a token, waiting if necessary"""
        async with self.lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self.last_update
            self.tokens = min(self.rate, self.tokens + elapsed * (self.rate / 60))
            self.last_update = now
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) * (60 / self.rate)
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class NVIDIAKit:
    """
    LLM API wrapper with streaming, rate limiting, and fallback support.
    Supports NVIDIA API and LiteLLM (for self-hosted models).
    
    Patent claim: Novel integration of thinking mode with autonomous
    agent loops for self-review and chain-of-thought reasoning.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        fallback_provider: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize LLM API wrapper.
        
        Args:
            api_key: API key (defaults to $NVIDIA_API_KEY or $LITELLM_API_KEY)
            base_url: API base URL (defaults to NVIDIA or LiteLLM based on env)
            model: Model identifier (defaults to env vars)
            provider: "nvidia" or "litellm" (auto-detected from env if not specified)
            fallback_provider: Optional fallback provider config
        """
        # Auto-detect provider from environment if not specified
        if provider is None:
            if os.getenv("LITELLM_MODEL_BASE_URL") and os.getenv("LITELLM_API_KEY"):
                provider = "litellm"
            else:
                provider = "nvidia"
        
        # Set defaults based on provider
        if provider == "litellm":
            base_url = base_url or os.getenv("LITELLM_MODEL_BASE_URL")
            model = (
                model
                or os.getenv("LITELLM_MODEL_NAME")
                or os.getenv("DEFAULT_MODEL_NAME")
            )
            api_key = api_key or os.getenv("LITELLM_API_KEY", "")
        else:  # nvidia
            base_url = base_url or os.getenv("NVIDIA_BASE_URL")
            model = (
                model
                or os.getenv("NVIDIA_MODEL_NAME")
                or os.getenv("DEFAULT_MODEL_NAME")
            )
            api_key = api_key or os.getenv("NVIDIA_API_KEY", "")

        if not base_url:
            raise ValueError(
                "Base URL required (set LITELLM_MODEL_BASE_URL or NVIDIA_BASE_URL, "
                "or pass base_url=...)"
            )
        if not model:
            raise ValueError(
                "Model required (set LITELLM_MODEL_NAME, NVIDIA_MODEL_NAME, "
                "or DEFAULT_MODEL_NAME, or pass model=...)"
            )
        
        self.config = LLMConfig(
            api_key=api_key,
            base_url=base_url,
            model=model,
            provider=provider
        )
        
        if not self.config.api_key:
            raise ValueError(f"API key required (set ${provider.upper()}_API_KEY or pass api_key)")
        
        self.fallback_provider = fallback_provider
        self.rate_limiter = RateLimiter(self.config.rate_limit_per_minute)
        self.session: Optional[aiohttp.ClientSession] = None
        self._last_request_meta: Dict[str, Any] = {
            "app": "aether-ui",
            "model": self.config.model,
            "model_group": self._infer_model_group(self.config.model),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "spend": 0.0,
            "request_id": "pending",
            "timestamp": datetime.now().isoformat(),
            "headers_sent": self._litellm_headers(),
            "provider": self.config.provider,
            "error": None,
        }
        self._last_payload: Optional[Dict[str, Any]] = None
        
        logger.info(f"Initialized LLMKit with provider: {provider}, model: {model}")

    def _litellm_headers(self) -> Dict[str, str]:
        """Headers used for LiteLLM tracking."""
        if self.config.provider != "litellm":
            return {"Content-Type": "application/json"}
        return {
            "x-litellm-app": "aether-ui",
            "x-litellm-tags": "aether-pro,production",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _infer_model_group(model_name: str) -> str:
        """Infer a lightweight model group label from model id."""
        normalized = (model_name or "").lower()
        if "ocr" in normalized:
            return "ocr_utility"
        if any(tag in normalized for tag in ("vision", "vl", "mm", "omni")):
            return "vision_reasoning"
        return "text_reasoning"

    @staticmethod
    def _extract_usage_numbers(usage: Optional[Dict[str, Any]]) -> Dict[str, float]:
        """Normalize usage payload fields across providers."""
        usage = usage or {}
        prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        completion_tokens = int(
            usage.get("completion_tokens") or usage.get("output_tokens") or 0
        )
        total_tokens = int(
            usage.get("total_tokens")
            or usage.get("total_token_count")
            or (prompt_tokens + completion_tokens)
        )
        spend = float(
            usage.get("total_cost")
            or usage.get("cost")
            or usage.get("spend")
            or 0.0
        )
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "spend": spend,
        }

    def _record_request_meta(
        self,
        *,
        model_name: Optional[str],
        usage: Optional[Dict[str, Any]],
        request_id: Optional[str],
        error: Optional[str] = None,
    ) -> None:
        """Store latest request metadata for debug/context endpoints."""
        model = model_name or self.config.model
        usage_numbers = self._extract_usage_numbers(usage)
        self._last_request_meta = {
            "app": "aether-ui",
            "model": model,
            "model_group": self._infer_model_group(model),
            "prompt_tokens": usage_numbers["prompt_tokens"],
            "completion_tokens": usage_numbers["completion_tokens"],
            "total_tokens": usage_numbers["total_tokens"],
            "spend": usage_numbers["spend"],
            "request_id": request_id or "unknown",
            "timestamp": datetime.now().isoformat(),
            "headers_sent": self._litellm_headers(),
            "provider": self.config.provider,
            "error": error,
        }

    def get_last_request_meta(self) -> Dict[str, Any]:
        """Return latest LiteLLM/NVIDIA request metadata."""
        return dict(self._last_request_meta)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            headers = {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json"
            }
            
            # Add Litellm tracking headers for usage analytics
            if self.config.provider == "litellm":
                headers["x-litellm-app"] = "aether-ui"
                headers["x-litellm-tags"] = "aether-pro,production"
            
            self.session = aiohttp.ClientSession(
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )
        return self.session
    
    async def close(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def _make_request(
        self,
        messages: List[Dict[str, Any]],
        thinking: bool = False,
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> aiohttp.ClientResponse:
        """Make API request with retry logic"""
        await self.rate_limiter.acquire()
        
        session = await self._get_session()
        
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": stream,
            "temperature": temperature
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        # Thinking mode is NVIDIA-specific
        if thinking and self.config.provider == "nvidia":
            payload["chat_template_kwargs"] = {"thinking": True}
        
        url = f"{self.config.base_url}/chat/completions"
        
        response = await session.post(url, json=payload)
        if response.status >= 400:
            request_id = response.headers.get("x-litellm-call-id")
            error_body = await response.text()
            raise LLMRequestError(
                f"LLM request failed ({response.status}): {error_body}",
                request_id=request_id,
            )
        
        return response
    
    async def complete(
        self,
        messages: List[Dict[str, str]],
        thinking: bool = False,
        stream: bool = True,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> ModelResponse:
        """
        Complete a chat conversation.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            thinking: Enable chain-of-thought reasoning mode
            stream: Stream response (currently returns full response)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            
        Returns:
            ModelResponse with content and optional thinking trace
        """
        try:
            response = await self._make_request(
                messages=messages,
                thinking=thinking,
                stream=stream,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if stream:
                return await self._handle_stream_response(response, thinking)
            else:
                data = await response.json()
                parsed = self._parse_response(data, thinking)
                self._record_request_meta(
                    model_name=data.get("model", parsed.model),
                    usage=data.get("usage", parsed.usage),
                    request_id=response.headers.get("x-litellm-call-id"),
                )
                return parsed
        
        except Exception as e:
            request_id = e.request_id if isinstance(e, LLMRequestError) else None
            self._record_request_meta(
                model_name=self.config.model,
                usage=None,
                request_id=request_id,
                error=str(e),
            )
            if self.fallback_provider:
                return await self._fallback_complete(messages, thinking, temperature, max_tokens)
            raise
    
    async def _handle_stream_response(
        self,
        response: aiohttp.ClientResponse,
        thinking: bool
    ) -> ModelResponse:
        """Handle streaming response"""
        content_parts = []
        thinking_parts = []
        usage = None
        finish_reason = "stop"
        
        async for line in response.content:
            line = line.decode('utf-8').strip()
            
            if not line or line == "data: [DONE]":
                continue
            
            if line.startswith("data: "):
                line = line[6:]
            
            try:
                chunk = json.loads(line)
                
                if "choices" in chunk and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0].get("delta", {})
                    
                    if "content" in delta:
                        content_parts.append(delta["content"])
                    
                    if thinking and "thinking" in delta:
                        thinking_parts.append(delta["thinking"])
                    
                    if "finish_reason" in chunk["choices"][0]:
                        finish_reason = chunk["choices"][0]["finish_reason"]
                
                if "usage" in chunk:
                    usage = chunk["usage"]
            
            except json.JSONDecodeError:
                continue

        self._record_request_meta(
            model_name=self.config.model,
            usage=usage,
            request_id=response.headers.get("x-litellm-call-id"),
        )
        
        return ModelResponse(
            content="".join(content_parts),
            thinking="".join(thinking_parts) if thinking_parts else None,
            model=self.config.model,
            usage=usage,
            finish_reason=finish_reason
        )
    
    async def complete_stream(
        self,
        messages: List[Dict[str, str]],
        thinking: bool = False,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> AsyncIterator[str]:
        """
        Stream completion results as they arrive.
        
        Yields:
            Content chunks as they arrive from the API
            
        Note: Final chunk includes usage metadata as JSON when stream completes.
        """
        try:
            response = await self._make_request(
                messages=messages,
                thinking=thinking,
                stream=True,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            usage = None
            model_name = self.config.model
            request_id = response.headers.get("x-litellm-call-id")
            
            async for line in response.content:
                line = line.decode('utf-8').strip()
                
                if not line:
                    continue
                    
                if line == "data: [DONE]":
                    # Stream complete - yield usage metadata
                    self._record_request_meta(
                        model_name=model_name,
                        usage=usage,
                        request_id=request_id,
                    )
                    if usage:
                        usage_payload = json.dumps({
                            'usage': usage,
                            'model': model_name,
                            'provider': self.config.provider,
                            'request_id': request_id,
                        })
                        yield f"__USAGE__:{usage_payload}"
                    continue
                
                if line.startswith("data: "):
                    line = line[6:]
                
                try:
                    chunk = json.loads(line)
                    
                    # Capture usage info from final chunk
                    if "usage" in chunk:
                        usage = chunk["usage"]
                    
                    # Capture model info
                    if "model" in chunk:
                        model_name = chunk["model"]
                    
                    if "choices" in chunk and len(chunk["choices"]) > 0:
                        delta = chunk["choices"][0].get("delta", {})
                        
                        if "content" in delta and delta["content"]:
                            yield delta["content"]
                        
                        if thinking and "thinking" in delta and delta["thinking"]:
                            yield delta["thinking"]
                
                except json.JSONDecodeError:
                    continue
        
        except Exception as e:
            request_id = e.request_id if isinstance(e, LLMRequestError) else None
            self._record_request_meta(
                model_name=self.config.model,
                usage=None,
                request_id=request_id,
                error=str(e),
            )
            logger.error(f"Streaming error: {e}")
            raise
    
    def _parse_response(self, data: Dict[str, Any], thinking: bool) -> ModelResponse:
        """Parse non-streaming response"""
        choice = data["choices"][0]
        message = choice["message"]
        
        return ModelResponse(
            content=message.get("content", ""),
            thinking=message.get("thinking") if thinking else None,
            model=data.get("model", self.config.model),
            usage=data.get("usage"),
            finish_reason=choice.get("finish_reason", "stop")
        )
    
    async def complete_with_vision(
        self,
        messages: List[Dict[str, Any]],
        images: List[str],
        thinking: bool = False,
        temperature: float = 0.7
    ) -> ModelResponse:
        """
        Complete with vision (multimodal) support.
        
        Args:
            messages: List of message dicts
            images: List of image paths or base64 strings
            thinking: Enable chain-of-thought reasoning
            temperature: Sampling temperature
            
        Returns:
            ModelResponse with content and optional thinking
        """
        # Encode images to base64 if they're file paths
        encoded_images = []
        for img in images:
            if os.path.isfile(img):
                with open(img, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode('utf-8')
                    encoded_images.append(f"data:image/jpeg;base64,{img_data}")
            else:
                encoded_images.append(img)
        
        # Add images to the last user message
        if messages and messages[-1]["role"] == "user":
            content = messages[-1]["content"]
            messages[-1]["content"] = [
                {"type": "text", "text": content}
            ] + [
                {"type": "image_url", "image_url": {"url": img}}
                for img in encoded_images
            ]
        
        return await self.complete(
            messages=messages,
            thinking=thinking,
            temperature=temperature
        )
    
    async def complete_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Complete with native function calling.
        
        Args:
            messages: Conversation history
            tools: List of tool schemas (OpenAI format)
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            
        Returns:
            Dict with 'content' and/or 'tool_calls'
        """
        try:
            await self.rate_limiter.acquire()
            session = await self._get_session()
            
            payload = {
                "model": self.config.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "stream": False,
                "temperature": temperature
            }
            
            if max_tokens:
                payload["max_tokens"] = max_tokens

            # DEBUG: Log the full payload for the user to see
            try:
                # Truncate long strings for readability in logs, but keep structure
                debug_payload = json.loads(json.dumps(payload))
                for msg in debug_payload.get("messages", []):
                    if len(msg.get("content", "")) > 500:
                        msg["content"] = msg["content"][:500] + "... [truncated]"
                logger.info(f"LLM REQUEST PAYLOAD:\n{json.dumps(debug_payload, indent=2)}")
                
                # Store full payload for API retrieval
                self._last_payload = payload
            except Exception as e:
                logger.error(f"Failed to log debug payload: {e}")
            
            url = f"{self.config.base_url}/chat/completions"
            
            async with session.post(url, json=payload) as response:
                if response.status >= 400:
                    error_body = await response.text()
                    message = (
                        f"Tool calling error ({response.status}): {error_body}"
                    )
                    self._record_request_meta(
                        model_name=self.config.model,
                        usage=None,
                        request_id=response.headers.get("x-litellm-call-id"),
                        error=message,
                    )
                    raise RuntimeError(message)

                data = await response.json()
                
                choice = data["choices"][0]
                message = choice["message"]
                
                result = {
                    "content": message.get("content", ""),
                    "tool_calls": [],
                    "usage": data.get("usage"),
                    "model": data.get("model", self.config.model),
                    "request_id": response.headers.get("x-litellm-call-id"),
                }
                
                # Parse tool calls
                if "tool_calls" in message:
                    for tc in message["tool_calls"]:
                        if tc["type"] == "function":
                            result["tool_calls"].append({
                                "id": tc["id"],
                                "name": tc["function"]["name"],
                                "arguments": json.loads(tc["function"]["arguments"])
                            })
                
                self._record_request_meta(
                    model_name=result["model"],
                    usage=result["usage"],
                    request_id=result["request_id"],
                )
                return result
                
        except Exception as e:
            if not isinstance(e, RuntimeError):
                self._record_request_meta(
                    model_name=self.config.model,
                    usage=None,
                    request_id=None,
                    error=str(e),
                )
            logger.error(f"Tool calling error: {e}")
            raise
    
    async def _fallback_complete(
        self,
        messages: List[Dict[str, Any]],
        thinking: bool,
        temperature: float,
        max_tokens: Optional[int]
    ) -> ModelResponse:
        """Fallback to alternative provider."""
        if not self.fallback_provider:
            raise ValueError("No fallback provider configured")
        
        # TODO: Implement fallback logic
        return ModelResponse(
            content="[FALLBACK ERROR] Primary provider failed and fallback not implemented",
            model=self.config.model or "unconfigured",
            finish_reason="error"
        )
    
    def set_fallback_provider(self, provider_config: Dict[str, Any]):
        """Set fallback provider configuration"""
        self.fallback_provider = provider_config
    
    async def health_check(self) -> bool:
        """Check if API is accessible"""
        try:
            response = await self.complete(
                messages=[{"role": "user", "content": "test"}],
                stream=False,
                max_tokens=5
            )
            return response.finish_reason in ["stop", "length"]
        except Exception:
            return False


# Convenience functions for common use cases

async def quick_complete(
    prompt: str,
    thinking: bool = False,
    api_key: Optional[str] = None
) -> str:
    """
    Quick completion without managing NVIDIAKit instance.
    
    Args:
        prompt: User prompt
        thinking: Enable chain-of-thought
        api_key: Optional API key
        
    Returns:
        Response content string
    """
    async with NVIDIAKit(api_key=api_key) as kit:
        response = await kit.complete(
            messages=[{"role": "user", "content": prompt}],
            thinking=thinking
        )
        return response.content


async def quick_vision(
    prompt: str,
    images: List[str],
    api_key: Optional[str] = None
) -> str:
    """
    Quick vision completion.
    
    Args:
        prompt: User prompt
        images: List of image paths
        api_key: Optional API key
        
    Returns:
        Response content string
    """
    async with NVIDIAKit(api_key=api_key) as kit:
        response = await kit.complete_with_vision(
            messages=[{"role": "user", "content": prompt}],
            images=images
        )
        return response.content


# Example usage
if __name__ == "__main__":
    async def main():
        # Basic completion
        async with NVIDIAKit() as kit:
            response = await kit.complete(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "What is 2+2?"}
                ]
            )
            print(f"Response: {response.content}")
            
            # With thinking mode
            response_thinking = await kit.complete(
                messages=[
                    {"role": "user", "content": "Solve: If x+5=10, what is x?"}
                ],
                thinking=True
            )
            print(f"\nThinking: {response_thinking.thinking}")
            print(f"Answer: {response_thinking.content}")
    
    asyncio.run(main())
