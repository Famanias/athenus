from typing import Dict, Any, List, Optional
from app.domain.ai.capabilities import TextGenerationRequest
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever

class MemoryManager:
    """Manages short-term conversation turns and working workspace context."""
    def __init__(self) -> None:
        self.conversation_history: List[Dict[str, str]] = []

    def add_turn(self, role: str, content: str) -> None:
        self.conversation_history.append({"role": role, "content": content})

class ContextBuilder:
    """Builds system & user prompts for RAG grounding."""
    def format_citation_prompt(self, query: str, context_text: str) -> str:
        return f"""Instruction: Answer the user's question accurately based on the video context below. Append timestamp badges (e.g. [01:15 - 01:45]) for every fact referenced.

Video Context:
{context_text}

User Question: {query}
Answer:"""

class WorkspaceIntelligenceManager:
    """Decomposed Workspace Intelligence Subsystem Manager."""
    
    def __init__(self, ai_service_bus: AIServiceBus, retriever: Optional[MultiStageRetriever] = None) -> None:
        self.ai_service_bus = ai_service_bus
        self.retriever = retriever or MultiStageRetriever(ai_service_bus)
        self.memory_manager = MemoryManager()
        self.context_builder = ContextBuilder()

    async def query_workspace(
        self,
        query: str,
        workspace_id: str,
        media_id: Optional[str] = None,
        current_timestamp: Optional[float] = None,
        selected_text: Optional[str] = None
    ) -> Dict[str, Any]:
        # 1. Multi-Stage Retrieval with timestamp & selected text context
        retrieval_ctx = await self.retriever.execute_retrieval(
            query=query,
            workspace_id=workspace_id,
            media_id=media_id,
            current_timestamp=current_timestamp,
            selected_text=selected_text
        )
        
        # 2. Text Generation via AI Service Bus
        text_capability = self.ai_service_bus.get_text_capability()
        gen_request = TextGenerationRequest(
            prompt=retrieval_ctx.assembled_prompt,
            temperature=0.3
        )
        response = await text_capability.generate(gen_request)

        # 3. Update Memory
        self.memory_manager.add_turn("user", query)
        self.memory_manager.add_turn("assistant", response.text)

        return {
            "query": query,
            "answer": response.text,
            "citations": [
                {
                    "chunk_id": c.get("id"),
                    "start_time": c.get("start_time"),
                    "end_time": c.get("end_time"),
                    "text": c.get("text")
                }
                for c in retrieval_ctx.retrieved_chunks
            ],
            "context_provenance": retrieval_ctx.context_provenance
        }
