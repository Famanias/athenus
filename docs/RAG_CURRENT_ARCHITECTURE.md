# Document 1 — Current RAG Architecture (Athenus)

> **Status**: Verified against source code as of 2026-08-10 (branch `restore-frontend-ingestion`).
> This document describes **what is actually implemented**, not what previous plans/ADRs describe.
> Where the code diverges from an ADR, the code is authoritative and the divergence is noted.

---

## 0. Executive Summary

Athenus's RAG system is **event-driven**, not a single linear pipeline module. A file upload kicks
off a chain of asynchronous workers (parse → OCR → chunk → embed → index → graph-extract), and a chat
query runs an 8-stage retrieval pipeline before the LLM call.

Everything is **local-first**. There are three stores:

| Store | Location | Holds |
|---|---|---|
| Local filesystem | `./data/uploads/` | Original binary files (PDFs, videos, audio) |
| SQLite (embedded) | `./data/athenus.db` | All structured metadata, chunk text, chat history, knowledge graph, jobs |
| Embedded Qdrant (on disk) | `./data/qdrant/` | 384-dim chunk embeddings (collection `transcript_chunks`) |

> **Important**: There is **no PostgreSQL** in the code. Earlier ADRs discuss a future
> cloud-mode PostgreSQL target, but the running system uses SQLite exclusively. There are also
> **no Alembic migrations** — schema is created at boot via `SQLModel.metadata.create_all()` plus
> ad-hoc `ALTER TABLE` statements.

---

## 1. Storage Layer

### 1.1 Where the original PDF binary lives

- On the **local filesystem** at `./data/uploads/{media_id}_{original_filename}`.
- Written directly by `POST /api/v1/media/upload` (`backend/app/presentation/api/v1/media.py`).
- The file is treated as **immutable** (write-once, never modified by ingestion).
- `media_id` scheme: documents get `doc_xxxxxxxx`, video/audio get `med_xxxxxxxx`
  (8 hex chars from `uuid4`). The `doc_`/`med_` prefix is the primary way code distinguishes
  documents from media.

### 1.2 How metadata is stored

- SQLite table **`media_items`** (ORM: `MediaItemTable`), one row per uploaded file.
- Key columns: `id` (`doc_…`/`med_…`), `workspace_id`, `title`, `file_path` (absolute path to the
  binary), `media_type` (`video`/`audio`/`document`), `file_size_bytes`, `duration_seconds`,
  `status`, `error_message`, timestamps.
- `media_id` is the **association key** between the binary file, its metadata, its chunks, its
  vectors, and any derived artifacts. There is no separate "document/media ID" — the same ID
  serves both roles.

### 1.3 Original vs. processed representation

- **Yes, they are stored separately.**
  - Original binary → filesystem (`./data/uploads/`), never mutated.
  - Parsed/processed text → SQLite **`transcript_chunks`** table **and** Qdrant vectors.
- **Notable**: The raw parsed markdown produced by AnyDoc is **never persisted**. It exists only
  transiently in the in-memory `DocumentParsedEvent` payload. Only the per-page chunks survive.

### 1.4 Where processed text/pages are stored

- SQLite table **`transcript_chunks`** (ORM: `TranscriptChunkTable`), shared by both documents and video:
  | Column | Meaning for video | Meaning for documents |
  |---|---|---|
  | `id` | `{media_id}_chunk_{index}` | `{document_id}_chunk_{index}` |
  | `media_id` | media ID | document ID |
  | `workspace_id` | workspace | workspace |
  | `text` | ~250-word transcript chunk | **one full page of text** |
  | `start_time` / `end_time` | timestamp range (sec) | **page number as a float** (both = page) |
  | `chunk_index` | index | index |
  | `word_count` | words | words |
- A legacy table **`document_pages`** exists on disk but has **no ORM model** and is not read/written
  by current code — an orphan from an earlier ingestion version.
- Raw ASR segments live in **`transcript_segments`** (video only; empty for documents).

### 1.5 Where embeddings are stored

Two distinct embedding stores:

