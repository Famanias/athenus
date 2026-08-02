# 2. SQLite for Embedded Desktop Metadata Storage

* **Status**: Accepted
* **Date**: 2026-08-02
* **Context**: Desktop Mode requires a relational database engine for media metadata, transcripts, user progress, and system settings without requiring non-technical users to install or manage an external database server like PostgreSQL.

## Decision
We select **SQLite (via SQLModel / SQLAlchemy + Alembic migrations)** as the embedded relational store for single-user Desktop Mode. When running in Cloud or Multi-user Mode, the exact same domain repositories connect to **PostgreSQL**.

## Consequences
* **Positive**: Zero user installation friction, lightweight binary size, fast local file-backed queries.
* **Negative**: Concurrency constraints under multi-writer scenarios (handled by worker queue serialization in single-user mode).
