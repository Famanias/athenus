from datetime import datetime
import json
from typing import Optional, Dict, Any
from app.infrastructure.db.models import SystemSettings
from app.infrastructure.db.session import engine
from app.infrastructure.cache.runtime import application_memory_cache

try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session


class SettingsService:
    """Domain service managing persistent system settings via SQLite database."""

    _instance: Optional["SettingsService"] = None
    _cache_key = "settings:global"

    def __new__(cls) -> "SettingsService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def _parse_active_models(raw) -> Dict[str, str]:
        """Decode the per-provider active model map, tolerating dict or JSON-string input."""
        if isinstance(raw, dict):
            return {str(k): str(v) for k, v in raw.items() if v}
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items() if v}
        except Exception:
            pass
        return {}

    def _detach(self, rec: SystemSettings) -> SystemSettings:
        active_models = self._parse_active_models(rec.active_models)
        # Backfill legacy single-column selection into the per-provider map
        if not active_models.get("ollama") and rec.selected_ollama_model:
            active_models["ollama"] = rec.selected_ollama_model
        detached = SystemSettings(
            id=rec.id,
            default_llm=rec.default_llm,
            selected_ollama_model=rec.selected_ollama_model or active_models.get("ollama"),
            ollama_models_dir=rec.ollama_models_dir,
            default_stt=rec.default_stt,
            default_embedding=rec.default_embedding,
            gpu_acceleration=bool(rec.gpu_acceleration),
            updated_at=rec.updated_at
        )
        # Assign the decoded map after construction to avoid pydantic coercion of dict -> str
        detached.active_models = active_models
        return detached

    def get_settings(self) -> SystemSettings:
        """Fetch persistent settings from SQLite database, initializing defaults if none exist."""
        cached = application_memory_cache.get(self._cache_key)
        if isinstance(cached, SystemSettings):
            return cached.model_copy(deep=True) if hasattr(cached, "model_copy") else self._detach(cached)
        if not engine or not Session:
            rec = SystemSettings(id="global")
            rec.active_models = {}
            return rec

        try:
            with Session(engine) as session:
                settings_rec = session.get(SystemSettings, "global")
                if not settings_rec:
                    settings_rec = SystemSettings(id="global")
                    session.add(settings_rec)
                    session.commit()
                    session.refresh(settings_rec)
                detached = self._detach(settings_rec)
                application_memory_cache.set(self._cache_key, detached)
                return detached.model_copy(deep=True) if hasattr(detached, "model_copy") else detached
        except Exception:
            rec = SystemSettings(id="global")
            rec.active_models = {}
            return rec

    def update_settings(self, updates: Dict[str, Any]) -> SystemSettings:
        """Update system settings fields and commit to SQLite database."""
        # Normalize the active_models map so the DB always stores valid JSON
        normalized = dict(updates)
        active_models = self._parse_active_models(self.get_settings().active_models)
        if isinstance(updates.get("active_models"), dict):
            active_models.update(updates["active_models"])
        if "selected_ollama_model" in updates:
            active_models["ollama"] = updates["selected_ollama_model"] or ""
        if active_models:
            active_models = {k: v for k, v in active_models.items() if v}
        normalized["active_models"] = json.dumps(active_models) if active_models else None
        if active_models.get("ollama"):
            normalized["selected_ollama_model"] = active_models["ollama"]

        if not engine or not Session:
            rec = SystemSettings(id="global")
            for k, v in normalized.items():
                if hasattr(rec, k):
                    setattr(rec, k, v)
            return self._detach(rec)

        try:
            with Session(engine) as session:
                rec = session.get(SystemSettings, "global")
                if not rec:
                    rec = SystemSettings(id="global")
                    session.add(rec)

                for key, val in normalized.items():
                    if hasattr(rec, key) and key != "id":
                        setattr(rec, key, val)

                rec.updated_at = datetime.utcnow()
                session.add(rec)
                session.commit()
                session.refresh(rec)
                detached = self._detach(rec)
                application_memory_cache.set(self._cache_key, detached)
                return detached.model_copy(deep=True) if hasattr(detached, "model_copy") else detached
        except Exception:
            rec = SystemSettings(id="global")
            for k, v in normalized.items():
                if hasattr(rec, k):
                    setattr(rec, k, v)
            return self._detach(rec)
