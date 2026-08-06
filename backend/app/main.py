import os
import sys

# Ensure backend root directory is in sys.path when running script directly
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.infrastructure.db.session import init_db
from app.presentation.api.v1.health import router as health_router
from app.presentation.api.v1.media import router as media_router
from app.presentation.api.v1.chat import router as chat_router
from app.presentation.api.v1.workspaces import router as workspaces_router
from app.presentation.api.v1.graph import router as graph_router
from app.presentation.api.v1.learning import router as learning_router
from app.presentation.api.v1.agents import router as agents_router
from app.presentation.api.v1.settings import router as settings_router
from app.presentation.api.v1.system import router as system_router
import app.presentation.api.v1.chat as chat_module
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.events.event_bus import event_bus
from app.infrastructure.adapters.ollama_adapter import OllamaTextGenAdapter
from app.infrastructure.adapters.cloud_llm_adapter import CloudTextGenAdapter
from app.infrastructure.adapters.whisper_adapter import FasterWhisperSTTAdapter
from app.infrastructure.adapters.sentence_transformers_adapter import SentenceTransformersEmbeddingAdapter
from app.services.workers.transcript_worker import TranscriptWorker
from app.services.workers.embedding_worker import EmbeddingWorker
from app.services.workers.graph_extraction_worker import GraphExtractionWorker
from app.application.services.workspace_intelligence import WorkspaceIntelligenceManager
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever
from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter

# System AI Service Bus singleton
registry = ModelRegistry()
router_policy = ProviderRouter(registry)
ai_service_bus = AIServiceBus(registry, router_policy)

# Instantiated Cloud Adapters
openrouter_adapter = CloudTextGenAdapter("OpenRouter", "https://openrouter.ai/api/v1", settings.OPENROUTER_DEFAULT_MODEL)
groq_adapter = CloudTextGenAdapter("Groq", "https://api.groq.com/openai/v1", settings.GROQ_DEFAULT_MODEL)

# Register Adapters
ai_service_bus.register_text_adapter("ollama", OllamaTextGenAdapter())
ai_service_bus.register_text_adapter("openrouter", openrouter_adapter)
ai_service_bus.register_text_adapter("groq", groq_adapter)
ai_service_bus.register_stt_adapter("faster_whisper", FasterWhisperSTTAdapter())
ai_service_bus.register_embedding_adapter("sentence_transformers", SentenceTransformersEmbeddingAdapter())

# Global references (populated in lifespan)
vector_store = None
intelligence_manager = None

from app.application.events.progress_store import progress_store
from app.bootstrap.event_subscribers import register_media_subscribers
from app.presentation.api.v1.media import media_repository

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Boot sequence: initialize SQLite schema & load models
    init_db()
    
    # Explicitly load persistent settings from SQLite and sync router policy
    from app.domain.settings.settings_service import SettingsService
    settings_rec = SettingsService().get_settings()
    if settings_rec.default_llm and settings_rec.default_llm.lower() == "ollama":
        router_policy.policy.prefer_local = True
    else:
        router_policy.policy.prefer_local = False

    # Register Domain Event subscribers to link EventBus with MediaRepository and ProgressStore
    register_media_subscribers(event_bus, media_repository, progress_store)

    global vector_store, intelligence_manager
    vector_store = EmbeddedQdrantVectorStoreAdapter()
    
    transcript_worker = TranscriptWorker(event_bus, ai_service_bus)
    embedding_worker = EmbeddingWorker(event_bus, ai_service_bus, vector_store=vector_store)
    graph_worker = GraphExtractionWorker(event_bus, ai_service_bus, graph_service=KnowledgeGraphService())

    intelligence_manager = WorkspaceIntelligenceManager(
        ai_service_bus,
        retriever=MultiStageRetriever(ai_service_bus, vector_store=vector_store)
    )
    chat_module.intelligence_manager = intelligence_manager

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
app.include_router(media_router, prefix=settings.API_V1_PREFIX, tags=["Media"])
app.include_router(chat_router, prefix=settings.API_V1_PREFIX, tags=["Chat"])
app.include_router(workspaces_router, prefix=settings.API_V1_PREFIX, tags=["Workspaces"])
app.include_router(graph_router, prefix=settings.API_V1_PREFIX, tags=["Knowledge Graph"])
app.include_router(learning_router, prefix=settings.API_V1_PREFIX, tags=["Learning Tools"])
app.include_router(agents_router, prefix=settings.API_V1_PREFIX, tags=["Agentic AI"])
app.include_router(settings_router, prefix=settings.API_V1_PREFIX, tags=["Settings"])
app.include_router(system_router, prefix=settings.API_V1_PREFIX, tags=["System"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
