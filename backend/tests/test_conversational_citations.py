import asyncio
import pytest
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.domain.knowledge.query_classifier import is_conversational_query
from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever, RetrievalContext
from app.application.services.workspace_intelligence import WorkspaceIntelligenceManager
from app.domain.ai.capabilities import ITextGenerationCapability, TextGenerationRequest, TextGenerationResponse


class MockLLMAdapter(ITextGenerationCapability):
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        prompt_text = request.prompt
        if "Hi." in prompt_text or "Hello" in prompt_text:
            return TextGenerationResponse(text="Hello! How can I help you today?", prompt_tokens=10, completion_tokens=10)
        elif "Thanks" in prompt_text or "thank you" in prompt_text.lower():
            return TextGenerationResponse(text="You're very welcome!", prompt_tokens=10, completion_tokens=5)
        elif "Good morning" in prompt_text:
            return TextGenerationResponse(text="Good morning! What would you like to study today?", prompt_tokens=10, completion_tokens=10)
        elif "How are you" in prompt_text:
            return TextGenerationResponse(text="I'm doing well, thank you! Ready to learn.", prompt_tokens=10, completion_tokens=10)
        elif "photosynthesis" in prompt_text.lower():
            return TextGenerationResponse(text="Photosynthesis is the process used by plants to convert light energy into chemical energy [Document Page 42].", prompt_tokens=50, completion_tokens=20)
        else:
            return TextGenerationResponse(text="Pretrained knowledge response.", prompt_tokens=30, completion_tokens=10)

    async def stream(self, request: TextGenerationRequest):
        yield "Response"


class MockRetrieverWithLibrary:
    def __init__(self, bus):
        self.ai_service_bus = bus

    async def execute_retrieval(self, query: str, workspace_id: str, **kwargs) -> RetrievalContext:
        if is_conversational_query(query):
            return RetrievalContext(
                query=query,
                workspace_id=workspace_id,
                retrieved_chunks=[],
                graph_triples=[],
                context_provenance=None,
                assembled_prompt=f"You are Athenus AI... User Question: {query}\nAnswer:"
            )

        if "photosynthesis" in query.lower():
            return RetrievalContext(
                query=query,
                workspace_id=workspace_id,
                retrieved_chunks=[{
                    "id": "bio_doc_1",
                    "media_id": "bio_101",
                    "title": "Biology Textbook.pdf",
                    "source_type": "pdf",
                    "page_number": 42,
                    "section_title": "Chapter 4",
                    "text": "Photosynthesis converts light into chemical energy."
                }],
                graph_triples=[],
                context_provenance={"document_id": "bio_101", "current_page": 42},
                has_relevant_context=True,
                assembled_prompt=f"Context: Photosynthesis... User Question: {query}\nAnswer:"
            )

        # Unrelated query in workspace with existing sources — low relevance chunks filtered out by reranker
        return RetrievalContext(
            query=query,
            workspace_id=workspace_id,
            retrieved_chunks=[],
            graph_triples=[],
            context_provenance=None,
            assembled_prompt=f"You are Athenus AI... User Question: {query}\nAnswer:"
        )


def test_conversational_queries_produce_zero_citations():
    async def _test():
        registry = ModelRegistry()
        router = ProviderRouter(registry)
        bus = AIServiceBus(registry, router)
        bus.register_text_adapter("ollama", MockLLMAdapter())

        retriever = MockRetrieverWithLibrary(bus)
        manager = WorkspaceIntelligenceManager(bus, retriever=retriever)

        # 1. "Hi." produces no citations and no retrieval-status message
        res_hi = await manager.query_workspace("Hi.", workspace_id="library_ws")
        assert res_hi["citations"] == [], f"Expected [] citations for 'Hi.', got {res_hi['citations']}"
        assert not res_hi["answer"].startswith("No relevant context found")

        # 2. "Hello." produces no citations and no retrieval-status message
        res_hello = await manager.query_workspace("Hello.", workspace_id="library_ws")
        assert res_hello["citations"] == [], f"Expected [] citations for 'Hello.', got {res_hello['citations']}"
        assert not res_hello["answer"].startswith("No relevant context found")

        # 3. Other simple conversational queries ("Thanks", "Good morning", "How are you?") produce no citations and no retrieval-status message
        res_thanks = await manager.query_workspace("Thanks!", workspace_id="library_ws")
        assert res_thanks["citations"] == [], f"Expected [] citations for 'Thanks!', got {res_thanks['citations']}"
        assert not res_thanks["answer"].startswith("No relevant context found")

        res_gm = await manager.query_workspace("Good morning", workspace_id="library_ws")
        assert res_gm["citations"] == [], f"Expected [] citations for 'Good morning', got {res_gm['citations']}"
        assert not res_gm["answer"].startswith("No relevant context found")

        res_hru = await manager.query_workspace("How are you?", workspace_id="library_ws")
        assert res_hru["citations"] == [], f"Expected [] citations for 'How are you?', got {res_hru['citations']}"
        assert not res_hru["answer"].startswith("No relevant context found")

        # 4. Genuine information query with relevant evidence produces valid citations
        res_photo = await manager.query_workspace("What is photosynthesis?", workspace_id="library_ws")
        assert len(res_photo["citations"]) == 1
        assert res_photo["citations"][0]["page_number"] == 42
        assert res_photo["citations"][0]["title"] == "Biology Textbook.pdf"

        # 5. Information query with no relevant evidence does not inherit unrelated workspace citations and no raw status message
        res_unrelated = await manager.query_workspace("What is quantum string theory?", workspace_id="library_ws")
        assert res_unrelated["citations"] == []
        assert not res_unrelated["answer"].startswith("No relevant context found")

    asyncio.run(_test())
