# Implementation Plan — Phase 4: Persistent Conversational Memory & Knowledge Graph Integration

Integrate long-term persistent knowledge graph concept nodes, relationship triples, and conversation deletion memory directly into SQLite and the multi-stage RAG retrieval pipeline.

---

## User Review Required

> [!IMPORTANT]
> **Key Architecture Decisions for Phase 4:**
> 1. **Persistent Knowledge Graph Schema (`KnowledgeConceptTable` & `KnowledgeRelationTable`)**: Store extracted domain entities, concept definitions, and relation triples in SQLite bound to `workspace_id`.
> 2. **RAG Stage 4 Graph Traversal Context Injection**: Update `MultiStageRetriever` to traverse relevant knowledge graph triples and expand the RAG prompt context with structured concept relationships.
> 3. **Chat Deletion API Endpoint (`DELETE /api/v1/chat/history`)**: Provide explicit backend support to delete/clear chat history for a workspace in SQLite upon user action.
> 4. **Workflow Checkpoint**: Stop after Phase 4 verification and self-review to request user review before completing the mitigation roadmap.

---

## Proposed Changes

### Database Layer (`backend/app/infrastructure/db/`)

#### [MODIFY] [models.py](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py)
- **[NEW]** Add `KnowledgeConceptTable` SQLModel/SQLAlchemy class:
  - `id`: String PK
  - `workspace_id`: String (indexed)
  - `name`: String (indexed)
  - `description`: Optional text
- **[NEW]** Add `KnowledgeRelationTable` SQLModel/SQLAlchemy class:
  - `id`: String PK
  - `workspace_id`: String (indexed)
  - `source_concept`: String
  - `target_concept`: String
  - `relation_type`: String (e.g. `is_a`, `part_of`, `uses`, `prerequisite_for`)

---

### Knowledge Graph Repository (`backend/app/infrastructure/db/`)

#### [MODIFY] [sqlite_knowledge_graph.py](file:///e:/repos/athenus/backend/app/infrastructure/db/sqlite_knowledge_graph.py) or [knowledge_graph.py](file:///e:/repos/athenus/backend/app/domain/knowledge/knowledge_graph.py)
- Implement SQLite persistence methods for adding concepts, relations, and querying subgraphs by workspace ID.

---

### Retrieval Subsystem (`backend/app/infrastructure/retrieval/`)

#### [MODIFY] [multi_stage_retriever.py](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py)
- Enable **Stage 4 (Knowledge Graph Traversal)**:
  - Query persistent graph relations for concepts in `query`.
  - Append formatted knowledge triples into `ctx.assembled_prompt`.

---

### Presentation & API Layer (`backend/app/presentation/api/v1/`)

#### [MODIFY] [chat.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/chat.py)
- Add `DELETE /api/v1/chat/history` endpoint to clear active chat messages for a workspace in SQLite.

---

### Verification & Test Suite (`backend/tests/`)

#### [NEW] [test_knowledge_graph_memory.py](file:///e:/repos/athenus/backend/tests/test_knowledge_graph_memory.py)
- Add automated tests:
  - Concept/relation SQLite persistence.
  - Knowledge graph traversal prompt expansion.
  - Chat history deletion endpoint verification.

---

## Verification Plan

### Automated Tests
1. **Knowledge Graph & Memory Pytest**:
   ```bash
   cd backend
   python -m pytest tests/test_knowledge_graph_memory.py
   python -m pytest
   ```
2. **Frontend Type Check**:
   ```bash
   cd frontend
   npx tsc --noEmit
   ```

### Manual Verification
1. Open **Chat** (`view-chat`) and submit questions building domain concepts.
2. Click **Clear Chat** $\rightarrow$ call `DELETE http://localhost:8000/api/v1/chat/history?workspace_id=default`.
3. Verify chat history in SQLite is cleared and fresh conversation starts cleanly.
