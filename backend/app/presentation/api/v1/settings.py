import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.core.config import settings
from app.domain.ai.model_registry import ModelRegistry
from app.domain.settings.settings_service import SettingsService

from app.domain.ai.local_model_provider import ProviderStatusDTO, ModelCatalogDTO
from app.application.registries.local_provider_registry import LocalModelProviderRegistry
from app.infrastructure.adapters.ollama_provider import OllamaProviderAdapter

router = APIRouter()
model_registry = ModelRegistry()
settings_service = SettingsService()

local_provider_registry = LocalModelProviderRegistry()
local_provider_registry.register(OllamaProviderAdapter())

# In-memory transient API key store (kept out of persistent DB for security)
_transient_api_key: str = ""

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

class ProviderSettingsPatchDTO(BaseModel):
    default_llm: Optional[str] = None
    selected_ollama_model: Optional[str] = None
    default_stt: Optional[str] = None
    gpu_acceleration: Optional[bool] = None
    api_key: Optional[str] = None

def _normalize_provider(raw: str) -> str:
    provider_map = {
        "llama3:8b": "ollama",
        "llama3": "ollama",
        "ollama": "ollama",
        "groq": "groq",
        "openrouter": "openrouter",
    }
    provider = provider_map.get(raw.lower(), raw.lower())
    valid_llms = ["ollama", "groq", "openrouter"]
    if provider not in valid_llms:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid LLM provider '{raw}'. Must be one of {valid_llms}."
        )
    return provider

@router.get("/settings/providers", response_model=ProviderSettingsResponse)
def get_provider_settings():
    db_rec = settings_service.get_settings()
    return ProviderSettingsResponse(
        default_llm=db_rec.default_llm,
        selected_ollama_model=db_rec.selected_ollama_model,
        default_stt=db_rec.default_stt,
        default_embedding=db_rec.default_embedding,
        gpu_acceleration=db_rec.gpu_acceleration,
        api_key=_transient_api_key
    )

@router.put("/settings/providers", response_model=ProviderSettingsResponse)
def update_provider_settings(payload: ProviderSettingsDTO):
    global _transient_api_key
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

    if payload.api_key is not None:
        _transient_api_key = payload.api_key

    db_rec = settings_service.update_settings({
        "default_llm": provider,
        "selected_ollama_model": payload.selected_ollama_model,
        "default_stt": payload.default_stt,
        "gpu_acceleration": payload.gpu_acceleration,
    })

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
        default_llm=db_rec.default_llm,
        selected_ollama_model=db_rec.selected_ollama_model,
        default_stt=db_rec.default_stt,
        default_embedding=db_rec.default_embedding,
        gpu_acceleration=db_rec.gpu_acceleration,
        api_key=_transient_api_key
    )

@router.patch("/settings/providers", response_model=ProviderSettingsResponse)
def patch_provider_settings(payload: ProviderSettingsPatchDTO):
    global _transient_api_key
    updates = payload.model_dump(exclude_unset=True)

    if "api_key" in updates:
        key = updates.pop("api_key")
        _transient_api_key = key
        if key:
            from app.main import openrouter_adapter, groq_adapter
            openrouter_adapter.set_api_key(key)
            groq_adapter.set_api_key(key)

    if "default_llm" in updates:
        updates["default_llm"] = _normalize_provider(updates["default_llm"])

    db_rec = settings_service.update_settings(updates)

    # Sync router policy for provider preference
    from app.main import router_policy
    new_provider = updates.get("default_llm")
    if new_provider is not None:
        router_policy.policy.prefer_local = new_provider == "ollama"

    return ProviderSettingsResponse(
        default_llm=db_rec.default_llm,
        selected_ollama_model=db_rec.selected_ollama_model,
        default_stt=db_rec.default_stt,
        default_embedding=db_rec.default_embedding,
        gpu_acceleration=db_rec.gpu_acceleration,
        api_key=_transient_api_key
    )

# --- Provider Registry Endpoints ---

class LocalProviderItemDTO(BaseModel):
    id: str
    label: str

@router.get("/settings/providers/local", response_model=List[LocalProviderItemDTO])
def list_local_providers():
    providers = local_provider_registry.list_providers()
    return [LocalProviderItemDTO(id=p.provider_id, label=p.label) for p in providers]

