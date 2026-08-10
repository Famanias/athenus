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
        document_id: Optional[str] = None,
        source_type: Optional[str] = None,
        current_timestamp: Optional[float] = None,
        current_page: Optional[int] = None,
        selected_text: Optional[str] = None
    ) -> Dict[str, Any]:
        # 1. Multi-Stage Retrieval with timestamp/page & selected text context
        retrieval_ctx = await self.retriever.execute_retrieval(
            query=query,
            workspace_id=workspace_id,
            media_id=media_id,
            document_id=document_id,
            source_type=source_type,
            current_timestamp=current_timestamp,
            current_page=current_page,
            selected_text=selected_text
        )
        
        # 2. Text Generation via AI Service Bus
        text_capability = self.ai_service_bus.get_text_capability()
        gen_request = TextGenerationRequest(
            prompt=retrieval_ctx.assembled_prompt,
            temperature=0.3,
            max_tokens=2048
        )
        response = await text_capability.generate(gen_request)
        final_answer = response.text
        has_active_provenance = False
        if retrieval_ctx.context_provenance and isinstance(retrieval_ctx.context_provenance, dict):
            has_active_provenance = any(v for k, v in retrieval_ctx.context_provenance.items() if v is not None)

        if not retrieval_ctx.retrieved_chunks and not retrieval_ctx.graph_triples and not has_active_provenance:
            if not final_answer.startswith("No relevant context found"):
                final_answer = f"No relevant context found in workspace materials. {final_answer}"

        # 3. Update Memory
        self.memory_manager.add_turn("user", query)
        self.memory_manager.add_turn("assistant", final_answer)

        # 4. Generalized Citations formatting
        formatted_citations = []
        for c in retrieval_ctx.retrieved_chunks:
            c_source = c.get("source_type", "video")
            is_doc = c_source == "pdf" or "page_number" in c or (c.get("location") and c["location"].get("type") == "document")
            if is_doc:
                page_num = c.get("page_number") or (c.get("location") and c["location"].get("page")) or 1
                sec = c.get("section_title") or (c.get("location") and c["location"].get("section")) or f"Page {page_num}"
                formatted_citations.append({
                    "chunk_id": c.get("id") or c.get("chunk_id"),
                    "source_type": "pdf",
                    "start_time": None,
                    "end_time": None,
                    "page_number": page_num,
                    "section_title": sec,
                    "location": c.get("location") or {"type": "document", "page": page_num, "section": sec},
                    "text": c.get("text", "")
                })
            else:
                formatted_citations.append({
                    "chunk_id": c.get("id") or c.get("chunk_id"),
                    "source_type": "video",
                    "start_time": c.get("start_time", 0.0),
                    "end_time": c.get("end_time", 0.0),
                    "page_number": None,
                    "section_title": None,
                    "location": c.get("location") or {"type": "video", "start_time": c.get("start_time", 0.0), "end_time": c.get("end_time", 0.0)},
                    "text": c.get("text", "")
                })

        return {
            "query": query,
            "answer": final_answer,
            "citations": formatted_citations,
            "context_provenance": retrieval_ctx.context_provenance
        }

