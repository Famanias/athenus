import asyncio
import pytest
from app.domain.ai.capabilities import ITextGenerationCapability, IEmbeddingCapability, TextGenerationRequest, TextGenerationResponse
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.domain.knowledge.bm25_retriever import BM25Retriever
from app.domain.knowledge.reranker import CrossEncoderReranker
from app.application.services.workspace_intelligence import WorkspaceIntelligenceManager
from fastapi.testclient import TestClient
from app.main import app
from typing import List

class MockOllamaAdapter(ITextGenerationCapability):
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        return TextGenerationResponse(
            text="Artificial intelligence is transforming education by enabling personalized learning paths [00:00 - 00:10].",
            prompt_tokens=50,
            completion_tokens=20
        )

    async def stream(self, request: TextGenerationRequest):
        yield "Artificial intelligence is transforming education by enabling personalized learning paths [00:00 - 00:10]."

class MockEmbeddingAdapter(IEmbeddingCapability):
    """Deterministic 384-dim mock embedding for CI — avoids HuggingFace download."""
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [[0.01 * (i + 1) for i in range(384)] for _ in texts]

    async def embed_query(self, query: str) -> List[float]:
        return [0.01 * (i + 1) for i in range(384)]

def test_bm25_retriever():
    retriever = BM25Retriever()
    docs = [
        {"id": "d1", "text": "Python is a programming language used in machine learning."},
        {"id": "d2", "text": "Educational video platforms index video transcripts using vector search."},
        {"id": "d3", "text": "Deep learning models require large GPU acceleration."}
    ]
    results = retriever.rank("machine learning Python", docs, top_k=2)
    assert len(results) >= 1
    assert results[0]["id"] == "d1"

def test_cross_encoder_reranker():
    reranker = CrossEncoderReranker()
    candidates = [
        {"id": "c1", "text": "Intro to neural networks and backpropagation", "score": 0.8, "bm25_score": 1.2},
        {"id": "c2", "text": "Cooking recipe for spaghetti carbonara", "score": 0.1, "bm25_score": 0.0}
    ]
    reranked = reranker.rerank("neural networks", candidates, top_k=1)
    assert len(reranked) == 1
    assert reranked[0]["id"] == "c1"

def test_workspace_intelligence_manager():
    async def _test():
        registry = ModelRegistry()
        router = ProviderRouter(registry)
        bus = AIServiceBus(registry, router)
        bus.register_text_adapter("ollama", MockOllamaAdapter())
        bus.register_embedding_adapter("sentence_transformers", MockEmbeddingAdapter())

        manager = WorkspaceIntelligenceManager(bus)
        res = await manager.query_workspace("What is AI?", workspace_id="ws1")
        assert "answer" in res
        assert "Artificial intelligence" in res["answer"]

    asyncio.run(_test())

def _build_mock_intelligence_manager() -> WorkspaceIntelligenceManager:
    """Build a WorkspaceIntelligenceManager wired with mock adapters for endpoint testing."""
    registry = ModelRegistry()
    router = ProviderRouter(registry)
    bus = AIServiceBus(registry, router)
    bus.register_text_adapter("ollama", MockOllamaAdapter())
    bus.register_embedding_adapter("sentence_transformers", MockEmbeddingAdapter())
    return WorkspaceIntelligenceManager(bus)

def test_chat_query_endpoint():
    from app.presentation.api.v1.chat import get_intelligence_manager
    app.dependency_overrides[get_intelligence_manager] = _build_mock_intelligence_manager
    try:
        client = TestClient(app)
        payload = {
            "query": "Explain how RAG retrieval works",
            "workspace_id": "ws_test"
        }
        response = client.post("/api/v1/chat/query", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "citations" in data
    finally:
        app.dependency_overrides.pop(get_intelligence_manager, None)


def test_enforce_token_budget():
    from app.domain.knowledge.chunker import count_tokens
    from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever

    bus = AIServiceBus(ModelRegistry(), ProviderRouter(ModelRegistry()))
    retriever = MultiStageRetriever(bus)

    # Large chunks
    huge_chunk_1 = {"id": "c1", "source_type": "pdf", "page_number": 1, "text": "word " * 1500}
    huge_chunk_2 = {"id": "c2", "source_type": "pdf", "page_number": 2, "text": "word " * 1500}
    huge_chunk_3 = {"id": "c3", "source_type": "pdf", "page_number": 3, "text": "word " * 1500}

    chunks = [huge_chunk_1, huge_chunk_2, huge_chunk_3]
    context_limit = 4000  # Tight test context limit
    reserved_output = 1000

    assembled, final_chunks = retriever.enforce_token_budget(
        query="Explain quantum mechanics",
        chunks=chunks,
        triples=[],
        active_context="",
        model_context_limit=context_limit,
        reserved_output_tokens=reserved_output
    )

    input_tokens = count_tokens(assembled)
    assert input_tokens + reserved_output <= context_limit
    assert len(final_chunks) < len(chunks), "Expected lower scoring chunk to be trimmed"
