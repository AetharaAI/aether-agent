"""
Base Provider Interface

================================================================================
ARCHITECTURE: Provider Layer - Base Interface
================================================================================

This module defines the abstract interface that all LLM providers must implement.
Provides a common contract for multi-model support.

DESIGN PRINCIPLES:
1. Async-first: All methods are async for non-blocking I/O
2. Streaming support: Both streaming and non-streaming interfaces
3. Type safety: Dataclasses for all request/response objects
4. Error handling: Consistent exception hierarchy

INTEGRATION NOTES:
- Stub implementation - no real API calls yet
- Real providers will inherit from ProviderClient
- Maintain compatibility with existing nvidia_kit.py during transition
================================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, AsyncIterator, Literal
from datetime import datetime


@dataclass
class ProviderConfig:
    """Configuration for LLM provider"""
    api_key: str
    base_url: str
    model: str
    timeout: int = 120
    max_retries: int = 3
    rate_limit_per_minute: int = 60
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    extra_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class Message:
    """Chat message structure"""
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass
class ProviderResponse:
    """Standardized response from any provider"""
    content: str
    model: str
    provider: str
    thinking: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    finish_reason: str = "stop"
    latency_ms: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StreamChunk:
    """Streaming response chunk"""
    content: str
    thinking: Optional[str] = None
    is_finished: bool = False
    finish_reason: Optional[str] = None


class ProviderError(Exception):
    """Base exception for provider errors"""
    pass


class ProviderRateLimitError(ProviderError):
    """Rate limit exceeded"""
    pass


class ProviderAuthError(ProviderError):
    """Authentication failed"""
    pass


class ProviderClient(ABC):
    """
    Abstract base class for LLM providers.
    
    All provider implementations must inherit from this class
    and implement the required methods.
    
    USAGE:
        class MyProvider(ProviderClient):
            async def generate(self, messages, **kwargs):
                # Implementation
                pass
                
            async def stream(self, messages, **kwargs):
                # Implementation
                pass
                
            async def health_check(self):
                # Implementation
                pass
    """
    
    def __init__(self, config: ProviderConfig):
        self.config = config
        self._session: Optional[Any] = None
    
    @abstractmethod
    async def generate(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        thinking: bool = False,
        **kwargs
    ) -> ProviderResponse:
        """
        Generate a completion from the LLM.
        
        Args:
            messages: List of chat messages
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            thinking: Enable chain-of-thought reasoning
            **kwargs: Provider-specific parameters
            
        Returns:
            ProviderResponse with generated content
            
        Raises:
            ProviderError: On API errors
            ProviderRateLimitError: On rate limit
            ProviderAuthError: On auth failures
        """
        pass
    
    @abstractmethod
    async def stream(
        self,
        messages: List[Message],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        thinking: bool = False,
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream completion from the LLM.
        
        Args:
            messages: List of chat messages
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            thinking: Enable chain-of-thought reasoning
            **kwargs: Provider-specific parameters
            
        Yields:
            StreamChunk objects as tokens are generated
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Check provider health and availability.
        
        Returns:
            Dict with health status:
            {
                "healthy": bool,
                "latency_ms": int,
                "model": str,
                "provider": str,
                "error": Optional[str]
            }
        """
        pass
    
    async def close(self):
        """Close any open connections/sessions"""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
