# Document 1 — Current RAG Architecture (Athenus)

> **Status**: Verified against source code as of 2026-08-10 (branch `restore-frontend-ingestion`).
> This document describes **what is actually implemented** after the completion of the RAG Reliability Remediation Plan.

---

## 0. Executive Summary

Athenus's RAG system is an **event-driven, local-first RAG architecture**. A file upload kicks off a chain of asynchronous workers (parse → sub-chunk → embed → FTS5 index → graph-extract), and a chat query executes a high-precision multi-stage retrieval pipeline before LLM generation.

Everything is **local-first**. There are three primary stores:

| Store | Location | Holds |
|---|---|---|
| Local filesystem | `./data/uploads/` | Original binary files (PDFs, videos, audio) |
| SQLite (embedded) | `./data/athenus.db` | All structured metadata, ~500-word sub-chunks, chat history, knowledge graph, jobs, and `transcript_chunks_fts` FTS5 virtual table |
| Embedded Qdrant (on disk) | `./data/qdrant/` | 384-dim sub-chunk embeddings (collection `transcript_chunks`) |

---

## 1. Storage Layer

### 1.1 Original File Storage

- Stored on local filesystem at `./data/uploads/{media_id}_{original_filename}`.
- Written directly by `POST /api/v1/media/upload` (`backend/app/presentation/api/v1/media.py`).
- Treated as immutable.
- `media_id` format: documents receive `doc_xxxxxxxx`, video/audio receive `med_xxxxxxxx` (8 hex chars from `uuid4`).

### 1.2 Processed Sub-Chunks & FTS5 Virtual Table

- SQLite table **`transcript_chunks`** (ORM: `TranscriptChunkTable`):
  - Document pages are divided into **~500-word sub-chunks with a strict hard ceiling of $\le 750$ tokens** per chunk via `SemanticChunker.chunk_document_pages()`.
  - Sub-chunk IDs follow `{document_id}_chunk_{index}`.
  - Location payload preserves `page`, `section`, `sub_chunk_index`, and `total_sub_chunks`.
- SQLite virtual table **`transcript_chunks_fts`**:
  - Full-text search (FTS5) virtual table mirroring `transcript_chunks` (`chunk_id`, `workspace_id`, `text`).
  - Native SQLite database triggers (`transcript_chunks_ai`, `transcript_chunks_au`, `transcript_chunks_ad`) automatically synchronize all `INSERT`, `UPDATE`, and `DELETE` operations on `transcript_chunks` directly into `transcript_chunks_fts`.

### 1.3 Embeddings

- **Qdrant** (`transcript_chunks` collection):
  - Embedded Qdrant at `./data/qdrant/`, 384-dim vectors (`BAAI/bge-small-en-v1.5`), `COSINE` distance.
  - Deterministic Point ID: `uuid5(NAMESPACE_URL, chunk_id)`.
  - Supports `score_threshold = 0.2` filtering low-relevance noise.

---

## 2. Ingestion Pipeline

```
POST /api/v1/media/upload
  → File written to ./data/uploads/{media_id}_{filename}
  → MediaItem row created in SQLite
  → PersistentIngestionWorker.enqueue_media()  (artifact_jobs row)
      → process_next_job() → DocumentUploadedEvent
          → DocumentWorker.handle_document_uploaded()
              → AnyDocDocumentParsingAdapter.parse_document()   (Clean text + pypdf fallback)
              → RapidOCROCRAdapter.perform_ocr()                 (Scanned/empty pages only)
              → DocumentParsedEvent
                  → EmbeddingWorker.handle_document_parsed()
                      → SemanticChunker.chunk_document_pages()   (~500-word sub-chunks, ≤750 tokens)
                      → SentenceTransformersEmbeddingAdapter.embed_texts()
                      → SQLite transcript_chunks + FTS5 Trigger Mirroring
                      → EmbeddedQdrantVectorStoreAdapter.upsert() → Qdrant "transcript_chunks"
                      → ChunksIndexedEvent → Media status = COMPLETED
                          → GraphExtractionWorker → Knowledge concepts + relations
                              → ConceptGraphUpdatedEvent → Ingestion job = completed
```

### 2.1 Parsing & Sub-Chunking (`anydoc_adapter.py`, `chunker.py`)
- Clean text extraction with `pypdf` fallback filtering out PDF binary streams (`endstream`, `endobj`) and XMP metadata XML tags (`<x:xmpmeta>`).
- Supports large documents up to **2,000 pages** and 100 MB file size limit.
- Sub-chunking in `SemanticChunker.chunk_document_pages()` splits multi-thousand-word pages into ~500-word sub-chunks, strictly enforcing `count_tokens(text) <= 750`.

