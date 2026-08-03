from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.core.config import settings
from app.domain.ai.model_registry import ModelRegistry

router = APIRouter()
model_registry = ModelRegistry()

# In-memory settings state
current_settings = {
    "default_llm": settings.DEFAULT_LLM_PROVIDER,
    "selected_ollama_model": None,
    "default_stt": settings.DEFAULT_STT_PROVIDER,
    "default_embedding": settings.EMBEDDING_MODEL_NAME,
    "gpu_acceleration": True,
    "api_key": ""
}

class ProviderSettingsDTO(BaseModel):
    default_llm: str
    selected_ollama_model: Optional[str] = None
    default_stt: str
    gpu_acceleration: bool
    api_key: Optional[str] = ""

class ProviderSettingsResponse(BaseModel):
    default_llm: str
    selected_ollama_model: Optional[str] = None
    default_stt: str
    default_embedding: str
    gpu_acceleration: bool
    api_key: Optional[str] = ""
    status: str = "ok"

@router.get("/settings/providers", response_model=ProviderSettingsResponse)
def get_provider_settings():
    return ProviderSettingsResponse(
        default_llm=current_settings["default_llm"],
        selected_ollama_model=current_settings.get("selected_ollama_model"),
        default_stt=current_settings["default_stt"],
        default_embedding=current_settings["default_embedding"],
        gpu_acceleration=current_settings["gpu_acceleration"],
        api_key=current_settings.get("api_key", "")
    )

@router.put("/settings/providers", response_model=ProviderSettingsResponse)
def update_provider_settings(payload: ProviderSettingsDTO):
    llm_raw = payload.default_llm.lower()
    provider_map = {
        "llama3:8b": "ollama",
        "llama3": "ollama",
        "ollama": "ollama",
        "groq": "groq",
        "openrouter": "openrouter",
    }
    provider = provider_map.get(llm_raw, llm_raw)
    valid_llms = ["ollama", "groq", "openrouter"]
    if provider not in valid_llms:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid LLM provider '{payload.default_llm}'. Must be one of {valid_llms}."
        )

    current_settings["default_llm"] = provider
    current_settings["selected_ollama_model"] = payload.selected_ollama_model
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
        selected_ollama_model=current_settings["selected_ollama_model"],
        default_stt=current_settings["default_stt"],
        default_embedding=current_settings["default_embedding"],
        gpu_acceleration=current_settings["gpu_acceleration"],
        api_key=current_settings["api_key"]
    )

# --- Ollama Local Models Directory Settings ---

from typing import List
from app.services.ollama_scanner import (
    OllamaModelScanner,
    DirectoryNotFoundError,
    InvalidOllamaDirectoryError,
)

ollama_scanner = OllamaModelScanner()
current_settings["ollama_models_dir"] = None

class DiscoveredModelDTO(BaseModel):
    full_id: str
    model_name: str
    tag: str
    provider: str = "ollama"
    size_bytes: Optional[int] = None

class UpdateOllamaDirectoryDTO(BaseModel):
    models_dir: str

class OllamaSettingsResponse(BaseModel):
    configured_dir: Optional[str] = None
    resolved_dir: Optional[str] = None
    valid: bool = False
    models_count: int = 0
    models: List[DiscoveredModelDTO] = []
    error: Optional[str] = None

def _scan_and_build_response(models_dir: Optional[str]) -> OllamaSettingsResponse:
    if not models_dir:
        return OllamaSettingsResponse(
            configured_dir=None,
            resolved_dir=None,
            valid=False,
            models_count=0,
            models=[],
            error=None
        )

    try:
        config_dir, res_dir, models = ollama_scanner.scan(models_dir)
        dto_models = [
            DiscoveredModelDTO(
                full_id=m.full_id,
                model_name=m.model_name,
                tag=m.tag,
                provider=m.provider,
                size_bytes=m.size_bytes
            )
            for m in models
        ]
        return OllamaSettingsResponse(
            configured_dir=config_dir,
            resolved_dir=res_dir,
            valid=True,
            models_count=len(dto_models),
            models=dto_models,
            error=None
        )
    except DirectoryNotFoundError as e:
        return OllamaSettingsResponse(
            configured_dir=models_dir,
            resolved_dir=None,
            valid=False,
            models_count=0,
            models=[],
            error=str(e)
        )
    except InvalidOllamaDirectoryError as e:
        return OllamaSettingsResponse(
            configured_dir=models_dir,
            resolved_dir=None,
            valid=False,
            models_count=0,
            models=[],
            error=str(e)
        )
    except Exception as e:
        return OllamaSettingsResponse(
            configured_dir=models_dir,
            resolved_dir=None,
            valid=False,
            models_count=0,
            models=[],
            error=f"Scanning failed: {str(e)}"
        )

@router.get("/settings/ollama", response_model=OllamaSettingsResponse)
def get_ollama_settings():
    return _scan_and_build_response(current_settings.get("ollama_models_dir"))

@router.put("/settings/ollama", response_model=OllamaSettingsResponse)
def update_ollama_directory(payload: UpdateOllamaDirectoryDTO):
    current_settings["ollama_models_dir"] = payload.models_dir
    res = _scan_and_build_response(payload.models_dir)
    if not res.valid and res.error:
        raise HTTPException(status_code=400, detail=res.error)
    return res

@router.post("/settings/ollama/scan", response_model=OllamaSettingsResponse)
def scan_ollama_models():
    configured = current_settings.get("ollama_models_dir")
    if not configured:
        raise HTTPException(status_code=400, detail="No Ollama models directory is currently configured.")
    res = _scan_and_build_response(configured)
    if not res.valid and res.error:
        raise HTTPException(status_code=400, detail=res.error)
    return res

