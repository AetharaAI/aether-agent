"""
Aether LLM Provider Layer

================================================================================
ARCHITECTURE: Provider Layer (Aether Core)
================================================================================

This module provides a pluggable provider interface for multi-model support.
Designed for future extensibility without breaking existing functionality.

CURRENT STATUS: Skeleton/Stub Implementation
- Interfaces defined and ready for real API integration
- No active API calls in stub providers
- Default remains local NVIDIA model via nvidia_kit.py

LAYER POSITION:
  Identity Layer -> Memory Layer -> Context Layer -> [PROVIDER LAYER] -> Tool Layer

SUPPORTED PROVIDERS (Stubs):
- NVIDIA (local/primary)
- OpenAI
- Anthropic
- OpenRouter
- Google Gemini

INTEGRATION PLAN:
1. Implement real provider classes with actual API clients
2. Add provider selection logic to AetherCore
3. Maintain backward compatibility with existing nvidia_kit usage
4. Add provider health checks and fallback chains

USAGE:
    from aether.providers import ProviderClient, get_provider
    
    client = get_provider("openai")  # Returns stub until implemented
    response = await client.generate(messages=[...])

================================================================================
"""

__version__ = "0.1.0"

from .base_provider import ProviderClient, ProviderConfig, ProviderResponse

__all__ = [
    "ProviderClient",
    "ProviderConfig", 
    "ProviderResponse",
]


def get_provider(name: str, **kwargs) -> ProviderClient:
    """
    Factory function to get a provider client by name.
    
    Args:
        name: Provider name (openai, nvidia, anthropic, openrouter, gemini)
        **kwargs: Provider-specific configuration
        
    Returns:
        ProviderClient instance
        
    Note:
        Currently returns stub implementations. Real API integration
        will be added in future iterations.
    """
    # Lazy imports to avoid loading unused providers
    if name == "nvidia":
        from .nvidia_provider import NVIDIAProvider
        return NVIDIAProvider(**kwargs)
    elif name == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider(**kwargs)
    elif name == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(**kwargs)
    elif name == "openrouter":
        from .openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(**kwargs)
    elif name == "gemini":
        from .gemini_provider import GeminiProvider
        return GeminiProvider(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {name}. Available: nvidia, openai, anthropic, openrouter, gemini")