### 2.2 Persistent Queue & Legacy Migration (`persistent_ingestion_queue.py`)
- Single-threaded sequential worker under `_lock` (`asyncio.Lock`).
- `boot_recovery()` runs `_backfill_fts5()` to backfill missing FTS5 entries and `_enqueue_legacy_rechunk_jobs()` to migrate legacy whole-page PDF documents (`media_type == 'document'`) into ~500-word sub-chunks.

---

## 3. Query & Multi-Stage Retrieval Pipeline

```
User query
  ↓  POST /api/v1/chat/query
  ↓  WorkspaceIntelligenceManager.query_workspace
  ↓  MultiStageRetriever.execute_retrieval
  │     Stage 1  Query Tokenization
  │     Stage 2-3 Active Context        (Full page text concatenation OR ±30s video window)
  │     Stage 4  KG Triples             (Zero-Match KG Guardrail — keyword matching)
  │     Stage 5  Hybrid Search          (Qdrant dense + 1.5x active boost + FTS5 BM25 + RRF k=60)
  │     Stage 6  Cross-Encoder Rerank   (Top candidates reranked)
  │     Stage 7  Token Budget Check     (Input tokens + 2,048 reserved output <= context limit)
  │     Stage 8  Prompt Presentation    (Presentation order: bm25*0.7 + cosine*0.3 + direct answer prompt)
  ↓  Active LLM adapter (Groq / Anthropic / OpenAI / Ollama)
  ↓  Response generation + deduplicated structured citations
```

### 3.1 Key RAG Pipeline Innovations
1. **Active-Item Context Score Boosting**: Dense vector hits matching the active `document_id` or `media_id` receive a **1.5x score multiplier**, prioritizing active viewer materials.
2. **SQLite FTS5 Full-Corpus BM25 Search**: `BM25Retriever.search_fts5()` executes native FTS5 queries across the full workspace corpus.
3. **Reciprocal Rank Fusion (RRF, $k=60$)**: Combines dense vector hits and sparse BM25 hits using $\text{RRF}(c) = \frac{1}{60 + \text{rank}_{\text{dense}}} + \frac{1}{60 + \text{rank}_{\text{sparse}}}$, deduplicating by `chunk_id` and capping candidates at top $N=15$.
4. **Dense Vector Score Thresholding**: `EmbeddedQdrantVectorStoreAdapter.search(score_threshold=0.2)` filters out low-relevance vector noise.
5. **Zero-Match Knowledge Graph Guardrail**: `KnowledgeGraphService.get_workspace_triples()` filters triples against query concept keywords; returns `[]` when zero concepts match, keeping prompts clean.
6. **Active Document Page Concatenation**: `_extract_document_page_context()` queries SQLite `transcript_chunks` for `start_time <= current_page <= end_time`, joining all page sub-chunks in `chunk_index ASC` order with double newlines.
7. **Token Budget Enforcement & Output Capacity**: Guarantees $\text{reserved\_output\_tokens} = 2,048$ output generation tokens by measuring prompt input tokens against model context limits (`model_context_limit`).
8. **Conversational Grounding & Citation Suppression**: Internal context state `has_relevant_context` is separated from user presentation. Generic greetings or unsupported queries receive natural friendly responses while suppressing spurious citations.

---

## 4. File & Component Map

| Component | File |
|---|---|
| Persistent Queue & Migration | [`backend/app/domain/ingestion/persistent_ingestion_queue.py`](file:///e:/repos/athenus/backend/app/domain/ingestion/persistent_ingestion_queue.py) |
| Document Parsing | [`backend/app/infrastructure/adapters/anydoc_adapter.py`](file:///e:/repos/athenus/backend/app/infrastructure/adapters/anydoc_adapter.py) |
| Sub-Chunking Engine | [`backend/app/domain/knowledge/chunker.py`](file:///e:/repos/athenus/backend/app/domain/knowledge/chunker.py) |
| FTS5 DB Triggers & Session | [`backend/app/infrastructure/db/session.py`](file:///e:/repos/athenus/backend/app/infrastructure/db/session.py) |
| FTS5 BM25 Retriever | [`backend/app/domain/knowledge/bm25_retriever.py`](file:///e:/repos/athenus/backend/app/domain/knowledge/bm25_retriever.py) |
| Qdrant Vector Adapter | [`backend/app/infrastructure/adapters/qdrant_adapter.py`](file:///e:/repos/athenus/backend/app/infrastructure/adapters/qdrant_adapter.py) |
| Multi-Stage RAG Retriever | [`backend/app/infrastructure/retrieval/multi_stage_retriever.py`](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py) |
| Intelligence Manager | [`backend/app/application/services/workspace_intelligence.py`](file:///e:/repos/athenus/backend/app/application/services/workspace_intelligence.py) |
| Telemetry & Audit Service | [`backend/app/domain/telemetry/telemetry_service.py`](file:///e:/repos/athenus/backend/app/domain/telemetry/telemetry_service.py) |
