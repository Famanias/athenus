from typing import Generator
from app.core.config import settings

try:
    from sqlmodel import SQLModel, Session, create_engine
    connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
    engine = create_engine(settings.DATABASE_URL, echo=settings.DEBUG, connect_args=connect_args)

    def init_db() -> None:
        """Initialize database tables."""
        SQLModel.metadata.create_all(engine)

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
