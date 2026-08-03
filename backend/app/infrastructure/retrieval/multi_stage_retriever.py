from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from app.domain.ai.service_bus import AIServiceBus
from app.domain.knowledge.bm25_retriever import BM25Retriever
from app.domain.knowledge.reranker import CrossEncoderReranker
from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter

from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService

@dataclass
class RetrievalContext:
    query: str
    workspace_id: str
    media_id: Optional[str] = None
    rewritten_query: str = ""
    retrieved_chunks: List[Dict[str, Any]] = field(default_factory=list)
    graph_triples: List[str] = field(default_factory=list)
    assembled_prompt: str = ""

class MultiStageRetriever:
    """8-Stage Layered Retrieval Pipeline."""
    
    def __init__(
        self,
        ai_service_bus: AIServiceBus,
        vector_store: Optional[EmbeddedQdrantVectorStoreAdapter] = None,
        kg_service: Optional[KnowledgeGraphService] = None
    ) -> None:
        self.ai_service_bus = ai_service_bus
        self.vector_store = vector_store or EmbeddedQdrantVectorStoreAdapter()
        self.kg_service = kg_service or KnowledgeGraphService()
        self.bm25 = BM25Retriever()
        self.reranker = CrossEncoderReranker()

    async def execute_retrieval(self, query: str, workspace_id: str, media_id: Optional[str] = None) -> RetrievalContext:
        ctx = RetrievalContext(query=query, workspace_id=workspace_id, media_id=media_id)
        
        # Stage 1: Query Rewrite & Expansion
        ctx.rewritten_query = f"{query} (Context: educational video breakdown)"

        # Stage 2: Intent Detection
        # Stage 3: Workspace Context Injection
        
        # Stage 4: Knowledge Graph Traversal
        ctx.graph_triples = self.kg_service.get_workspace_triples(workspace_id)

        # Stage 5: Hybrid Search (Dense Embedded Qdrant + Sparse BM25)
        embedding_cap = self.ai_service_bus.get_embedding_capability()
        query_vector = await embedding_cap.embed_query(ctx.rewritten_query)

        dense_hits = await self.vector_store.search(
            query_vector=query_vector,
            limit=10,
            filter_media_id=media_id,
            filter_workspace_id=workspace_id
        )

        dense_docs = [hit["payload"] for hit in dense_hits if "payload" in hit]
        bm25_hits = self.bm25.rank(ctx.rewritten_query, dense_docs, top_k=5)

        # Stage 6: Cross-Encoder Re-Ranking
        reranked_chunks = self.reranker.rerank(ctx.rewritten_query, bm25_hits, top_k=3)
        ctx.retrieved_chunks = reranked_chunks

        # Stage 7: Context Compression
        compressed_text = self._compress_context(reranked_chunks)

        # Stage 8: Grounded Prompt Assembly
        ctx.assembled_prompt = self._assemble_prompt(query, compressed_text, ctx.graph_triples)
        return ctx

    def _compress_context(self, chunks: List[Dict[str, Any]]) -> str:
        parts = []
        for c in chunks:
            start_min = int(c.get("start_time", 0.0) // 60)
            start_sec = int(c.get("start_time", 0.0) % 60)
            end_min = int(c.get("end_time", 0.0) // 60)
            end_sec = int(c.get("end_time", 0.0) % 60)
            time_badge = f"[{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}]"
            parts.append(f"{time_badge} {c.get('text', '')}")
        return "\n\n".join(parts)

    def _assemble_prompt(self, query: str, context_text: str, triples: List[str]) -> str:
        kg_context = ""
        if triples:
            kg_context = "\nKnowledge Graph Concepts & Relationships:\n" + "\n".join(f"- {t}" for t in triples) + "\n"

        return f"""You are Athenus AI, an intelligent learning assistant. Answer the user's question using ONLY the provided timestamped video context and knowledge graph relationships below. Always include clickable timestamp citations (e.g. [MM:SS - MM:SS]) matching the context.

Context:
{context_text}
{kg_context}
User Question: {query}
Answer:"""
