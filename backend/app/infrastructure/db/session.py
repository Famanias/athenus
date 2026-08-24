from typing import Generator
from app.core.config import settings
from app.infrastructure.db.fts5_repair import repair_transcript_chunks_fts


def _configure_sqlite_engine(db_engine, database_url: str) -> None:
    """Apply the local-first concurrency/read-throughput profile per connection."""
    if db_engine is None or "sqlite" not in database_url:
        return
    from sqlalchemy import event

    @event.listens_for(db_engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout = 5000")
            cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA cache_size = -64000")
            cursor.execute("PRAGMA mmap_size = 268435456")
            cursor.execute("PRAGMA foreign_keys = ON")
        finally:
            cursor.close()

try:
    from sqlmodel import SQLModel, Session, create_engine
    connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
    engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, connect_args=connect_args)
    _configure_sqlite_engine(engine, settings.DATABASE_URL)

    def _migrate_db_columns() -> None:
        if not engine:
            return
        try:
            from sqlalchemy import inspect, text
            inspector = inspect(engine)
            with engine.connect() as conn:
                if inspector.has_table("workspaces"):
                    cols = [c["name"] for c in inspector.get_columns("workspaces")]
                    if "is_pinned" not in cols:
                        conn.execute(text("ALTER TABLE workspaces ADD COLUMN is_pinned BOOLEAN DEFAULT 0"))
                    if "is_archived" not in cols:
                        conn.execute(text("ALTER TABLE workspaces ADD COLUMN is_archived BOOLEAN DEFAULT 0"))
                    if "settings_json" not in cols:
                        conn.execute(text("ALTER TABLE workspaces ADD COLUMN settings_json TEXT"))
                    if "last_accessed_at" not in cols:
                        conn.execute(text("ALTER TABLE workspaces ADD COLUMN last_accessed_at DATETIME"))

                if inspector.has_table("chat_sessions"):
                    cols = [c["name"] for c in inspector.get_columns("chat_sessions")]
                    if "is_pinned" not in cols:
                        conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN is_pinned BOOLEAN DEFAULT 0"))
                    if "is_archived" not in cols:
                        conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN is_archived BOOLEAN DEFAULT 0"))
                    if "last_message_at" not in cols:
                        conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN last_message_at DATETIME"))
                    if "message_count" not in cols:
                        conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN message_count INTEGER DEFAULT 0"))
                    if "preview_text" not in cols:
                        conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN preview_text TEXT"))

                if inspector.has_table("knowledge_concepts"):
                    cols = [c["name"] for c in inspector.get_columns("knowledge_concepts")]
                    if "status" not in cols:
                        conn.execute(text("ALTER TABLE knowledge_concepts ADD COLUMN status VARCHAR DEFAULT 'ready'"))
                    if "media_id" not in cols:
                        conn.execute(text("ALTER TABLE knowledge_concepts ADD COLUMN media_id VARCHAR"))
                    if "source_chunk_ids" not in cols:
                        conn.execute(text("ALTER TABLE knowledge_concepts ADD COLUMN source_chunk_ids TEXT"))
                    if "start_time" not in cols:
                        conn.execute(text("ALTER TABLE knowledge_concepts ADD COLUMN start_time FLOAT"))
                    if "end_time" not in cols:
                        conn.execute(text("ALTER TABLE knowledge_concepts ADD COLUMN end_time FLOAT"))
                    if "embedding" not in cols:
                        conn.execute(text("ALTER TABLE knowledge_concepts ADD COLUMN embedding TEXT"))
                    if "updated_at" not in cols:
                        conn.execute(text("ALTER TABLE knowledge_concepts ADD COLUMN updated_at DATETIME"))

                if inspector.has_table("knowledge_relations"):
                    cols = [c["name"] for c in inspector.get_columns("knowledge_relations")]
                    if "weight" not in cols:
                        conn.execute(text("ALTER TABLE knowledge_relations ADD COLUMN weight FLOAT DEFAULT 1.0"))
                    if "media_id" not in cols:
                        conn.execute(text("ALTER TABLE knowledge_relations ADD COLUMN media_id VARCHAR"))
                    if "updated_at" not in cols:
                        conn.execute(text("ALTER TABLE knowledge_relations ADD COLUMN updated_at DATETIME"))

                if inspector.has_table("artifact_jobs"):
                    cols = [c["name"] for c in inspector.get_columns("artifact_jobs")]
                    if "stage" not in cols:
                        conn.execute(text("ALTER TABLE artifact_jobs ADD COLUMN stage VARCHAR DEFAULT 'queued'"))

                if inspector.has_table("system_settings"):
                    cols = [c["name"] for c in inspector.get_columns("system_settings")]
                    if "active_models" not in cols:
                        conn.execute(text("ALTER TABLE system_settings ADD COLUMN active_models TEXT"))

                if inspector.has_table("notes"):
                    cols = [c["name"] for c in inspector.get_columns("notes")]
                    if "folder_id" not in cols:
                        conn.execute(text("ALTER TABLE notes ADD COLUMN folder_id VARCHAR"))
                    if "content" not in cols:
                        conn.execute(text("ALTER TABLE notes ADD COLUMN content TEXT"))
                    if "generation_method" not in cols:
                        conn.execute(text("ALTER TABLE notes ADD COLUMN generation_method VARCHAR DEFAULT 'llm'"))
                    if "fallback_reason" not in cols:
                        conn.execute(text("ALTER TABLE notes ADD COLUMN fallback_reason VARCHAR"))
                    if "provider_id" not in cols:
                        conn.execute(text("ALTER TABLE notes ADD COLUMN provider_id VARCHAR"))
                    if "model_id" not in cols:
                        conn.execute(text("ALTER TABLE notes ADD COLUMN model_id VARCHAR"))
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_notes_folder_id ON notes (folder_id)"))
                conn.commit()
        except Exception as e:
            print("MIGRATION ERROR:", e)

    _migrate_db_columns()

    def init_db() -> None:
        """Initialize database tables."""
        import app.infrastructure.db.models  # noqa: F401
        SQLModel.metadata.create_all(engine)
        _migrate_db_columns()
        if engine and "sqlite" in settings.DATABASE_URL:
            try:
                from sqlalchemy import text
                with engine.connect() as conn:
                    conn.execute(text("""
                        CREATE VIRTUAL TABLE IF NOT EXISTS transcript_chunks_fts USING fts5(
                            chunk_id UNINDEXED,
                            workspace_id UNINDEXED,
                            text
                        );
                    """))
                    conn.execute(text("""
                        CREATE TRIGGER IF NOT EXISTS transcript_chunks_ai AFTER INSERT ON transcript_chunks BEGIN
                            INSERT INTO transcript_chunks_fts(chunk_id, workspace_id, text) VALUES (new.id, new.workspace_id, new.text);
                        END;
                    """))
                    conn.execute(text("""
                        CREATE TRIGGER IF NOT EXISTS transcript_chunks_ad AFTER DELETE ON transcript_chunks BEGIN
                            DELETE FROM transcript_chunks_fts WHERE chunk_id = old.id;
                        END;
                    """))
                    conn.execute(text("""
                        CREATE TRIGGER IF NOT EXISTS transcript_chunks_au AFTER UPDATE ON transcript_chunks BEGIN
                            DELETE FROM transcript_chunks_fts WHERE chunk_id = old.id;
                            INSERT INTO transcript_chunks_fts(chunk_id, workspace_id, text) VALUES (new.id, new.workspace_id, new.text);
                        END;
                    """))
                    conn.commit()
            except Exception as e:
                print("FTS5 INIT ERROR:", e)
            # Self-heal legacy DBs whose transcript_chunks_fts vtable is broken
            # (e.g. vtable constructor failed). `repair_transcript_chunks_fts`
            # is a no-op on healthy databases. Without this, factory-reset and
            # any DELETE/UPDATE on transcript_chunks would 500.
            try:
                repair_transcript_chunks_fts(engine)
            except Exception as e:
                print("FTS5 REPAIR ERROR:", e)

    def get_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session
