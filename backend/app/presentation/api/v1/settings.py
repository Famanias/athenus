import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from app.core.config import settings
from app.domain.ai.model_registry import ModelRegistry
from app.domain.settings.settings_service import SettingsService
from app.infrastructure.cache.runtime import application_memory_cache

from app.domain.ai.local_model_provider import ProviderStatusDTO, ModelCatalogDTO
from app.application.registries.local_provider_registry import LocalModelProviderRegistry
from app.infrastructure.adapters.ollama_provider import OllamaProviderAdapter

router = APIRouter()
model_registry = ModelRegistry()
settings_service = SettingsService(cache_store=application_memory_cache)

local_provider_registry = LocalModelProviderRegistry()
local_provider_registry.register(OllamaProviderAdapter())

# In-memory transient API key store (kept out of persistent DB for security)
_transient_api_key: str = ""

class ProviderSettingsDTO(BaseModel):
    default_llm: str
    selected_ollama_model: Optional[str] = None
    selected_model: Optional[str] = None
    active_models: Optional[Dict[str, str]] = None
    default_stt: str
    gpu_acceleration: bool
    api_key: Optional[str] = ""

class ProviderSettingsResponse(BaseModel):
    default_llm: str
    selected_ollama_model: Optional[str] = None
    selected_model: Optional[str] = None
    active_models: Optional[Dict[str, str]] = None
    default_stt: str
    default_embedding: str
    gpu_acceleration: bool
    api_key: Optional[str] = ""
    status: str = "ok"

class ProviderSettingsPatchDTO(BaseModel):
    default_llm: Optional[str] = None
    selected_ollama_model: Optional[str] = None
    selected_model: Optional[str] = None
    active_models: Optional[Dict[str, str]] = None
    default_stt: Optional[str] = None
    gpu_acceleration: Optional[bool] = None
    api_key: Optional[str] = None

def _active_model_for(db_rec, provider_id: str) -> Optional[str]:
    """Resolve the persisted active model for a provider from the per-provider map."""
    models = getattr(db_rec, "active_models", None) or {}
    return models.get(provider_id) or None

def _merge_selected_model(updates: dict, provider_id: str) -> dict:
    """Fold a convenience `selected_model` value into the per-provider active_models map."""
    if "selected_model" not in updates:
        return updates
    merged = dict(updates)
    selected = merged.pop("selected_model")
    active_models = dict(merged.get("active_models") or {})
    if selected:
        active_models[provider_id] = selected
    merged["active_models"] = active_models
    return merged

def _apply_model_to_adapter(adapter, model: Optional[str]) -> None:
    """Hot-swap the in-memory default model on an adapter without a restart."""
    if model and adapter and hasattr(adapter, "set_model"):
        adapter.set_model(model)

def _normalize_provider(raw: str) -> str:
    provider_map = {
        "llama3:8b": "ollama",
        "llama3": "ollama",
        "ollama": "ollama",
        "groq": "groq",
        "openrouter": "openrouter",
        "openai": "openai",
        "anthropic": "anthropic",
    }
    provider = provider_map.get(raw.lower(), raw.lower())
    try:
        from app.main import llm_provider_registry
        if llm_provider_registry and llm_provider_registry.get(provider):
            return provider
    except Exception:
        pass
    valid_llms = ["ollama", "groq", "openrouter", "openai", "anthropic"]
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
        selected_model=_active_model_for(db_rec, db_rec.default_llm),
        active_models=db_rec.active_models or {},
        default_stt=db_rec.default_stt,
        default_embedding=db_rec.default_embedding,
        gpu_acceleration=db_rec.gpu_acceleration,
        api_key=_transient_api_key
    )

@router.put("/settings/providers", response_model=ProviderSettingsResponse)
def update_provider_settings(payload: ProviderSettingsDTO):
    global _transient_api_key
    provider = _normalize_provider(payload.default_llm)

    if payload.api_key is not None:
        _transient_api_key = payload.api_key

    updates = {
        "default_llm": provider,
        "selected_ollama_model": payload.selected_ollama_model,
        "default_stt": payload.default_stt,
        "gpu_acceleration": payload.gpu_acceleration,
    }
    if payload.selected_model or payload.active_models:
        active_models = dict(payload.active_models or {})
        if payload.selected_model:
            active_models[provider] = payload.selected_model
        updates["active_models"] = active_models

    db_rec = settings_service.update_settings(updates)

    # Dynamically update backend config resolver & target adapter
    try:
        from app.main import config_resolver, llm_provider_registry, router_policy
        config_resolver.set_active_provider_id(provider)
        active_adapter = llm_provider_registry.get(provider)
        if active_adapter:
            if payload.api_key and payload.api_key.strip() and hasattr(active_adapter, "set_api_key"):
                active_adapter.set_api_key(payload.api_key.strip())
            _apply_model_to_adapter(active_adapter, _active_model_for(db_rec, provider))
        router_policy.policy.prefer_local = provider == "ollama"
    except Exception:
        pass

    return ProviderSettingsResponse(
        default_llm=db_rec.default_llm,
        selected_ollama_model=db_rec.selected_ollama_model,
        selected_model=_active_model_for(db_rec, db_rec.default_llm),
        active_models=db_rec.active_models or {},
        default_stt=db_rec.default_stt,
        default_embedding=db_rec.default_embedding,
        gpu_acceleration=db_rec.gpu_acceleration,
        api_key=_transient_api_key
    )

