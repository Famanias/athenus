# 3. Embedded Qdrant for Desktop Vector Storage

* **Status**: Accepted
* **Date**: 2026-08-02
* **Context**: Vector similarity search is essential for semantic RAG retrieval over transcript chunks. Desktop users should not be forced to run Docker Desktop to run a local vector database.

## Decision
We select **Embedded Qdrant (via `qdrant-client` local path storage)** as the primary vector store for Desktop Mode. Docker containerized Qdrant and Qdrant Cloud remain supported via configuration options for high-scale or server deployments.

## Consequences
* **Positive**: Native Python/Rust local disk storage with zero Docker dependency for desktop end-users; seamless migration to Qdrant Cloud or Docker container.
* **Negative**: Must manage local file locks and index disk footprint gracefully.
