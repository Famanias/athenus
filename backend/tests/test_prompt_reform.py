import asyncio
import pytest
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever
from app.infrastructure.adapters.sentence_transformers_adapter import SentenceTransformersEmbeddingAdapter
from app.application.services.workspace_intelligence import WorkspaceIntelligenceManager
from app.domain.ai.capabilities import ITextGenerationCapability, TextGenerationRequest, TextGenerationResponse


class MockLLMAdapter(ITextGenerationCapability):
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        return TextGenerationResponse(
            text="Python is a high-level programming language.",
            prompt_tokens=30,
            completion_tokens=10
        )

    async def stream(self, request: TextGenerationRequest):
        yield "Python is a high-level programming language."


def test_prompt_reform_and_presentation_order():
    bus = AIServiceBus(ModelRegistry(), ProviderRouter(ModelRegistry()))
    retriever = MultiStageRetriever(bus)

    chunks = [
        {"id": "c1", "source_type": "pdf", "page_number": 1, "text": "Low BM25 high cosine", "bm25_score": 0.1, "score": 0.9},
        {"id": "c2", "source_type": "pdf", "page_number": 2, "text": "High BM25 high priority", "bm25_score": 1.0, "score": 0.8}
    ]

    compressed = retriever._compress_context(chunks)
    # c2 has prompt_priority_score = 1.0*0.7 + 0.8*0.3 = 0.94
    # c1 has prompt_priority_score = 0.1*0.7 + 0.9*0.3 = 0.34
    assert "High BM25 high priority" in compressed.split("\n\n")[0]

    assembled = retriever._assemble_prompt("What is Python?", compressed, triples=[], active_context="")
    assert "If the context contains a direct answer, provide it CONCISELY without additional reasoning." in assembled


class MockVectorStore:
    async def search(self, **kwargs):
        return []


def test_empty_evidence_fallback():
    async def _test():
        registry = ModelRegistry()
        router = ProviderRouter(registry)
        bus = AIServiceBus(registry, router)
        bus.register_text_adapter("ollama", MockLLMAdapter())
        bus.register_embedding_adapter("sentence_transformers", SentenceTransformersEmbeddingAdapter())

        retriever = MultiStageRetriever(bus, vector_store=MockVectorStore())
        manager = WorkspaceIntelligenceManager(bus, retriever=retriever)
        res = await manager.query_workspace("Unrelated query without context", workspace_id="empty_ws")
        assert "answer" in res
        assert res["answer"].startswith("No relevant context found in workspace materials.")

    asyncio.run(_test())
