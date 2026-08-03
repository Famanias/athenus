# Implementation Plan — Phase 2: Proper Workspace Isolation

Establish strict workspace knowledge isolation so that vector search and multi-stage retrieval queries never leak embeddings or knowledge passages across different workspaces.

---

## User Review Required

> [!IMPORTANT]
> **Key Architecture Decisions for Phase 2:**
> 1. **Qdrant Payload Filtering by `workspace_id`**: Update `EmbeddedQdrantVectorStoreAdapter.search()` to filter points by `workspace_id` first, preventing cross-workspace vector retrieval.
> 2. **Multi-Stage Retriever Alignment**: Update `MultiStageRetriever.execute_retrieval()` to pass both `workspace_id` and optional `media_id` down to the Qdrant vector store adapter and BM25 sparse ranker.
> 3. **Combined Filter Support**: Support dual filtering (`must` clause containing both `workspace_id` AND `media_id` when searching a specific video within a workspace).
> 4. **Workflow Checkpoint**: Stop after Phase 2 verification and self-review to request user approval before beginning Phase 3.

---

## Proposed Changes

### Vector Store Adapter Layer (`backend/app/infrastructure/adapters/`)

#### [MODIFY] [qdrant_adapter.py](file:///e:/repos/athenus/backend/app/infrastructure/adapters/qdrant_adapter.py)
- Update `search()` signature to accept `filter_workspace_id: Optional[str] = None` alongside `filter_media_id: Optional[str] = None`.
- Build a Qdrant `Filter` with `FieldCondition` rules:
  - Match `workspace_id == filter_workspace_id` when specified.
  - Match `media_id == filter_media_id` when specified.
  - Combine conditions using `Filter(must=[...])`.

---

### Retrieval Subsystem (`backend/app/infrastructure/retrieval/`)

#### [MODIFY] [multi_stage_retriever.py](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py)
- Pass `filter_workspace_id=workspace_id` and `filter_media_id=media_id` into `self.vector_store.search()`.
- Ensure candidate documents passed to `BM25Retriever` and `CrossEncoderReranker` respect workspace bounds.

---

### Verification & Test Suite (`backend/tests/`)

#### [NEW] [test_workspace_isolation.py](file:///e:/repos/athenus/backend/tests/test_workspace_isolation.py)
- Add isolated integration tests:
  - Upsert 5 chunks for `workspace_ml` ("Machine Learning / Gradient Descent").
  - Upsert 5 chunks for `workspace_history` ("Roman Empire / Julius Caesar").
  - Query `workspace_ml` for *"Who was Julius Caesar?"* $\rightarrow$ assert **0 hits** returned from Roman Empire.
  - Query `workspace_history` for *"What is backpropagation?"* $\rightarrow$ assert **0 hits** returned from Machine Learning.

---

## Verification Plan

### Automated Tests
1. **Workspace Isolation Pytest**:
   ```bash
   cd backend
   python -m pytest tests/test_workspace_isolation.py
   python -m pytest
   ```
2. **Frontend Type Check**:
   ```bash
   cd frontend
   npx tsc --noEmit
   ```

### Manual Verification
1. Create Workspace A ("Machine Learning") and upload a CS video.
2. Create Workspace B ("History") and upload a History video.
3. Switch to Workspace B, open Chat, and ask a question about Machine Learning.
4. Verify that 0 citations or context passages from Workspace A are retrieved or returned in the citations panel.