@router.patch("/settings/providers", response_model=ProviderSettingsResponse)
def patch_provider_settings(payload: ProviderSettingsPatchDTO):
    global _transient_api_key
    updates = payload.model_dump(exclude_unset=True)

    key_override: Optional[str] = None
    if "api_key" in updates:
        key_override = updates.pop("api_key")
        _transient_api_key = key_override or ""

    if "default_llm" in updates:
        updates["default_llm"] = _normalize_provider(updates["default_llm"])

    # Determine the provider the selected_model applies to (new or current default)
    target_provider = updates.get("default_llm") or settings_service.get_settings().default_llm
    updates = _merge_selected_model(updates, target_provider)

    db_rec = settings_service.update_settings(updates)

    # Sync router policy & config resolver
    try:
        from app.main import config_resolver, llm_provider_registry, router_policy
        new_provider = db_rec.default_llm
        if new_provider is not None:
            config_resolver.set_active_provider_id(new_provider)
            router_policy.policy.prefer_local = new_provider == "ollama"
            active_adapter = llm_provider_registry.get(new_provider)
            if active_adapter:
                if key_override and key_override.strip() and hasattr(active_adapter, "set_api_key"):
                    active_adapter.set_api_key(key_override.strip())
                _apply_model_to_adapter(active_adapter, _active_model_for(db_rec, new_provider))
    except Exception:
        pass

    return ProviderSettingsResponse(
        default_llm=db_rec.default_llm,
        selected_ollama_model=db_rec.selected_ollama_model,
        selected_model=_active_model_for(db_rec, db_rec.default_llm),
        active_models=db_rec.active_models or {},
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
    is_local: bool = False
    is_configured: bool = False
    is_available: bool = False
    active_model: Optional[str] = None
    error: Optional[str] = None
    models: List[CatalogModelDTO] = []

class CatalogSelectionDTO(BaseModel):
    provider: str
    model: Optional[str] = None

class ProviderCatalogResponse(BaseModel):
    active: CatalogSelectionDTO
    providers: List[CatalogProviderDTO] = []

class TestConnectionResponse(BaseModel):
    provider_id: str
    is_available: bool
    is_configured: bool
    active_model: str
    error: Optional[str] = None

@router.post("/settings/providers/{provider_id}/test", response_model=TestConnectionResponse)
async def test_provider_connection(provider_id: str):
    try:
        from app.main import llm_provider_registry
        provider = llm_provider_registry.get(provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' is not registered.")
        health = await provider.check_health()
        return TestConnectionResponse(
            provider_id=health.provider_id,
            is_available=health.is_available,
            is_configured=health.is_configured,
            active_model=health.active_model,
            error=health.error_message
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/settings/providers/catalog", response_model=ProviderCatalogResponse)
async def get_provider_catalog():
    try:
        from app.main import llm_provider_registry, config_resolver
        raw_catalog = await llm_provider_registry.get_catalog()
        db_rec = settings_service.get_settings()
        
        providers = []
        for p in raw_catalog:
            models = [CatalogModelDTO(id=m["id"]) for m in p.get("models", [])]

            providers.append(CatalogProviderDTO(
                id=p["id"],
                label=p["name"],
                is_local=p.get("is_local", False),
                is_configured=p.get("is_configured", False),
                is_available=p.get("is_available", False),
                active_model=p.get("active_model"),
                error=p.get("error"),
                models=models
            ))

        active_provider = config_resolver.get_active_provider_id()
        active_model: Optional[str] = None
        
        for p in providers:
            if p.id == active_provider:
                active_model = _active_model_for(db_rec, active_provider) or p.active_model
                break

        return ProviderCatalogResponse(
            active=CatalogSelectionDTO(provider=active_provider, model=active_model),
            providers=providers,
        )
    except Exception:
        # Fallback catalog build
        db_rec = settings_service.get_settings()
        providers = [
            CatalogProviderDTO(id="ollama", label="Ollama (Local)", models=[]),
            CatalogProviderDTO(id="groq", label="Groq API (Cloud LPU)", models=[CatalogModelDTO(id=settings.GROQ_DEFAULT_MODEL)]),
            CatalogProviderDTO(id="openrouter", label="OpenRouter API (Cloud Universal)", models=[CatalogModelDTO(id=settings.OPENROUTER_DEFAULT_MODEL)]),
        ]
        return ProviderCatalogResponse(
            active=CatalogSelectionDTO(provider=db_rec.default_llm or "ollama", model=None),
            providers=providers,
        )
