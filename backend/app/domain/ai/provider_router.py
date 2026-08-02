from dataclasses import dataclass
from typing import Optional
from app.domain.ai.model_registry import ModelCapabilityType, ModelMetadata, ModelRegistry

@dataclass
class RoutingPolicy:
    prefer_local: bool = True
    max_allowed_vram_mb: int = 8192
    allow_cloud_fallback: bool = False

class ProviderRouter:
    def __init__(self, registry: ModelRegistry, default_policy: Optional[RoutingPolicy] = None) -> None:
        self.registry = registry
        self.policy = default_policy or RoutingPolicy()

    def select_model(self, capability: ModelCapabilityType, preferred_model_id: Optional[str] = None) -> ModelMetadata:
        if preferred_model_id:
            model = self.registry.get(preferred_model_id)
            if model and capability in model.capabilities:
                return model

        available = self.registry.find_by_capability(capability, local_only=self.policy.prefer_local)
        if available:
            return available[0]

        # Fallback to any model matching capability
        all_models = self.registry.find_by_capability(capability, local_only=False)
        if all_models:
            return all_models[0]

        raise RuntimeError(f"No suitable model registered for capability: {capability}")
