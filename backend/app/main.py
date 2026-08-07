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
from app.presentation.api.v1.analytics import router as analytics_router
from app.presentation.api.v1.agents import router as agents_router
from app.presentation.api.v1.settings import router as settings_router
from app.presentation.api.v1.system import router as system_router
import app.presentation.api.v1.chat as chat_module
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.domain.ai.config_resolver import ProviderConfigResolver
from app.domain.ai.provider_registry import LLMProviderRegistry
from app.infrastructure.events.event_bus import event_bus
from app.infrastructure.adapters.ollama_adapter import OllamaTextGenAdapter
from app.infrastructure.adapters.openai_compatible_adapter import OpenAICompatibleProviderAdapter
from app.infrastructure.adapters.anthropic_adapter import AnthropicProviderAdapter
from app.infrastructure.adapters.whisper_adapter import FasterWhisperSTTAdapter
from app.infrastructure.adapters.sentence_transformers_adapter import SentenceTransformersEmbeddingAdapter
from app.services.workers.transcript_worker import TranscriptWorker
from app.services.workers.embedding_worker import EmbeddingWorker
from app.services.workers.graph_extraction_worker import GraphExtractionWorker
from app.application.services.workspace_intelligence import WorkspaceIntelligenceManager
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever
from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter

# Initialize ProviderConfigResolver & LLMProviderRegistry
config_resolver = ProviderConfigResolver()
llm_provider_registry = LLMProviderRegistry(config_resolver=config_resolver)

# Instantiate Core Provider Adapters
ollama_adapter = OllamaTextGenAdapter()
openrouter_adapter = OpenAICompatibleProviderAdapter(
    provider_id="openrouter",
    name="OpenRouter API (Cloud Universal)",
    base_url=settings.OPENROUTER_BASE_URL,
    api_key=settings.OPENROUTER_API_KEY,
    default_model=settings.OPENROUTER_DEFAULT_MODEL
)
groq_adapter = OpenAICompatibleProviderAdapter(
    provider_id="groq",
    name="Groq API (Cloud LPU)",
    base_url=settings.GROQ_BASE_URL,
    api_key=settings.GROQ_API_KEY,
    default_model=settings.GROQ_DEFAULT_MODEL
)
openai_adapter = OpenAICompatibleProviderAdapter(
    provider_id="openai",
    name="OpenAI API",
    base_url=settings.OPENAI_BASE_URL,
    api_key=settings.OPENAI_API_KEY,
    default_model=settings.OPENAI_DEFAULT_MODEL
)
anthropic_adapter = AnthropicProviderAdapter(
    api_key=settings.ANTHROPIC_API_KEY,
    base_url=settings.ANTHROPIC_BASE_URL,
    default_model=settings.ANTHROPIC_DEFAULT_MODEL
)

# Register Adapters in Registry
llm_provider_registry.register(ollama_adapter)
llm_provider_registry.register(openrouter_adapter)
llm_provider_registry.register(groq_adapter)
llm_provider_registry.register(openai_adapter)
llm_provider_registry.register(anthropic_adapter)

# Register custom providers from CUSTOM_LLM_PROVIDERS json string in .env
if getattr(settings, "CUSTOM_LLM_PROVIDERS", None):
    try:
        import json
        custom_list = json.loads(settings.CUSTOM_LLM_PROVIDERS)
        for p in custom_list:
            custom_adapter = OpenAICompatibleProviderAdapter(
                provider_id=p["id"],
                name=p.get("name", p["id"]),
                base_url=p["base_url"],
                api_key=p.get("api_key", ""),
                default_model=p.get("default_model", "default")
            )
            llm_provider_registry.register(custom_adapter)
    except Exception:
        pass

# System AI Service Bus singleton
registry = ModelRegistry()
router_policy = ProviderRouter(registry)
ai_service_bus = AIServiceBus(registry, router_policy, llm_registry=llm_provider_registry)

# Register text & multimodal adapters
ai_service_bus.register_text_adapter("ollama", ollama_adapter)
ai_service_bus.register_text_adapter("openrouter", openrouter_adapter)
ai_service_bus.register_text_adapter("groq", groq_adapter)
ai_service_bus.register_text_adapter("openai", openai_adapter)
ai_service_bus.register_text_adapter("anthropic", anthropic_adapter)
ai_service_bus.register_stt_adapter("faster_whisper", FasterWhisperSTTAdapter())
ai_service_bus.register_embedding_adapter("sentence_transformers", SentenceTransformersEmbeddingAdapter())

# Global references (populated in lifespan)
vector_store = None
intelligence_manager = None
persistent_ingestion_worker = None

from app.application.events.progress_store import progress_store
from app.bootstrap.event_subscribers import register_media_subscribers
from app.presentation.api.v1.media import media_repository

from app.services.workers.learning_evolution_worker import LearningEvolutionWorker
from app.domain.ingestion.persistent_ingestion_queue import PersistentIngestionWorker

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

    global vector_store, intelligence_manager, persistent_ingestion_worker
    vector_store = EmbeddedQdrantVectorStoreAdapter()
    
    transcript_worker = TranscriptWorker(event_bus, ai_service_bus)
    embedding_worker = EmbeddingWorker(event_bus, ai_service_bus, vector_store=vector_store)
    graph_worker = GraphExtractionWorker(event_bus, ai_service_bus, graph_service=KnowledgeGraphService())
    learning_evolution_worker = LearningEvolutionWorker(event_bus)

    persistent_ingestion_worker = PersistentIngestionWorker(event_bus)
    persistent_ingestion_worker.boot_recovery()

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

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(media_router, prefix=settings.API_V1_PREFIX)
app.include_router(chat_router, prefix=settings.API_V1_PREFIX)
app.include_router(workspaces_router, prefix=settings.API_V1_PREFIX)
app.include_router(graph_router, prefix=settings.API_V1_PREFIX)
app.include_router(learning_router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics_router, prefix=settings.API_V1_PREFIX)
app.include_router(agents_router, prefix=settings.API_V1_PREFIX)
app.include_router(settings_router, prefix=settings.API_V1_PREFIX)
app.include_router(system_router, prefix=settings.API_V1_PREFIX)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
