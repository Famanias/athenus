from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.infrastructure.db.session import init_db
from app.presentation.api.v1.health import router as health_router
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.adapters.ollama_adapter import OllamaTextGenAdapter
from app.infrastructure.adapters.whisper_adapter import FasterWhisperSTTAdapter
from app.infrastructure.adapters.sentence_transformers_adapter import SentenceTransformersEmbeddingAdapter

# System AI Service Bus singleton
registry = ModelRegistry()
router_policy = ProviderRouter(registry)
ai_service_bus = AIServiceBus(registry, router_policy)

# Register Adapters
ai_service_bus.register_text_adapter("ollama", OllamaTextGenAdapter())
ai_service_bus.register_stt_adapter("faster_whisper", FasterWhisperSTTAdapter())
ai_service_bus.register_embedding_adapter("sentence_transformers", SentenceTransformersEmbeddingAdapter())

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Boot sequence: initialize SQLite schema & load models
    init_db()
    yield
    # Shutdown sequence

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan
)

# CORS middleware for local Tauri desktop shell & dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(health_router, prefix=settings.API_V1_PREFIX, tags=["Health"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
