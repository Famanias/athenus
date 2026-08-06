from typing import Generator
from app.core.config import settings

try:
    from sqlmodel import SQLModel, Session, create_engine
    connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
    engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, connect_args=connect_args)

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
                conn.commit()
        except Exception as e:
            print("MIGRATION ERROR:", e)

    _migrate_db_columns()

    def init_db() -> None:
        """Initialize database tables."""
        import app.infrastructure.db.models  # noqa: F401
        SQLModel.metadata.create_all(engine)
        _migrate_db_columns()

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
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        def init_db() -> None:
            Base.metadata.create_all(bind=engine)

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