1. **Qdrant** (chunk-level, for RAG retrieval):
   - Embedded (local) Qdrant on disk at `./data/qdrant/`, collection **`transcript_chunks`**.
   - Vector size **384**, distance **COSINE** (hardcoded to match `BAAI/bge-small-en-v1.5`).
   - Point ID = `uuid5(NAMESPACE_URL, chunk_id)` — deterministic, so re-ingestion overwrites.
   - Document payload: `chunk_id, media_id, document_id, workspace_id, source_type:"pdf", text,
     page_number, section_title, location{type:document, page, section, page_type, bbox}, chunk_index`.
   - Video payload: `chunk_id, media_id, workspace_id, text, start_time, end_time, chunk_index` —
     **note: no `source_type` field** for video. Downstream code detects documents by the presence of
     `page_number`/`location.type == "document"` rather than `source_type` alone.
2. **SQLite `knowledge_concepts.embedding`** (concept-level, for dedup only):
   - JSON-encoded 384-dim vector stored as TEXT; used by `ConceptMergingService` for cosine-similarity
     dedup of extracted graph concepts (threshold 0.88). **Not** used for retrieval.

### 1.6 Database tables (relevant subset of 22)

| Table | Purpose |
|---|---|
| `workspaces` | Workspace container |
| `media_items` | Uploaded files (docs, video, audio) |
| `transcript_segments` | Raw ASR segments (video) |
| `transcript_chunks` | Canonical chunk text (docs + video), also mirrored to Qdrant |
| `processing_logs` | Append-only pipeline audit trail (progress/errors) |
| `artifact_jobs` | Persistent ingestion queue + graph job lifecycle |
| `knowledge_concepts` | Extracted concepts (+ embedding JSON for dedup) |
| `knowledge_relations` | Extracted concept relations (triples) |
| `concept_aliases` | Concept name dedup aliases |
| `chat_sessions` / `chat_messages` | Chat history (persisted for display, **not** used at generation time) |
| `flashcard_decks` / `flashcards` / `flashcard_reviews` | Flashcards (SM-2) |
| `quizzes` / `quiz_questions` / `quiz_attempts` | Quizzes |
| `workspace_analytics` / `concept_mastery` / `study_sessions` | Analytics |

There are **no foreign-key constraints** — referential integrity is enforced at the application layer.

---

## 2. Ingestion Pipeline (what actually happens after upload)

```
POST /api/v1/media/upload
  → file written to ./data/uploads/{media_id}_{filename}
  → MediaItem row in SQLite
  → PersistentIngestionWorker.enqueue_media()  (artifact_jobs row)
      → process_next_job() → DocumentUploadedEvent
          → DocumentWorker.handle_document_uploaded()
              → AnyDocDocumentParsingAdapter.parse_document()   (text + page split)
              → RapidOCROCRAdapter.perform_ocr()                 (scanned/empty pages only)
              → DocumentParsedEvent
                  → EmbeddingWorker.handle_document_parsed()
                      → SemanticChunker.chunk_document_pages()   (1 unit per page)
                      → SentenceTransformersEmbeddingAdapter.embed_texts()
                      → _persist_document_units() → SQLite transcript_chunks
                      → EmbeddedQdrantVectorStoreAdapter.upsert() → Qdrant "transcript_chunks"
                      → ChunksIndexedEvent
                          → media status = COMPLETED
                          → GraphExtractionWorker → knowledge concepts + relations
                              → ConceptGraphUpdatedEvent → ingestion job = completed
```

### 2.1 Upload & registration (`media.py`)
- Extension classification: `.pdf/.docx/.pptx/.xlsx/.epub/.md/.txt` → document; `.mp3/.wav/…` → audio; else video.
- 100 MB hard limit for documents (413 + file deleted if exceeded).
- Enqueues into the persistent worker; if the worker isn't initialized, falls back to publishing the
  event directly via FastAPI `BackgroundTasks`.

