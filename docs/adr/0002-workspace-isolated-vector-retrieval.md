# ADR 0002: Workspace-Isolated Vector Retrieval in Qdrant & RAG

* **Status**: Accepted & Implemented
* **Date**: 2026-08-03
* **Context**: Embedded Qdrant vector store adapter executed dense search without workspace payload filtering. As a result, querying one workspace returned context hits and citations from completely unrelated lecture videos in other workspaces.
* **Decision**: Add mandatory `filter_workspace_id` parameter to `EmbeddedQdrantVectorStoreAdapter.search()` and pass `workspace_id` down from `MultiStageRetriever.execute_retrieval()`.
* **Alternatives Considered**:
  - *Separate Vector Collections per Workspace*: Would create collection sprawl and unnecessary disk management overhead in Qdrant.
* **Rationale**: Payload filtering (`FieldCondition(key="workspace_id", match=MatchValue(value=filter_workspace_id))`) in a single Qdrant collection is fast, clean, scalable, and guarantees 100% vector isolation.
* **Trade-offs**: Requires `workspace_id` to be indexed in vector payload metadata.
