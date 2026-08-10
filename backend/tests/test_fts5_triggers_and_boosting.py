import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import asyncio

from app.domain.knowledge.bm25_retriever import BM25Retriever
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever


class MockVectorStoreForBoosting:
    def __init__(self, hits):
        self.hits = hits

    async def search(self, query_vector, limit=10, filter_workspace_id=None, **kwargs):
        return self.hits


class MockEmbeddingAdapter:
    async def embed_query(self, text: str):
        return [0.1] * 384


def test_fts5_database_triggers():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        # Create tables & FTS5
        conn.execute(text("""
            CREATE TABLE transcript_chunks (
                id VARCHAR PRIMARY KEY,
                workspace_id VARCHAR,
                media_id VARCHAR,
                text TEXT,
                start_time FLOAT,
                end_time FLOAT,
                chunk_index INT,
                word_count INT
            );
        """))
        conn.execute(text("""
            CREATE VIRTUAL TABLE transcript_chunks_fts USING fts5(
                chunk_id UNINDEXED,
                workspace_id UNINDEXED,
                text
            );
        """))
        conn.execute(text("""
            CREATE TRIGGER transcript_chunks_ai AFTER INSERT ON transcript_chunks BEGIN
                INSERT INTO transcript_chunks_fts(chunk_id, workspace_id, text) VALUES (new.id, new.workspace_id, new.text);
            END;
        """))
        conn.execute(text("""
            CREATE TRIGGER transcript_chunks_ad AFTER DELETE ON transcript_chunks BEGIN
                DELETE FROM transcript_chunks_fts WHERE chunk_id = old.id;
            END;
        """))
        conn.execute(text("""
            CREATE TRIGGER transcript_chunks_au AFTER UPDATE ON transcript_chunks BEGIN
                DELETE FROM transcript_chunks_fts WHERE chunk_id = old.id;
                INSERT INTO transcript_chunks_fts(chunk_id, workspace_id, text) VALUES (new.id, new.workspace_id, new.text);
            END;
        """))

        # 1. Test INSERT trigger
        conn.execute(text("INSERT INTO transcript_chunks (id, workspace_id, text) VALUES ('chunk_1', 'ws_1', 'photosynthesis converts light energy');"))
        fts_rows = conn.execute(text("SELECT * FROM transcript_chunks_fts WHERE workspace_id = 'ws_1';")).mappings().all()
        assert len(fts_rows) == 1
        assert fts_rows[0]["chunk_id"] == "chunk_1"

        # 2. Test UPDATE trigger
        conn.execute(text("UPDATE transcript_chunks SET text = 'photosynthesis converts sunlight to chemical energy' WHERE id = 'chunk_1';"))
        fts_updated = conn.execute(text("SELECT * FROM transcript_chunks_fts WHERE workspace_id = 'ws_1';")).mappings().all()
        assert len(fts_updated) == 1
        assert "sunlight" in fts_updated[0]["text"]

        # 3. Test DELETE trigger
        conn.execute(text("DELETE FROM transcript_chunks WHERE id = 'chunk_1';"))
        fts_deleted = conn.execute(text("SELECT * FROM transcript_chunks_fts WHERE workspace_id = 'ws_1';")).mappings().all()
        assert len(fts_deleted) == 0


def test_active_item_boosting_and_rrf_fusion():
    async def _test():
        hits = [
            {"score": 0.5, "payload": {"id": "c1", "document_id": "doc_unrelated", "text": "general physics info"}},
            {"score": 0.5, "payload": {"id": "c2", "document_id": "doc_active", "text": "active photosynthesis page"}}
        ]
        bus = AIServiceBus(ModelRegistry(), ProviderRouter(ModelRegistry()))
        bus.register_embedding_adapter("sentence_transformers", MockEmbeddingAdapter())

        retriever = MultiStageRetriever(bus, vector_store=MockVectorStoreForBoosting(hits))
        
        # Retrieval with active document context (document_id = doc_active)
        ctx = await retriever.execute_retrieval(query="photosynthesis page info", workspace_id="ws_1", document_id="doc_active")

        # c2 score is boosted 1.5x (0.5 * 1.5 = 0.75) vs c1 (0.5), so c2 ranks first
        assert len(ctx.retrieved_chunks) > 0
        assert ctx.retrieved_chunks[0]["document_id"] == "doc_active"

    asyncio.run(_test())
