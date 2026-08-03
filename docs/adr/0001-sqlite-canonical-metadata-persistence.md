# ADR 0001: SQLite as Canonical Metadata Persistence Engine

* **Status**: Accepted & Implemented
* **Date**: 2026-08-03
* **Context**: Initially, workspace definitions, media item statuses, transcript mappings, and chat session turns were stored in in-memory dictionary maps. Upon backend restart or application closing, all uploaded video metadata and conversation threads were destroyed.
* **Decision**: Transition to **SQLite** (`./data/athenus.db`) as the canonical metadata database using `SQLModel` and `SQLAlchemy` ORM mapping.
* **Alternatives Considered**:
  - *In-Memory JSON Dumps*: Fragile to crash corruption and lacks query indexing.
  - *External PostgreSQL / MySQL Server*: Violates local-first, zero-dependency desktop deployment model.
* **Rationale**: SQLite is embedded, zero-config, ACID-compliant, local-first, and highly performant for desktop applications.
* **Trade-offs**: Single-writer lock model, but completely sufficient for single-user desktop learning application workloads.