### 2.2 Persistent ingestion queue (`persistent_ingestion_queue.py`)
- SQLite `artifact_jobs` is the source of truth; `id = "ingestion_{media_id}"`.
- Single-threaded sequential processing guarded by an `asyncio.Lock`.
- `boot_recovery()` re-queues stranded `queued`/`reserved`/`processing` jobs on startup.
- **Gotcha**: the job is marked `completed` only after `ConceptGraphUpdatedEvent` (i.e., after
  knowledge-graph extraction), **not** after vector indexing. Media status becomes `COMPLETED` at
  `ChunksIndexedEvent` — so there is a window where the media is "completed" but the job still shows
  processing.

### 2.3 Document parsing — AnyDoc (`anydoc_adapter.py`)
- Runs `anydoc.to_markdown(file_path)` **in a thread executor** (optional dependency — silently
  degrades to a plain-text fallback if `anydoc` is not installed; it is **not** in `requirements.txt`).
- Page identification: split markdown on `<!-- pagebreak -->`; if that yields one page, fall back to
  splitting on `\n\n---\n\n`.
- Limits: `max_pages = 200`, `max_file_size_mb = 100`, plus a zip-bomb guard (ratio >100:1 AND
  uncompressed >50 MB) for zip containers.
- Scanned-page detection is a **heuristic** (`len(clean_text) < 20` AND an image/scanned marker) — the
  ADR's `pdf-inspector` classifier is **not** implemented.
- Produces one `DocumentPageDTO` per page: `page_number`, `text`, `page_type`, `section_title = "Page N"`.

### 2.4 OCR — RapidOCR (`ocr_adapter.py`)
- Runs **only** for pages flagged `scanned` or blank (inside the heavy-ML semaphore).
- Local ONNX Runtime inference (`rapidocr_onnxruntime`, also optional / not in requirements).
- Fallback mode fabricates `"[OCR Extracted Text from {filename} page {page_number}]"` (dev/test only).
- **Scheduler note**: ADR0021 specifies `Semaphore=1` for the heavy-ML path, but the code instantiates
  `WorkloadScheduler()` with its default `Semaphore(2)`.

### 2.5 Chunking (`chunker.py`)
- **Documents: one chunk per page.** `chunk_document_pages()` creates a `SourceContentUnit` for every
  non-empty page, with `location = {type:"document", page, section, page_type, bbox:None}`. The
  `target_word_count=250` / `min_word_count=50` constructor params are **not** applied to documents —
  a 5,000-word page becomes one 5,000-word chunk.
- **Video: semantic windows.** `chunk_transcript()` groups ASR segments until ~250 words, preserving
  `start_time`/`end_time`.

### 2.6 Embedding (`sentence_transformers_adapter.py`)
- Model: `BAAI/bge-small-en-v1.5`, **384-dim**. Lazy-loaded; runs in an executor.
- **Mock fallback**: if the package is missing, returns a deterministic pseudo-vector
  `[0.01, 0.02, …, 3.84]` — search then returns meaningless cosine similarities. This silently
  degrades retrieval quality in any environment without the model installed.

### 2.7 Vector storage & SQLite persistence (`embedding_worker.py`)
- Chunk text persisted to `transcript_chunks` (best-effort; exceptions silently swallowed).
- Qdrant upsert with the payloads described in §1.5.
- Emits `ChunksIndexedEvent` → media status `COMPLETED`.

### 2.8 Knowledge graph extraction (`graph_extraction_worker.py`, `knowledge_graph_service.py`)
- Subscribes to `ChunksIndexedEvent`; loads chunk text from SQLite; runs LLM concept extraction
  (with a deterministic heuristic fallback); merges duplicates via exact/alias/embedding-cosine
  (threshold 0.88); writes `knowledge_concepts`, `knowledge_relations`, `concept_aliases`.
- Publishes `ConceptGraphUpdatedEvent` when done. **Relations accumulate per workspace and are
  unbounded.**

---

## 3. Query & Retrieval Pipeline

