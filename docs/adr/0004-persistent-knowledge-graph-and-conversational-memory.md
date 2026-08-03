# ADR 0004: Persistent Knowledge Graph & Conversational Memory Integration

* **Status**: Accepted & Implemented
* **Date**: 2026-08-03
* **Context**: Knowledge Graph concept nodes and relation edges were stored in an in-memory dictionary. Furthermore, chat history lacked explicit deletion endpoints.
* **Decision**:
  1. Store domain concepts and relationship triples in SQLite (`KnowledgeConceptTable` & `KnowledgeRelationTable`).
  2. Traverse workspace triples in Stage 4 of `MultiStageRetriever` and inject graph relationships into RAG prompts.
  3. Expose `DELETE /api/v1/chat/history` endpoint to clear active chat sessions in SQLite.
* **Alternatives Considered**:
  - *External Neo4j Graph DB*: Too heavy for offline local-first desktop app.
* **Rationale**: Storing triples in SQLite maintains the local-first zero-dependency goal while giving the LLM rich structured concept relationships alongside raw video transcript passages.
* **Trade-offs**: Graph traversal queries must be indexed by `workspace_id` to remain fast.
