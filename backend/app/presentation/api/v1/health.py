from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict
from app.core.config import settings
from app.domain.ai.model_registry import ModelRegistry, ModelCapabilityType

router = APIRouter()

class HealthCheckResponse(BaseModel):
    status: str
    version: str
    environment: str

class ProviderHealthResponse(BaseModel):
    available_capabilities: Dict[str, int]
    default_llm: str
    default_stt: str
    default_embedding: str

@router.get("/health", response_model=HealthCheckResponse)
def health_check():
    return HealthCheckResponse(
        status="ok",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT
    )

@router.get("/health/providers", response_model=ProviderHealthResponse)
def provider_health():
    registry = ModelRegistry()
    return ProviderHealthResponse(
        available_capabilities={
            "text_generation": len(registry.find_by_capability(ModelCapabilityType.TEXT_GENERATION)),
            "speech_to_text": len(registry.find_by_capability(ModelCapabilityType.SPEECH_TO_TEXT)),
            "embeddings": len(registry.find_by_capability(ModelCapabilityType.EMBEDDINGS)),
        },
        default_llm=settings.DEFAULT_LLM_MODEL,
        default_stt=settings.DEFAULT_STT_PROVIDER,
        default_embedding=settings.EMBEDDING_MODEL_NAME
    )