```
User query
  ↓  POST /api/v1/chat/query  (chat.py)
  ↓  WorkspaceIntelligenceManager.query_workspace  (workspace_intelligence.py)
  ↓  MultiStageRetriever.execute_retrieval  (multi_stage_retriever.py)
  │     Stage 1  Query "rewrite"        (cosmetic string append)
  │     Stage 2-3 Active context        (document page header OR ±30s video window)
  │     Stage 4  KG triples             (ALL relations in the workspace — unbounded)
  │     Stage 5  Hybrid search          (Qdrant dense top-10 → BM25 top-5)
  │     Stage 6  "Cross-encoder" rerank (keyword-overlap heuristic → top-3)
  │     Stage 7  Context "compression"  (badge + full chunk text — no truncation)
  │     Stage 8  Prompt assembly        (single string; no separate system prompt)
  ↓  TextGenerationRequest(prompt, temperature=0.3)
  ↓  Active LLM adapter → Groq / OpenRouter / OpenAI / Ollama / Anthropic
  ↓  answer + backend-built citations
```

### 3.1 Endpoint & request shape (`chat.py`)
`POST /api/v1/chat/query` accepts: `query`, `workspace_id` (default `"default"`), `session_id`,
`media_id`, `document_id`, `source_type`, `current_timestamp`, `current_page`, `selected_text`.
All are passed straight through to the manager.

### 3.2 Orchestrator (`workspace_intelligence.py`)
1. Runs retrieval → `RetrievalContext`.
2. Gets the active text provider and calls it with `TextGenerationRequest(prompt=assembled_prompt,
   temperature=0.3)`. `system_prompt` is left `None`; `max_tokens` stays at the dataclass default **1024**.
3. Appends the turn to an in-process `MemoryManager` (never read again — see §3.12).
4. Builds structured citations from the retrieved chunks and returns them.

### 3.3 Stage-by-stage

**Stage 1 — Query "rewrite"**: `rewritten_query = f"{query} (Context: educational materials breakdown)"`.
This is a cosmetic append. No query expansion, no rewriting LLM call.

**Stages 2–3 — Active context** (injected into the prompt, but **not** used to filter search):
- PDF path (`source_type == "pdf"` or `document_id` present, and `current_page` not None):
  builds a short header with the document ID, "Page N", and any selected text. It does **not** fetch
  the page's content.
- Video path (`media_id` + `current_timestamp`): queries `transcript_segments` for a **±30 s window**
  around the playback timestamp, formats `[MM:SS] text` lines, records provenance.

**Stage 4 — Knowledge graph**: `get_workspace_triples(workspace_id)` returns **every** `knowledge_relations`
row in the workspace, formatted `source --[relation]--> target`. No limit, no query relevance filter.

**Stage 5 — Hybrid search**:
- Query embedding via the same sentence-transformers adapter (`embed_query`).
- **Dense**: `vector_store.search(query_vector, limit=10, filter_workspace_id=workspace_id)`.
  - Only the workspace is filtered — **not** `media_id`/`document_id`/`source_type`. Retrieval is
    workspace-wide by design.
  - **No `score_threshold`** is passed. Every one of the top-10 is accepted regardless of cosine score.
  - Fallback path (no Qdrant client) returns hardcoded `score: 0.85` for every hit.
- **Sparse (BM25)**: `bm25_retriever.rank(rewritten_query, dense_docs, top_k=5)` — runs **over the 10
  dense hits only**, not the corpus. So a chunk absent from the dense top-10 can never surface.

**Stage 6 — "Cross-encoder" reranking** (`reranker.py`): despite the name, this is a **keyword-overlap
heuristic**, not a neural cross-encoder:
```
final_rerank_score = (Qdrant cosine * 0.4) + (bm25_score * 0.3) + (query–chunk token overlap * 0.3)
```
Sorts descending, keeps **top 3**. Final retrieved chunk count = 3.

**Stage 7 — Context "compression"** (`_compress_context`): no compression occurs. Each chunk is prefixed
with a badge (`[Document Page N (section)]` or `[MM:SS - MM:SS]`) and its **entire raw text** is appended,
joined with blank lines. A multi-thousand-word page passes through verbatim.

**Stage 8 — Prompt assembly** (`_assemble_prompt`): two single-string variants (no separate system message):
- **No context** (no chunks, no active context, no KG triples): general-knowledge instruction that
  explicitly forbids fabricating citations.
- **Grounded**: an instruction block telling the model to answer using **ONLY** the provided context and
  to **always include traceable citations**, followed by `active_context`, `Context:`, all KG triples,
  then `User Question:` / `Answer:`.