except ImportError:
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker, DeclarativeBase
        
        class Base(DeclarativeBase):
            pass
            
        connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
        engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, connect_args=connect_args)
        _configure_sqlite_engine(engine, settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        def init_db() -> None:
            import app.infrastructure.db.models  # noqa: F401
            Base.metadata.create_all(bind=engine)
            try:
                from sqlalchemy import inspect, text

                inspector = inspect(engine)
                if inspector.has_table("notes"):
                    columns = [column["name"] for column in inspector.get_columns("notes")]
                    with engine.begin() as connection:
                        if "folder_id" not in columns:
                            connection.execute(text("ALTER TABLE notes ADD COLUMN folder_id VARCHAR"))
                        if "content" not in columns:
                            connection.execute(text("ALTER TABLE notes ADD COLUMN content TEXT"))
                        if "generation_method" not in columns:
                            connection.execute(text("ALTER TABLE notes ADD COLUMN generation_method VARCHAR DEFAULT 'llm'"))
                        if "fallback_reason" not in columns:
                            connection.execute(text("ALTER TABLE notes ADD COLUMN fallback_reason VARCHAR"))
                        if "provider_id" not in columns:
                            connection.execute(text("ALTER TABLE notes ADD COLUMN provider_id VARCHAR"))
                        if "model_id" not in columns:
                            connection.execute(text("ALTER TABLE notes ADD COLUMN model_id VARCHAR"))
                        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_notes_folder_id ON notes (folder_id)"))
            except Exception as exc:
                print("MIGRATION ERROR:", exc)

        def get_session():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()
    except ImportError:
        engine = None
        def init_db() -> None:
            pass
        def get_session():
            yield None