@router.get("/settings/providers/local/{provider_id}", response_model=ProviderStatusDTO)
async def get_local_provider_status(provider_id: str):
    provider = local_provider_registry.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Local provider '{provider_id}' not found.")
    return await provider.get_status()

@router.get("/settings/providers/local/{provider_id}/models", response_model=ModelCatalogDTO)
async def get_local_provider_models(provider_id: str):
    provider = local_provider_registry.get_provider(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Local provider '{provider_id}' not found.")
    return await provider.list_models()

# --- Provider & Model Catalog ---

class CatalogModelDTO(BaseModel):
    id: str

class CatalogProviderDTO(BaseModel):
    id: str
    label: str
    models: List[CatalogModelDTO] = []

class CatalogSelectionDTO(BaseModel):
    provider: str
    model: Optional[str] = None

class ProviderCatalogResponse(BaseModel):
    active: CatalogSelectionDTO
    providers: List[CatalogProviderDTO] = []

def _get_live_ollama_models() -> List[CatalogModelDTO]:
    provider = local_provider_registry.get_provider("ollama")
    if not provider:
        return []
    try:
        catalog = asyncio.run(provider.list_models())
        return [CatalogModelDTO(id=m.full_id) for m in catalog.models]
    except Exception:
        return []

def _build_provider_catalog() -> ProviderCatalogResponse:
    db_rec = settings_service.get_settings()
    ollama_models = _get_live_ollama_models()

    if db_rec.ollama_models_dir:
        fs_res = _scan_and_build_response(db_rec.ollama_models_dir)
        existing_ids = {m.id for m in ollama_models}
        for fs_m in fs_res.models:
            if fs_m.full_id not in existing_ids:
                ollama_models.append(CatalogModelDTO(id=fs_m.full_id))
                existing_ids.add(fs_m.full_id)

    providers = [
        CatalogProviderDTO(
            id="ollama",
            label="Ollama (Local)",
            models=ollama_models,
        ),
        CatalogProviderDTO(
            id="groq",
            label="Groq API (Cloud LPU)",
            models=[CatalogModelDTO(id=settings.GROQ_DEFAULT_MODEL)],
        ),
        CatalogProviderDTO(
            id="openrouter",
            label="OpenRouter API (Cloud Universal)",
            models=[CatalogModelDTO(id=settings.OPENROUTER_DEFAULT_MODEL)],
        ),
    ]

    active_provider = (db_rec.default_llm or "ollama").lower()
    active_model: Optional[str] = None
    for p in providers:
        if p.id == active_provider:
            if active_provider == "ollama":
                active_model = db_rec.selected_ollama_model
            elif p.models:
                active_model = p.models[0].id
            break

    return ProviderCatalogResponse(
        active=CatalogSelectionDTO(provider=active_provider, model=active_model),
        providers=providers,
    )

@router.get("/settings/providers/catalog", response_model=ProviderCatalogResponse)
def get_provider_catalog():
    return _build_provider_catalog()

# --- Ollama Local Models Directory Settings ---

from app.services.ollama_scanner import (
    OllamaModelScanner,
    DirectoryNotFoundError,
    InvalidOllamaDirectoryError,
)

ollama_scanner = OllamaModelScanner()

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
    db_rec = settings_service.get_settings()
    return _scan_and_build_response(db_rec.ollama_models_dir)

@router.put("/settings/ollama", response_model=OllamaSettingsResponse)
def update_ollama_directory(payload: UpdateOllamaDirectoryDTO):
    db_rec = settings_service.update_settings({"ollama_models_dir": payload.models_dir})
    res = _scan_and_build_response(db_rec.ollama_models_dir)
    if not res.valid and res.error:
        raise HTTPException(status_code=400, detail=res.error)
    return res

@router.post("/settings/ollama/scan", response_model=OllamaSettingsResponse)
def scan_ollama_models():
    db_rec = settings_service.get_settings()
    if not db_rec.ollama_models_dir:
        raise HTTPException(status_code=400, detail="No Ollama models directory is currently configured.")
    return _scan_and_build_response(db_rec.ollama_models_dir)
