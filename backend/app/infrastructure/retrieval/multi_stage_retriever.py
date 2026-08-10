from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from app.domain.ai.service_bus import AIServiceBus
from app.domain.knowledge.bm25_retriever import BM25Retriever
from app.domain.knowledge.reranker import CrossEncoderReranker
from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.db.models import TranscriptSegmentTable, MediaItemTable
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


@dataclass
class RetrievalContext:
    query: str
    workspace_id: str
    media_id: Optional[str] = None
    document_id: Optional[str] = None
    source_type: Optional[str] = None
    current_timestamp: Optional[float] = None
    current_page: Optional[int] = None
    selected_text: Optional[str] = None
    rewritten_query: str = ""
    retrieved_chunks: List[Dict[str, Any]] = field(default_factory=list)
    graph_triples: List[str] = field(default_factory=list)
    assembled_prompt: str = ""
    context_provenance: Optional[Dict[str, Any]] = None


class MultiStageRetriever:
    """8-Stage Layered Retrieval Pipeline with Multi-Source Active Context Extraction."""
    
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

    async def execute_retrieval(
        self,
        query: str,
        workspace_id: str,
        media_id: Optional[str] = None,
        document_id: Optional[str] = None,
        source_type: Optional[str] = None,
        current_timestamp: Optional[float] = None,
        current_page: Optional[int] = None,
        selected_text: Optional[str] = None
    ) -> RetrievalContext:
        ctx = RetrievalContext(
            query=query,
            workspace_id=workspace_id,
            media_id=media_id,
            document_id=document_id,
            source_type=source_type,
            current_timestamp=current_timestamp,
            current_page=current_page,
            selected_text=selected_text
        )
        
        # Stage 1: Query Rewrite & Expansion
        ctx.rewritten_query = f"{query} (Context: educational materials breakdown)"

        # Stage 2-3: Extract Active Context (Video Timestamp OR PDF Document Page Window)
        active_context_text = ""
        provenance = None
        if source_type == "pdf" or document_id:
            active_context_text, provenance = self._extract_document_page_context(
                document_id=document_id or media_id,
                current_page=current_page,
                selected_text=selected_text
            )
        elif media_id and current_timestamp is not None:
            active_context_text, provenance = self._extract_timestamp_context(
                media_id=media_id,
                current_timestamp=current_timestamp,
                selected_text=selected_text
            )

        ctx.context_provenance = provenance

        # Stage 4: Knowledge Graph Traversal with Zero-Match Guardrail
        ctx.graph_triples = self.kg_service.get_workspace_triples(workspace_id, query=query)

        # Stage 5: Hybrid Search (Dense Embedded Qdrant + Sparse BM25)
        embedding_cap = self.ai_service_bus.get_embedding_capability()
        query_vector = await embedding_cap.embed_query(ctx.rewritten_query)

        dense_hits = await self.vector_store.search(
            query_vector=query_vector,
            limit=10,
            filter_workspace_id=workspace_id,
        )

        dense_docs = [hit["payload"] for hit in dense_hits if "payload" in hit]
        bm25_hits = self.bm25.rank(ctx.rewritten_query, dense_docs, top_k=5)

        # Stage 6: Cross-Encoder Re-Ranking
        reranked_chunks = self.reranker.rerank(ctx.rewritten_query, bm25_hits, top_k=3)
        ctx.retrieved_chunks = reranked_chunks

        # Stage 7: Context Compression
        compressed_text = self._compress_context(reranked_chunks)

        # Stage 8: Grounded Prompt Assembly
        ctx.assembled_prompt = self._assemble_prompt(query, compressed_text, ctx.graph_triples, active_context_text)
        return ctx

    def _extract_document_page_context(
        self,
        document_id: Optional[str],
        current_page: Optional[int],
        selected_text: Optional[str]
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        if not document_id or current_page is None:
            return "", None

        page_str = f"Page {current_page}"
        selected_info = f"\nUser Selected Text:\n\"{selected_text}\"\n" if selected_text else ""
        formatted_context = f"""
[Active Document Context]
Document ID: {document_id}
Active Page: {page_str}
{selected_info}"""

        provenance = {
            "document_id": document_id,
            "current_page": current_page,
            "selected_text": selected_text
        }
        return formatted_context, provenance

    def _extract_timestamp_context(
        self,
        media_id: Optional[str],
        current_timestamp: Optional[float],
        selected_text: Optional[str]
    ) -> tuple[str, Optional[Dict[str, Any]]]:
        if not media_id or current_timestamp is None or not engine or not Session or not select:
            return "", None

        try:
            window_start = max(0.0, current_timestamp - 30.0)
            window_end = current_timestamp + 30.0

            with Session(engine) as session:
                # Query media item title
                media_title = "Active Lecture Video"
                media_stmt = select(MediaItemTable).where(MediaItemTable.id == media_id)
                media_item = session.scalars(media_stmt).first() if hasattr(session, "scalars") else session.exec(media_stmt).first()
                if media_item and media_item.title:
                    media_title = media_item.title

                # Query segments in ±30s window around current_timestamp
                seg_stmt = (
                    select(TranscriptSegmentTable)
                    .where(TranscriptSegmentTable.media_id == media_id)
                    .where(TranscriptSegmentTable.start_time >= window_start)
                    .where(TranscriptSegmentTable.start_time <= window_end)
                    .order_by(TranscriptSegmentTable.start_time)
                )
                records = session.scalars(seg_stmt).all() if hasattr(session, "scalars") else session.exec(seg_stmt).all()

                if not records:
                    return "", None

                min_time = min(r.start_time for r in records)
                max_time = max(r.end_time for r in records)

                min_m, min_s = int(min_time // 60), int(min_time % 60)
                max_m, max_s = int(max_time // 60), int(max_time % 60)
                time_range_str = f"{min_m:02d}:{min_s:02d} - {max_m:02d}:{max_s:02d}"

                cur_m, cur_s = int(current_timestamp // 60), int(current_timestamp % 60)
                cur_str = f"{cur_m:02d}:{cur_s:02d}"

                lines = []
                for r in records:
                    r_m, r_s = int(r.start_time // 60), int(r.start_time % 60)
                    lines.append(f"[{r_m:02d}:{r_s:02d}] {r.text}")

                context_body = "\n".join(lines)
                selected_info = f"\nUser Selected Text:\n\"{selected_text}\"\n" if selected_text else ""

                formatted_context = f"""
[Active Video Playback Context]
Media Title: {media_title}
Active Playback Timestamp: {cur_str}
Surrounding Spoken Transcript ({time_range_str}):
{context_body}
{selected_info}"""

                provenance = {
                    "media_title": media_title,
                    "timestamp": cur_str,
                    "timestamp_range": time_range_str,
                    "segment_count": len(records),
                    "selected_text": selected_text
                }

                return formatted_context, provenance
        except Exception:
            return "", None

    def _compress_context(self, chunks: List[Dict[str, Any]]) -> str:
        parts = []
        for c in chunks:
            source_type = c.get("source_type")
            is_doc = source_type == "pdf" or "page_number" in c or (c.get("location") and c["location"].get("type") == "document")
            if is_doc:
                page_num = c.get("page_number") or (c.get("location") and c["location"].get("page")) or 1
                sec = c.get("section_title") or (c.get("location") and c["location"].get("section")) or f"Page {page_num}"
                badge = f"[Document Page {page_num} ({sec})]"
            else:
                start_min = int(c.get("start_time", 0.0) // 60)
                start_sec = int(c.get("start_time", 0.0) % 60)
                end_min = int(c.get("end_time", 0.0) // 60)
                end_sec = int(c.get("end_time", 0.0) % 60)
                badge = f"[{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}]"
            parts.append(f"{badge} {c.get('text', '')}")
        return "\n\n".join(parts)

    def _assemble_prompt(self, query: str, context_text: str, triples: List[str], active_context: str = "") -> str:
        kg_context = ""
        if triples:
            kg_context = "\nKnowledge Graph Concepts & Relationships:\n" + "\n".join(f"- {t}" for t in triples) + "\n"

        has_context = bool(context_text.strip() or active_context.strip() or kg_context.strip())
        if not has_context:
            return f"""You are Athenus AI, an intelligent learning assistant. Answer the question accurately using your general pretrained knowledge. Do NOT invent, fabricate, or cite any uploaded sources, page numbers, or timestamps.
User Question: {query}
Answer:"""

        return f"""You are Athenus AI, an intelligent learning assistant. Answer the user's question using ONLY the provided multi-source context (timestamped video segments, document pages, and knowledge graph relationships) below. Always include traceable citations (e.g. [MM:SS - MM:SS] for video or [Document Page X] for documents) matching the context.
{active_context}

Context:
{context_text}
{kg_context}
User Question: {query}
Answer:"""