### 3.4 The LLM call

- Active provider resolved from persisted settings (`default_llm`) → falls back to env `LLM_PROVIDER`
  (default `"ollama"`). Model resolved from per-provider settings, else default
  (Groq: `llama-3.3-70b-versatile`; Ollama: `llama3:8b`; OpenRouter: `google/gemini-2.5-flash`).
- `system_prompt` is never set by the chat path, so each adapter substitutes its own default
  (`"You are Athenus AI Assistant."`, or empty for Ollama).
- Adapters send **exactly two messages**: system + the entire assembled prompt as one `user` message.
- Parameters: `temperature=0.3`, `max_tokens=1024`, no stop sequences.
- **No conversation history** is included at generation time. `MemoryManager` appends turns but nothing
  ever reads them; chat history is persisted to SQLite only for the frontend's `GET /chat/history`.

---

## 4. Citations

There are **two independent citation channels**, and it is important to keep them separate:

### 4.1 Structured citations — built by the backend from retrieval metadata (the "📄 Page 176" badges)

- `WorkspaceIntelligenceManager.query_workspace` builds a citation object for **each of the top-3
  retrieved chunks** from their Qdrant payload: `chunk_id`, `source_type`, `page_number`,
  `section_title`, `location`, `text`, timestamps.
- `chat.py` serializes these into `CitationDTO`s and returns them in the API response.
- The frontend (`ChatMessageItem.tsx`) renders them as clickable badges:
  - Document: `📄 Page {page_number} ({section_title})`
  - Video: `⏱ {start} - {end}`
- **How "📄 Page 176" is connected to the source**: `page_number` is read from the **retrieved chunk's
  Qdrant payload**, which was populated at ingestion from the real page number. So the badge's page
  number is *real metadata from an actual chunk* — **provided the chunk was genuinely retrieved**.
- **Caveat**: because there is no relevance threshold, the citation list is simply the top-3 chunks.
  A chunk that is irrelevant to the answer still appears as a citation. And the same chunk list is
  shown to the user regardless of whether the LLM actually used it.

### 4.2 Inline badges — written by the LLM, **unvalidated**

- The grounded prompt instructs the LLM to *also* write inline citations such as
  `[Document Page X]` / `[MM:SS]` inside its answer text.
- A parser exists (`backend/app/domain/knowledge/citation_parser.py`,
  `parse_chat_citations`) with regexes for `[Document Page X]`, `[Page X]`, `[MM:SS]`, etc., but it is
  **referenced only by tests and docs — it is not wired into the runtime path.** Nothing validates,
  parses, or filters the inline badges the model emits.

### 4.3 Can the LLM invent citation metadata?

- **In the structured citation list (the UI badges): No.** The backend constructs those from retrieved
  chunk metadata; the LLM's output doesn't influence them.
- **In its own prose: Yes.** Nothing stops `llama-3.3-70b-versatile` from writing
  `[Document Page 999]` or `[12:34 - 12:56]` in the answer text, and the system does not check those
  against retrieved chunks. The "don't invent citations" safeguard exists **only** in the no-context
  prompt variant; the grounded variant actively *asks* for citations, which can encourage the model to
  produce them even when the supporting evidence is weak.

---

## 5. End-to-End Trace — "Who are the authors?"

1. Frontend calls `POST /api/v1/chat/query` with `{query: "Who are the authors?", workspace_id,
   session_id, and optionally document_id/source_type/current_page}`.
2. `MultiStageRetriever`:
   - Rewrites to `"Who are the authors? (Context: educational materials breakdown)"`.
   - If a PDF is active with `current_page=176`, builds an active-context header mentioning
     `Page 176` (but fetches no page text).
   - Loads **all** workspace knowledge-graph triples.
   - Embeds the rewritten query → Qdrant search (top 10, workspace filter only, no score threshold).
   - BM25 over those 10 → top 5; keyword-overlap heuristic → top 3.
   - Formats the 3 chunks with page/timestamp badges (full text, untruncated).
   - Assembles the grounded prompt (instruction block + active context + 3 chunks + all triples).
