from typing import Optional
from app.infrastructure.adapters.openai_compatible_adapter import OpenAICompatibleProviderAdapter

class CloudTextGenAdapter(OpenAICompatibleProviderAdapter):
    """Backwards-compatible alias for CloudTextGenAdapter wrapping OpenAICompatibleProviderAdapter."""

    def __init__(
        self,
        provider_name: str,
        base_url: str,
        default_model: str,
        api_key: Optional[str] = None
    ) -> None:
        super().__init__(
            provider_id=provider_name.lower(),
            name=provider_name,
            base_url=base_url,
            api_key=api_key or "",
            default_model=default_model,
            is_local=False
        )
