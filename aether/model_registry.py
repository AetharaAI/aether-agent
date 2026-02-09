"""
Model Registry - Dynamic model loading and switching
"""
import os
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ModelConfig:
    id: str
    name: str
    description: str
    provider: str
    model_name: str
    api_base: str
    api_key: str
    supports_vision: bool
    supports_streaming: bool
    max_tokens: int
    temperature: float
    is_default: bool
    tags: List[str]


class ModelRegistry:
    """Registry for managing LLM models dynamically."""
    
    def __init__(self, config_path: str = "config/model-registry.yaml"):
        self.config_path = Path(config_path)
        self.models: Dict[str, ModelConfig] = {}
        self._load_registry()
    
    def _load_registry(self):
        """Load model registry from YAML file."""
        if not self.config_path.exists():
            print(f"Warning: Model registry not found at {self.config_path}")
            self._bootstrap_from_environment()
            return
        
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        for model_data in config.get('models', []):
            # Skip disabled models (commented out in YAML will be None)
            if model_data is None:
                continue
                
            # Resolve environment variables
            api_base = self._resolve_env_vars(model_data.get('api_base', ''))
            api_key = self._resolve_env_vars(model_data.get('api_key', ''))
            
            model = ModelConfig(
                id=model_data['id'],
                name=model_data['name'],
                description=model_data.get('description', ''),
                provider=model_data['provider'],
                model_name=model_data['model_name'],
                api_base=api_base,
                api_key=api_key,
                supports_vision=model_data.get('supports_vision', False),
                supports_streaming=model_data.get('supports_streaming', True),
                max_tokens=model_data.get('max_tokens', 4096),
                temperature=model_data.get('temperature', 0.7),
                is_default=model_data.get('is_default', False),
                tags=model_data.get('tags', [])
            )
            self.models[model.id] = model

        if not self.models:
            self._bootstrap_from_environment()

        print(f"Loaded {len(self.models)} models from registry")

    def _bootstrap_from_environment(self):
        """Bootstrap a single model from environment if registry is empty."""
        model_id = (
            os.getenv("LITELLM_MODEL_NAME")
            or os.getenv("NVIDIA_MODEL_NAME")
            or os.getenv("DEFAULT_MODEL_NAME")
            or ""
        ).strip()
        if not model_id:
            print("Warning: no model configured in environment for ModelRegistry bootstrap")
            return

        is_litellm = bool(os.getenv("LITELLM_MODEL_BASE_URL"))
        provider = "litellm" if is_litellm else "nvidia"
        api_base = (
            os.getenv("LITELLM_MODEL_BASE_URL", "")
            if is_litellm
            else os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        )
        api_key = (
            os.getenv("LITELLM_API_KEY", "")
            if is_litellm
            else os.getenv("NVIDIA_API_KEY", "")
        )
        supports_vision = any(tag in model_id.lower() for tag in ("vision", "vl", "mm", "omni"))

        self.models[model_id] = ModelConfig(
            id=model_id,
            name=model_id,
            description="Environment-provided model configuration",
            provider=provider,
            model_name=model_id,
            api_base=api_base,
            api_key=api_key,
            supports_vision=supports_vision,
            supports_streaming=True,
            max_tokens=4096,
            temperature=0.7,
            is_default=True,
            tags=[],
        )
    
    def _resolve_env_vars(self, value: str) -> str:
        """Replace ${VAR} with environment variable values."""
        if not value:
            return value
        
        import re
        pattern = r'\$\{([^}]+)\}'
        
        def replace_var(match):
            var_name = match.group(1)
            return os.getenv(var_name, '')
        
        return re.sub(pattern, replace_var, value)
    
    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Get a specific model by ID."""
        return self.models.get(model_id)
    
    def get_default_model(self) -> Optional[ModelConfig]:
        """Get the default model."""
        for model in self.models.values():
            if model.is_default:
                return model
        # Return first model if no default set
        return next(iter(self.models.values()), None)
    
    def list_models(self) -> List[Dict[str, Any]]:
        """List all available models (for API/UI)."""
        return [
            {
                'id': m.id,
                'name': m.name,
                'description': m.description,
                'supports_vision': m.supports_vision,
                'supports_streaming': m.supports_streaming,
                'is_default': m.is_default,
                'tags': m.tags
            }
            for m in self.models.values()
        ]
    
    def get_models_by_tag(self, tag: str) -> List[ModelConfig]:
        """Get all models with a specific tag."""
        return [m for m in self.models.values() if tag in m.tags]


# Global registry instance
_registry: Optional[ModelRegistry] = None


def get_registry() -> ModelRegistry:
    """Get or create global model registry."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry
