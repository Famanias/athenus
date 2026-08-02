from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings
from app.domain.ai.model_registry import ModelRegistry

router = APIRouter()
model_registry = ModelRegistry()

# In-memory settings state
current_settings = {
    "default_llm": settings.DEFAULT_LLM_MODEL,
    "default_stt": settings.DEFAULT_STT_PROVIDER,
    "default_embedding": settings.EMBEDDING_MODEL_NAME,
    "gpu_acceleration": True,
    "api_key": ""
}

class ProviderSettingsDTO(BaseModel):
    default_llm: str
    default_stt: str
    gpu_acceleration: bool
    api_key: Optional[str] = ""

class ProviderSettingsResponse(BaseModel):
    default_llm: str
    default_stt: str
    default_embedding: str
    gpu_acceleration: bool
    api_key: Optional[str] = ""
    status: str = "ok"

@router.get("/settings/providers", response_model=ProviderSettingsResponse)
def get_provider_settings():
    return ProviderSettingsResponse(
        default_llm=current_settings["default_llm"],
        default_stt=current_settings["default_stt"],
        default_embedding=current_settings["default_embedding"],
        gpu_acceleration=current_settings["gpu_acceleration"],
        api_key=current_settings.get("api_key", "")
    )

@router.put("/settings/providers", response_model=ProviderSettingsResponse)
def update_provider_settings(payload: ProviderSettingsDTO):
    valid_llms = ["ollama", "groq", "openrouter"]
    if payload.default_llm.lower() not in valid_llms:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid LLM provider '{payload.default_llm}'. Must be one of {valid_llms}."
        )

    current_settings["default_llm"] = payload.default_llm
    current_settings["default_stt"] = payload.default_stt
    current_settings["gpu_acceleration"] = payload.gpu_acceleration
    current_settings["api_key"] = payload.api_key or ""

    # Dynamically update backend adapters
    from app.main import openrouter_adapter, groq_adapter, router_policy
    if payload.api_key:
        openrouter_adapter.set_api_key(payload.api_key)
        groq_adapter.set_api_key(payload.api_key)

    # Set router policy preferred model or local fallback
    if payload.default_llm.lower() == "ollama":
        router_policy.policy.prefer_local = True
    else:
        router_policy.policy.prefer_local = False

    return ProviderSettingsResponse(
        default_llm=current_settings["default_llm"],
        default_stt=current_settings["default_stt"],
        default_embedding=current_settings["default_embedding"],
        gpu_acceleration=current_settings["gpu_acceleration"],
        api_key=current_settings["api_key"]
    )
