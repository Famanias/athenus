from typing import List, Optional
import uuid
from app.domain.ai.capabilities import TranscriptSegmentDTO
from app.domain.ai.service_bus import AIServiceBus
from app.domain.knowledge.chunker import SemanticChunker
from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter
from app.infrastructure.events.event_bus import EventBus, DomainEvent

class EmbeddingWorker:
    """Worker handling semantic transcript chunking, embedding, and vector DB indexing."""
    
    def __init__(
        self,
        event_bus: EventBus,
        ai_service_bus: AIServiceBus,
        vector_store: Optional[EmbeddedQdrantVectorStoreAdapter] = None
    ) -> None:
        self.event_bus = event_bus
        self.ai_service_bus = ai_service_bus
        self.vector_store = vector_store or EmbeddedQdrantVectorStoreAdapter()
        self.chunker = SemanticChunker()

        # Subscribe to TranscriptCompletedEvent
        self.event_bus.subscribe("TranscriptCompletedEvent", self.handle_transcript_completed)

    async def handle_transcript_completed(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")
        raw_segments = event.payload.get("segments", [])

        try:
            current_stage = "chunking"
            # 1. Emit StageProgressEvent for chunking
            await self.event_bus.publish(DomainEvent(
                event_type="StageProgressEvent",
                aggregate_id=media_id,
                payload={
                    "media_id": media_id,
                    "workspace_id": workspace_id,
                    "stage": "chunking",
                    "progress": 75,
                    "message": "Generating semantic transcript chunks (~250 words)..."
                }
            ))

            # 2. Convert raw segments into DTOs
            segment_dtos = [
                TranscriptSegmentDTO(start_time=s["start_time"], end_time=s["end_time"], text=s["text"])
                for s in raw_segments
            ]

            # 3. Perform semantic chunking
            chunks = self.chunker.chunk_transcript(segment_dtos, media_id=media_id, workspace_id=workspace_id)
            if not chunks:
                await self.event_bus.publish(DomainEvent(
                    event_type="ChunksIndexedEvent",
                    aggregate_id=media_id,
                    payload={"media_id": media_id, "workspace_id": workspace_id, "chunk_count": 0}
                ))
                return

            current_stage = "vector_indexing"
            # 4. Emit StageProgressEvent for vector embedding & indexing
            await self.event_bus.publish(DomainEvent(
                event_type="StageProgressEvent",
                aggregate_id=media_id,
                payload={
                    "media_id": media_id,
                    "workspace_id": workspace_id,
                    "stage": "vector_indexing",
                    "progress": 90,
                    "message": f"Embedding {len(chunks)} chunks with SentenceTransformers and upserting into Embedded Qdrant..."
                }
            ))

            # 5. Generate embeddings via AI Service Bus
            embedding_capability = self.ai_service_bus.get_embedding_capability()
            chunk_texts = [c.text for c in chunks]
            embeddings = await embedding_capability.embed_texts(chunk_texts)

            # 5b. Persist canonical chunk metadata to SQLite for grounded learning artifact generation
            self._persist_chunks(chunks)

            # 6. Upsert vectors into Embedded Qdrant
            point_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, c.id)) for c in chunks]
            payloads = [
                {
                    "chunk_id": c.id,
                    "media_id": c.media_id,
                    "workspace_id": c.workspace_id,
                    "text": c.text,
                    "start_time": c.start_time,
                    "end_time": c.end_time,
                    "chunk_index": c.chunk_index
                }
                for c in chunks
            ]
            await self.vector_store.upsert(ids=point_ids, vectors=embeddings, payloads=payloads)

            # 7. Emit ChunksIndexedEvent
            await self.event_bus.publish(DomainEvent(
                event_type="ChunksIndexedEvent",
                aggregate_id=media_id,
                payload={
                    "media_id": media_id,
                    "workspace_id": workspace_id,
                    "chunk_count": len(chunks)
                }
            ))
        except Exception as e:
            err_msg = str(e).strip() or repr(e)
            await self.event_bus.publish(DomainEvent(
                event_type="ProcessingFailedEvent",
                aggregate_id=media_id,
                payload={"media_id": media_id, "stage": current_stage, "error": err_msg}
            ))

    def _persist_chunks(self, chunks) -> None:
        """Persist canonical transcript chunk metadata (text + timestamps) to SQLite."""
        try:
            from app.infrastructure.db.models import TranscriptChunkTable
            from app.infrastructure.db.session import engine
        except ImportError:
            return
        if not engine:
            return
        try:
            from sqlmodel import Session, select
            with Session(engine) as session:
                if not chunks:
                    return
                existing_stmt = select(TranscriptChunkTable).where(
                    TranscriptChunkTable.media_id == chunks[0].media_id
                )
                existing = session.scalars(existing_stmt).all() if hasattr(session, "scalars") else session.exec(existing_stmt).all()
                for rec in existing:
                    session.delete(rec)
                for c in chunks:
                    session.add(TranscriptChunkTable(
                        id=c.id,
                        media_id=c.media_id,
                        workspace_id=c.workspace_id,
                        text=c.text,
                        start_time=c.start_time,
                        end_time=c.end_time,
                        chunk_index=c.chunk_index,
                        word_count=c.word_count,
                    ))
                session.commit()
        except Exception:
            pass
