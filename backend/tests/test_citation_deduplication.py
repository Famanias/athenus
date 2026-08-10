import asyncio
import pytest
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever, RetrievalContext
from app.application.services.workspace_intelligence import WorkspaceIntelligenceManager
from app.domain.ai.capabilities import ITextGenerationCapability, TextGenerationRequest, TextGenerationResponse


class MockLLMAdapter(ITextGenerationCapability):
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        return TextGenerationResponse(
            text="Grounded answer referencing document page 1.",
            prompt_tokens=20,
            completion_tokens=10
        )

    async def stream(self, request: TextGenerationRequest):
        yield "Grounded answer referencing document page 1."


class MockDeduplicationRetriever:
    async def execute_retrieval(self, **kwargs) -> RetrievalContext:
        ctx = RetrievalContext(
            query=kwargs.get("query", ""),
            workspace_id=kwargs.get("workspace_id", "ws_test"),
            retrieved_chunks=[
                {
                    "id": "doc_1_sub_1",
                    "media_id": "doc_1",
                    "title": "Quantum Physics Textbook.pdf",
                    "source_type": "pdf",
                    "page_number": 1,
                    "section_title": "Chapter 1",
                    "text": "Sub-chunk 1 text on Page 1."
                },
                {
                    "id": "doc_1_sub_2",
                    "media_id": "doc_1",
                    "title": "Quantum Physics Textbook.pdf",
                    "source_type": "pdf",
                    "page_number": 1,
                    "section_title": "Chapter 1",
                    "text": "Sub-chunk 2 text on Page 1."
                },
                {
                    "id": "vid_1_seg_1",
                    "media_id": "vid_1",
                    "title": "Lecture Video 1",
                    "source_type": "video",
                    "start_time": 10.0,
                    "end_time": 25.0,
                    "text": "Video transcript segment 1."
                },
                {
                    "id": "vid_1_seg_2",
                    "media_id": "vid_1",
                    "title": "Lecture Video 1",
                    "source_type": "video",
                    "start_time": 10.0,
                    "end_time": 25.0,
                    "text": "Video transcript segment 2 duplicate."
                }
            ],
            graph_triples=[],
            context_provenance={"document_id": "doc_1", "current_page": 1}
        )
        return ctx


def test_citation_deduplication():
    async def _test():
        registry = ModelRegistry()
        router = ProviderRouter(registry)
        bus = AIServiceBus(registry, router)
        bus.register_text_adapter("ollama", MockLLMAdapter())

        manager = WorkspaceIntelligenceManager(bus, retriever=MockDeduplicationRetriever())
        res = await manager.query_workspace("What is Quantum Mechanics?", workspace_id="ws_test")

        citations = res.get("citations", [])
        # Should deduplicate 4 sub-chunks into 2 unique citations (1 PDF page 1, 1 Video 10-25s)
        assert len(citations) == 2
        assert citations[0]["source_type"] == "pdf"
        assert citations[0]["page_number"] == 1
        assert citations[0]["title"] == "Quantum Physics Textbook.pdf"

        assert citations[1]["source_type"] == "video"
        assert citations[1]["start_time"] == 10.0
        assert citations[1]["title"] == "Lecture Video 1"

    asyncio.run(_test())