3. `WorkspaceIntelligenceManager` calls the active LLM adapter with `temperature=0.3`, `max_tokens=1024`.
4. The adapter sends `[system: "You are Athenus AI Assistant."]`, `[user: <assembled prompt>]`.
5. The model's text is returned as `answer`; the top-3 chunks are returned as structured citations;
   the frontend renders `📄 Page 176` style badges from them.

---

## 6. File & Component Map

| Concern | File |
|---|---|
| Upload + file write | `backend/app/presentation/api/v1/media.py` |
| Config (paths, limits, models) | `backend/app/core/config.py` |
| All ORM models (SQLite) | `backend/app/infrastructure/db/models.py` |
| DB engine/session | `backend/app/infrastructure/db/session.py` |
| Persistent ingestion queue | `backend/app/domain/ingestion/persistent_ingestion_queue.py` |
| Document parse worker | `backend/app/services/workers/document_worker.py` |
| Embedding/index worker | `backend/app/services/workers/embedding_worker.py` |
| Graph extraction worker | `backend/app/services/workers/graph_extraction_worker.py` |
| AnyDoc adapter | `backend/app/infrastructure/adapters/anydoc_adapter.py` |
| RapidOCR adapter | `backend/app/infrastructure/adapters/ocr_adapter.py` |
| Chunking | `backend/app/domain/knowledge/chunker.py` |
| Embedding adapter | `backend/app/infrastructure/adapters/sentence_transformers_adapter.py` |
| Qdrant adapter | `backend/app/infrastructure/adapters/qdrant_adapter.py` |
| BM25 | `backend/app/domain/knowledge/bm25_retriever.py` |
| "Cross-encoder" reranker | `backend/app/domain/knowledge/reranker.py` |
| Knowledge graph service | `backend/app/domain/knowledge/knowledge_graph_service.py` |
| Concept merging | `backend/app/domain/knowledge/concept_merging.py` |
| Retrieval orchestration | `backend/app/infrastructure/retrieval/multi_stage_retriever.py` |
| Query orchestrator | `backend/app/application/services/workspace_intelligence.py` |
| Chat endpoint | `backend/app/presentation/api/v1/chat.py` |
| OpenAI-compatible adapter (Groq/OpenRouter/OpenAI) | `backend/app/infrastructure/adapters/openai_compatible_adapter.py` |
| Ollama adapter | `backend/app/infrastructure/adapters/ollama_adapter.py` |
| Anthropic adapter | `backend/app/infrastructure/adapters/anthropic_adapter.py` |
| Citation DTOs | `backend/app/presentation/api/v1/chat.py` |
| Inline citation parser (**not wired**) | `backend/app/domain/knowledge/citation_parser.py` |
| Chat service (frontend) | `frontend/src/services/chatService.ts` |
| Citation badge rendering (frontend) | `frontend/src/features/chat/ChatMessageItem.tsx` |

---

## 7. Observed Weaknesses (cross-reference to Part 2/3)

These are the code-level facts that the reliability analysis in
`RAG_RELIABILITY_REMEDIATION_PLAN.md` builds on:

1. **No relevance threshold** anywhere in the query path — every top-10 hit is accepted, top-3 survive
   via a keyword-overlap heuristic.
2. **"Cross-encoder" reranker is not a model** — a weighted token-overlap formula.
3. **BM25 only sees the dense top-10** — good keyword matches outside that set are unreachable.
4. **Query "rewrite" is cosmetic** — no real query understanding.
5. **Documents are chunked one page per chunk** — pages can be thousands of words, harming both
   retrieval precision and context size.
6. **No context-size guards** — no token counting, no truncation, no compression, no pre-flight check
   before sending to the LLM.
7. **Knowledge-graph triples are injected unbounded** — every relation in the workspace goes into every
   grounded prompt.
8. **Conversation history is never used at generation time** (each turn answered in isolation).
9. **Grounded prompt is hard "ONLY context"** with no insufficiency/fallback instruction and no
   "answer directly" instruction — the model is pushed to keep searching context it cannot find.
10. **Structured citations are the top-3 chunks unconditionally**; inline LLM citations are unvalidated.
