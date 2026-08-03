from datetime import datetime
from typing import Optional, Dict, Any
from app.infrastructure.db.models import SystemSettings
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session


class SettingsService:
    """Domain service managing persistent system settings via SQLite database."""

    _instance: Optional["SettingsService"] = None

    def __new__(cls) -> "SettingsService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _detach(self, rec: SystemSettings) -> SystemSettings:
        return SystemSettings(
            id=rec.id,
            default_llm=rec.default_llm,
            selected_ollama_model=rec.selected_ollama_model,
            ollama_models_dir=rec.ollama_models_dir,
            default_stt=rec.default_stt,
            default_embedding=rec.default_embedding,
            gpu_acceleration=bool(rec.gpu_acceleration),
            updated_at=rec.updated_at
        )

    def get_settings(self) -> SystemSettings:
        """Fetch persistent settings from SQLite database, initializing defaults if none exist."""
        if not engine or not Session:
            return SystemSettings(id="global")

        try:
            with Session(engine) as session:
                settings_rec = session.get(SystemSettings, "global")
                if not settings_rec:
                    settings_rec = SystemSettings(id="global")
                    session.add(settings_rec)
                    session.commit()
                    session.refresh(settings_rec)
                return self._detach(settings_rec)
        except Exception:
            return SystemSettings(id="global")

    def update_settings(self, updates: Dict[str, Any]) -> SystemSettings:
        """Update system settings fields and commit to SQLite database."""
        if not engine or not Session:
            rec = SystemSettings(id="global")
            for k, v in updates.items():
                if hasattr(rec, k):
                    setattr(rec, k, v)
            return rec

        try:
            with Session(engine) as session:
                rec = session.get(SystemSettings, "global")
                if not rec:
                    rec = SystemSettings(id="global")
                    session.add(rec)

                for key, val in updates.items():
                    if hasattr(rec, key) and key != "id":
                        setattr(rec, key, val)

                rec.updated_at = datetime.utcnow()
                session.add(rec)
                session.commit()
                session.refresh(rec)
                return self._detach(rec)
        except Exception:
            rec = SystemSettings(id="global")
            for k, v in updates.items():
                if hasattr(rec, k):
                    setattr(rec, k, v)
            return rec
