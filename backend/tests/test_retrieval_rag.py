import asyncio
import pytest
from app.domain.ai.capabilities import ITextGenerationCapability, TextGenerationRequest, TextGenerationResponse
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.domain.knowledge.bm25_retriever import BM25Retriever
from app.domain.knowledge.reranker import CrossEncoderReranker
from app.infrastructure.adapters.sentence_transformers_adapter import SentenceTransformersEmbeddingAdapter
from app.application.services.workspace_intelligence import WorkspaceIntelligenceManager
from fastapi.testclient import TestClient
from app.main import app

class MockOllamaAdapter(ITextGenerationCapability):
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        return TextGenerationResponse(
            text="Artificial intelligence is transforming education by enabling personalized learning paths [00:00 - 00:10].",
            prompt_tokens=50,
            completion_tokens=20
        )

    async def stream(self, request: TextGenerationRequest):
        yield "Artificial intelligence is transforming education by enabling personalized learning paths [00:00 - 00:10]."

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
        bus.register_embedding_adapter("sentence_transformers", SentenceTransformersEmbeddingAdapter())

        manager = WorkspaceIntelligenceManager(bus)
        res = await manager.query_workspace("What is AI?", workspace_id="ws1")
        assert "answer" in res
        assert "Artificial intelligence" in res["answer"]

    asyncio.run(_test())

def test_chat_query_endpoint():
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
