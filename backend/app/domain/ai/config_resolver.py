from typing import Optional, Dict
from app.core.config import settings

class ProviderConfigResolver:
    """Layered Configuration Resolver separating read-only `.env` secrets from hot-swappable runtime state."""

    def __init__(self, settings_service: Optional[object] = None) -> None:
        self._settings_service = settings_service

    def _get_db_settings(self) -> Optional[object]:
        if self._settings_service is not None:
            return self._settings_service.get_settings()
        try:
            from app.domain.settings.settings_service import SettingsService
            return SettingsService().get_settings()
        except Exception:
            return None

    def get_active_provider_id(self) -> str:
        """Resolve the currently selected active provider ID from SQLite settings, falling back to .env / default."""
        db_rec = self._get_db_settings()
        if db_rec and getattr(db_rec, "default_llm", None):
            return db_rec.default_llm.lower()
        return getattr(settings, "LLM_PROVIDER", "ollama").lower()

    def set_active_provider_id(self, provider_id: str) -> str:
        """Hot-swap the active provider selection in SQLite state without requiring a process restart."""
        pid = provider_id.lower()
        try:
            if self._settings_service is not None:
                self._settings_service.update_settings({"default_llm": pid})
            else:
                from app.domain.settings.settings_service import SettingsService
                SettingsService().update_settings({"default_llm": pid})
        except Exception:
            pass
        return pid

    def get_api_key(self, provider_id: str) -> Optional[str]:
        """Resolve the secret API key for a given provider ID strictly from environment configuration."""
        pid = provider_id.lower()
        env_map: Dict[str, Optional[str]] = {
            "openrouter": getattr(settings, "OPENROUTER_API_KEY", None),
            "groq": getattr(settings, "GROQ_API_KEY", None),
            "openai": getattr(settings, "OPENAI_API_KEY", None),
            "anthropic": getattr(settings, "ANTHROPIC_API_KEY", None),
        }
        return env_map.get(pid)

    def is_configured(self, provider_id: str, is_local: bool = False) -> bool:
        """Determine if a provider has required credentials set in environment configuration."""
        if is_local:
            return True
        key = self.get_api_key(provider_id)
        return bool(key and key.strip())
