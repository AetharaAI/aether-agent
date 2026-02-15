import os
import yaml
from typing import Dict, Any, Optional

class ProviderRouter:
    """
    Manages LLM provider configuration and routing.
    Allows dynamic switching between providers defined in config/provider-registry.yaml.
    """

    def __init__(self, config_path: str = "config/provider-registry.yaml"):
        self.config_path = config_path
        self.config = {}
        self.current_provider_name = "litellm"  # Default fallback
        self.selected_model = None  # User-selected model (overrides provider default)
        self.load_config()

    def load_config(self):
        """Load provider configuration from YAML file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Provider registry not found at {self.config_path}")
        
        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)
        
        # Set initial provider from config default
        self.current_provider_name = self.config.get("default_provider", "litellm")

    def get_providers(self) -> Dict[str, Any]:
        """Return all available providers."""
        return self.config.get("providers", {})

    def set_provider(self, provider_name: str):
        """Set the active provider."""
        providers = self.get_providers()
        if provider_name not in providers:
            raise ValueError(f"Provider '{provider_name}' not found in registry.")

        self.current_provider_name = provider_name
        self.selected_model = None  # Reset selected model when provider changes

    def set_model(self, model_name: str):
        """Set the user-selected model (overrides provider default)."""
        self.selected_model = model_name

    def get_current_provider_config(self) -> Dict[str, Any]:
        """Get configuration for the currently active provider."""
        providers = self.get_providers()
        config = providers.get(self.current_provider_name)
        
        if not config:
             # Fallback if somehow invalid state
             return {}

        # Resolve API key from environment
        key_env = config.get("key_env")
        api_key = os.getenv(key_env) if key_env else None
        
        # Resolve model from environment or config
        model_env = config.get("model_env")
        default_model = os.getenv(model_env) if model_env else config.get("default_model")
        
        return {
            "type": config.get("type"),
            "base_url": config.get("base_url"),
            "api_key": api_key,
            "models_endpoint": config.get("models_endpoint"),
            "default_model": default_model,
            "name": self.current_provider_name,
            "tool_format": config.get("tool_format", "openai"),
        }

    def get_llm_config(self) -> Dict[str, Any]:
        """
        Returns a standardized config dictionary for LLM initialization.
        Compatible with LiteLLM/OpenAI clients.
        """
        provider_config = self.get_current_provider_config()

        # Priority: user-selected model > provider default > env var fallback
        model = self.selected_model or provider_config.get("default_model")
        if not model:
             # Generically fallback if nothing specific found
             model = os.getenv("LITELLM_MODEL_NAME", "gpt-3.5-turbo")

        return {
            "api_key": provider_config.get("api_key"),
            "base_url": provider_config.get("base_url"),
            "custom_llm_provider": "openai",  # Most are openai-compatible
            "default_model": model,
            "tool_format": provider_config.get("tool_format", "openai"),
        }
