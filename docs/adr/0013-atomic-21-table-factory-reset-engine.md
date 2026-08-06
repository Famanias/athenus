# ADR 0013: Atomic 21-Table Factory Reset Engine

* **Status**: Accepted & Implemented
* **Date**: 2026-08-06
* **Context**: The "CLEAR MY DATA" factory reset endpoint previously purged only 10 initial tables, leaving newly introduced domain tables (flashcards, quizzes, blueprints, concept mastery, analytics) as orphan rows in SQLite.
* **Decision**: Expand `SystemResetService.perform_factory_reset()` into an **Atomic 21-Table Purge Engine**. The purge pipeline explicitly deletes records across all 21 SQLModel database tables in strict child-to-parent foreign key order, drops and re-creates vector store collections in Qdrant, deletes uploaded media files from disk, and clears in-memory progress snapshots.
* **Alternatives Considered**:
  - *Deleting SQLite DB File*: Causes file lock errors on Windows when connection pools are open.
  - *Partial Table Purge*: Leaves orphaned records and inconsistent system state.
* **Rationale**: Explicit child-to-parent table deletion inside a single SQLite transaction guarantees 100% data destruction while preserving database schema integrity and connection pool stability.
* **Trade-offs**: Table list must be updated whenever new DB tables are added, but guarantees zero residual privacy leaks.
