# MEMORY_ARCHITECTURE.md — Athenus Knowledge OS Structured Memory Architecture

Comprehensive specification of the 4-layer memory model, persistent chat sessions, workspace isolation, and Knowledge Graph concept storage.

---

## 1. Overview & 4-Layer Memory Model

Athenus Knowledge OS separates **Knowledge Storage** from **User Conversational & Conceptual Memory** across 4 memory tiers:

```text
 ┌─────────────────────────────────────────────────────────────┐
 │                      4-Layer Memory Model                   │
 │                                                             │
 │  ┌──────────────────────┐       ┌──────────────────────┐    │
 │  │ 1. Short-Term Memory │       │  2. Working Memory   │    │
 │  │ (Zustand UI State)   │       │(Workspace Filter RAG)│    │
 │  └──────────────────────┘       └──────────────────────┘    │
 │                                                             │
 │  ┌──────────────────────┐       ┌──────────────────────┐    │
 │  │ 3. Long-Term Memory  │       │ 4. Semantic Memory   │    │
 │  │ (SQLite Chat/Logs)   │       │(Knowledge Graph DB)  │    │
 │  └──────────────────────┘       └──────────────────────┘    │
 └─────────────────────────────────────────────────────────────┘
```

---

## 2. Memory Tier Specifications

### Tier 1: Short-Term Memory (Zustand UI State)
* **Lifetime**: Application session RAM.
* **Component**: Frontend `chatSlice.ts` store.
* **Function**: Maintains active conversation turn UI state during view tab switches, preventing UI thread clearing.

### Tier 2: Working Memory (Workspace Filter RAG)
* **Lifetime**: Query execution window.
* **Components**: `MultiStageRetriever` & `EmbeddedQdrantVectorStoreAdapter`.
* **Function**: Scopes vector embedding search strictly to `workspace_id` and optional `media_id` filters, preventing cross-workspace context leakage.

### Tier 3: Long-Term Memory (SQLite Relational Persistence)
* **Lifetime**: Persistent on disk (`./data/athenus.db`).
* **Tables**: `chat_sessions`, `chat_messages`, `processing_logs`.
* **Function**: Stores turn-by-turn chat history (user prompts, assistant responses, citations) and pipeline execution audit logs across backend and desktop app restarts. REST endpoints `GET /chat/history` and `DELETE /chat/history` manage lifecycle.

### Tier 4: Semantic Memory (Persistent Knowledge Graph)
* **Lifetime**: Persistent on disk (`./data/athenus.db`).
* **Tables**: `knowledge_concepts`, `knowledge_relations`.
* **Function**: Stores extracted domain concept nodes and directional relationship triples (`source_concept`, `target_concept`, `relation_type`). In Stage 4 of `MultiStageRetriever`, graph triples are traversed and injected directly into RAG prompts.
