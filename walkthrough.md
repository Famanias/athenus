# Athenus RAG Reliability Remediation — Walkthrough & Verification Record

Canonical chronological record of implementation, automated testing, and manual QA validation for all remediation phases.

---

# Milestone 1 — Document Ingestion & Chunking Integrity

## Phase 1.1 — Sub-Chunking (~500 words, ≤750 token ceiling) & Clean PDF Text Extraction

### Phase Summary
Implemented document page sub-chunking with ~500-word target blocks and a strict hard maximum token ceiling of ≤750 tokens per chunk. Upgraded PDF fallback document parsing using `pypdf` to extract clean page-by-page text while filtering out raw PDF stream objects (`endstream`, `endobj`) and embedded XMP metadata XML tags.

### What Was Implemented
- Sub-chunking algorithm in `SemanticChunker.chunk_document_pages()` splitting multi-thousand-word pages into ~500-word sub-chunks while strictly enforcing `count_tokens(chunk.text) <= 750`.
- Token counter (`count_tokens()`) supporting `tiktoken` encoding with fallback character-ratio calculation.
- Clean PDF text extraction in `AnyDocDocumentParsingAdapter._parse_with_fallback()` using `pypdf.PdfReader` with XMP metadata (`<x:xmpmeta>`, `<rdf:RDF>`, `xapGImg:image`) and PDF binary stream filtering.
- Location metadata preservation (`page`, `section`, `sub_chunk_index`, `total_sub_chunks`) across all sub-chunks.

### Root Cause Addressed
- Previously, single pages were treated as giant 5,000+ word chunks (~7,500 tokens), causing retrieval chunk truncation and context dilution.
- Plain-text fallback reading opened binary `.pdf` files as text strings, indexing raw binary PDF syntax (`endstream`, `endobj`, base64 image thumbnails) into Qdrant/SQLite, which corrupted LLM prompt contexts and broke response generation.

### Files/Components Changed
- [`backend/app/domain/knowledge/chunker.py`](file:///e:/repos/athenus/backend/app/domain/knowledge/chunker.py): Added `count_tokens()`, `split_text_into_subchunks()`, and updated `chunk_document_pages()`.
- [`backend/app/infrastructure/adapters/anydoc_adapter.py`](file:///e:/repos/athenus/backend/app/infrastructure/adapters/anydoc_adapter.py): Integrated `pypdf` text extraction and XMP/PDF stream sanitization.
- [`backend/requirements.txt`](file:///e:/repos/athenus/backend/requirements.txt): Added `pypdf>=4.0.0`.
- [`backend/tests/test_chunker_generalization.py`](file:///e:/repos/athenus/backend/tests/test_chunker_generalization.py): Added `test_chunk_document_pages_token_ceiling`.

### Important Implementation Decisions
- Enforced hard ≤750 token limit per chunk directly at the chunker boundary rather than relying on LLM prompt truncation.
- Retained deterministic chunk ID scheme `{document_id}_chunk_{chunk_idx}` to ensure Qdrant upserts overwrite cleanly on re-ingestion.

### Automated Tests Performed and Results
- `python -m pytest tests/test_chunker_generalization.py`: **Passed (3/3 passed)** in 8.36s.
- `python -m pytest tests/test_anydoc_adapter.py`: **Passed (5/5 passed)** in 0.14s.
- `npx tsc --noEmit` (Frontend): **Passed (0 errors)**.

### Manual QA Validation
| Test | How to Conduct | Expected Behavior |
| :--- | :--- | :--- |
| **Document Sub-Chunking & Token Ceiling** | 1. Upload a PDF with multi-thousand-word pages.<br>2. Inspect SQLite `transcript_chunks` for `media_id`. | Pages are split into multiple sub-chunks, each with `word_count <= ~500` and `tokens <= 750`. |
| **Clean PDF Text Parsing** | 1. Upload a PDF containing vector graphics/XMP metadata (e.g. `AI.pdf`).<br>2. Ask chat: *"Give me a single sentence summary of the PDF."* | Answer is clean without `endstream`, `endobj`, or base64 image tags. Citations show distinct page numbers (`📄 Page 1`, `📄 Page 2`). |

### Validation Status
- **PASSED & VALIDATED BY USER** (Explicit manual QA approval received).

---

## Phase 1.2 — Knowledge Graph Triple Relevance Filtering & Zero-Match Guard

### Phase Summary
Implemented query relevance keyword/concept matching in `KnowledgeGraphService.get_workspace_triples()` and enforced the **Zero-Match KG Guardrail**. Unrelated queries or generic greetings will no longer inject arbitrary knowledge graph triples into the LLM context prompt.

### What Was Implemented
- Query keyword tokenization and concept relevance matching in `KnowledgeGraphService.get_workspace_triples(workspace_id, query)`.
- **Zero-Match KG Guardrail**: If zero concepts match the user query (or query contains no domain-specific keywords), `get_workspace_triples()` returns an empty list `[]`.
- Updated `MultiStageRetriever.execute_retrieval()` to pass `query` to `get_workspace_triples(workspace_id, query=query)`.
- Added unit test `test_kg_zero_match_guardrail()` in `backend/tests/test_knowledge_graph.py`.

### Root Cause Addressed
- Previously, `get_workspace_triples(workspace_id)` unconditionally returned ALL knowledge graph relations in the workspace and injected them into every single chat turn prompt regardless of relevance, polluting LLM prompts with unrelated concepts.

### Files/Components Changed
- [`backend/app/domain/knowledge/knowledge_graph_service.py`](file:///e:/repos/athenus/backend/app/domain/knowledge/knowledge_graph_service.py): Updated `get_workspace_triples()` to support `query` parameter, keyword/concept relevance filtering, and zero-match guard.
- [`backend/app/infrastructure/retrieval/multi_stage_retriever.py`](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py): Passed `query` to `self.kg_service.get_workspace_triples(workspace_id, query=query)`.
- [`backend/tests/test_knowledge_graph.py`](file:///e:/repos/athenus/backend/tests/test_knowledge_graph.py): Added `test_kg_zero_match_guardrail()`.

### Important Implementation Decisions
- Enforced zero triples (`[]`) for generic queries or greetings ("hi", "hello", "summarize the pdf") when no specific concept names match, keeping prompt context clean.
- When query keywords match specific graph concepts, only relationships containing those concepts are injected.

### Automated Tests Performed and Results
- `python -m pytest tests/test_knowledge_graph.py`: **Passed (16/16 passed)** in 2.82s.
- `npx tsc --noEmit` (Frontend): **Passed (0 errors)**.

### Manual QA Validation
| Test | How to Conduct | Expected Behavior |
| :--- | :--- | :--- |
| **Zero-Match KG Guardrail Test** | 1. In a workspace containing knowledge graph concepts (e.g. Robotics concepts), send a general greeting or unrelated query: *"hi, how are you?"* or *"what is the weather?"*.<br>2. Inspect the assembled prompt / context output. | **Zero knowledge graph triples** are injected into the prompt context. The response answers naturally without citing unrelated graph concepts. |
| **Relevant KG Triple Retrieval Test** | 1. Query a specific concept existing in the knowledge graph: *"What are the prerequisites for Neural Networks?"* (assuming Neural Networks exists in KG). | Only the relevant relationship triples for Neural Networks are retrieved and injected into the prompt context. |

### GAP/Observations
- Citations need improvement: consider simplifying citations by citing the relevant document instead of specific pages within that document.

### Validation Status
- **PASSED & VALIDATED BY USER** (Explicit manual QA approval received).

---

## Phase 1.3 — Token Budget Enforcement & Output Capacity Reservation (with Phase 1.3B Large Document Support)

### Phase Summary
Implemented model context limit lookup and token budget enforcement in `MultiStageRetriever.enforce_token_budget()`. Guaranteed output capacity reservation ($\text{reserved\_output\_tokens} = 2,048$) adhering strictly to the invariant:
$$\text{input\_tokens} + \text{reserved\_output\_tokens} \le \text{model\_context\_limit}$$
Additionally, expanded maximum document page safety limit from `200` to `2000` pages (Phase 1.3B) while maintaining the 100 MB file size limit to support large textbook/reference PDF ingestion.

### What Was Implemented
- Model context limit table configuration in `ModelRegistry` for Groq (`128,000`), Anthropic Claude (`200,000`), OpenAI (`128,000`), and Ollama (`8,192`).
- `MultiStageRetriever.enforce_token_budget()` method that dynamically measures prompt tokens and trims lower-scoring retrieved chunks if `input_tokens + reserved_output_tokens > model_context_limit`.
- Updated `WorkspaceIntelligenceManager.query_workspace()` and `capabilities.py` to set `max_tokens = 2048` in `TextGenerationRequest`, guaranteeing the LLM generation budget is never starved.
- Expanded `max_pages` default in `DocumentParsingRequest` (`capabilities.py`) and `DocumentWorker` (`document_worker.py`) from `200` to `2000` pages.
- Added unit test `test_enforce_token_budget()` in `backend/tests/test_retrieval_rag.py`.

### Root Cause Addressed
- Previously, context token limits were unconstrained or hardcoded to small values (e.g. 1024/512 tokens), leaving output generation starved or risking prompt overflow on long document queries.
- Ingestion defaulted to a restrictive 200-page limit, failing large 900+ page textbook uploads.

### Files/Components Changed
- [`backend/app/domain/ai/capabilities.py`](file:///e:/repos/athenus/backend/app/domain/ai/capabilities.py): Updated default `max_tokens` to `2048` and `max_pages` default to `2000`.
- [`backend/app/services/workers/document_worker.py`](file:///e:/repos/athenus/backend/app/services/workers/document_worker.py): Set `max_pages=2000` for document parsing requests.
- [`backend/app/domain/ai/model_registry.py`](file:///e:/repos/athenus/backend/app/domain/ai/model_registry.py): Registered accurate context windows for Groq (128k), Claude (200k), OpenAI (128k), and Ollama (8.1k).
- [`backend/app/infrastructure/retrieval/multi_stage_retriever.py`](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py): Implemented `enforce_token_budget()` and Stage 7 context limit trimming.
- [`backend/app/application/services/workspace_intelligence.py`](file:///e:/repos/athenus/backend/app/application/services/workspace_intelligence.py): Passed `max_tokens=2048` to text capability.
- [`backend/tests/test_retrieval_rag.py`](file:///e:/repos/athenus/backend/tests/test_retrieval_rag.py): Added `test_enforce_token_budget()`.

### Important Implementation Decisions
- Enforced hard `input_tokens + reserved_output_tokens <= model_context_limit` before calling provider adapters.
- Trims lowest-scoring reranked chunks first if total prompt size exceeds the maximum allowed input token threshold.
- Expanded page capacity ceiling to 2,000 pages while strictly enforcing the 100 MB binary file size safety limit.

### Automated Tests Performed and Results
- `python -m pytest tests/test_retrieval_rag.py -k test_enforce_token_budget`: **Passed (1/1 passed)** in 1.80s.
- `python -m pytest tests/test_document_worker.py`: **Passed (3/3 passed)** in 0.14s.
- `npx tsc --noEmit` (Frontend): **Passed (0 errors)**.

### Manual QA Validation
| Test | How to Conduct | Expected Behavior |
| :--- | :--- | :--- |
| **Token Budget & Output Capacity Test** | 1. Query a large document with a complex multi-part query using Groq (`llama-3.3-70b-versatile`) or Ollama (`llama3:8b`).<br>2. Inspect the generated answer length and completion status. | The AI returns a complete, comprehensive response up to 2,048 output tokens without cutting off mid-sentence or hitting context limit errors. |
| **Large Document (900+ Page) Ingestion Test** | 1. Upload a 900+ page PDF document (e.g. textbook < 100 MB).<br>2. Observe the document pipeline progress bar in the Athenus UI. | The document succeeds through the ingestion pipeline (`Receiving Document Upload ✓`, `Parsing Structure ✓`, `Complete ✓`) without page limit error failures. |

### GAP/Observations
- For large textbook uploads (900+ pages / ~2,000 sub-chunks / ~1 million words), unbatched CPU vector embedding calculation in `SentenceTransformers` (`bge-small-en-v1.5`) takes ~6–10 minutes inside Docker. Consider implementing chunk sub-batching (e.g. `batch_size=64`) and streaming progress events (`vector_indexing` 75% -> 95%) to optimize CPU memory throughput and provide granular UI progress updates.

### Validation Status
- **PASSED & VALIDATED BY USER** (Explicit user approval received).

---

## Phase 1.4 — Legacy Content Queue-Based Backfill & Migration

### Phase Summary
Implemented fast FTS5 search index backfill and queue-routed legacy document re-chunking migration in `PersistentIngestionWorker`. Executed automatically during `boot_recovery()` on backend server boot to ensure legacy materials are idempotently migrated to ~500-word sub-chunks and indexed into `transcript_chunks_fts`.

### What Was Implemented
- `PersistentIngestionWorker._backfill_fts5()` executing fast SQL backfill during server startup to populate `transcript_chunks_fts` for any chunks missing from the FTS5 index.
- `PersistentIngestionWorker._enqueue_legacy_rechunk_jobs()` scanning SQLite for legacy documents containing whole-page chunks (`word_count > 500` or single page-level chunk IDs) and enqueuing `rechunk_ingestion` jobs in `ArtifactJobTable`.
- `PersistentIngestionWorker._execute_rechunk_migration()` executing sequential re-chunking under `PersistentIngestionWorker._lock` (`asyncio.Lock`), replacing legacy page-level chunks with modern ~500-word sub-chunks (≤750 tokens) and updating FTS5 searchability.
- `init_db()` in `session.py` creating the `transcript_chunks_fts` SQLite FTS5 virtual table on startup.
- Added unit test `test_fts5_backfill_and_legacy_migration()` in `backend/tests/test_legacy_migration.py`.

### Root Cause Addressed
- Previously, legacy materials ingested prior to Phase 1.1 retained single-page chunks and were missing from SQLite FTS5 indexes, preventing BM25 searchability and causing retrieval quality divergence between legacy and newly ingested materials.

### Files/Components Changed
- [`backend/app/domain/ingestion/persistent_ingestion_queue.py`](file:///e:/repos/athenus/backend/app/domain/ingestion/persistent_ingestion_queue.py): Implemented `_backfill_fts5()`, `_enqueue_legacy_rechunk_jobs()`, `_execute_rechunk_migration()`, and updated `boot_recovery()` and `_fetch_next_queued_job()`.
- [`backend/app/infrastructure/db/session.py`](file:///e:/repos/athenus/backend/app/infrastructure/db/session.py): Added `transcript_chunks_fts` FTS5 virtual table creation in `init_db()`.
- [`backend/tests/test_legacy_migration.py`](file:///e:/repos/athenus/backend/tests/test_legacy_migration.py): Added automated verification for FTS5 backfill and legacy job queue creation.

### Important Implementation Decisions
- Executed legacy re-chunking jobs sequentially through `PersistentIngestionWorker` queue to prevent CPU/memory spikes.
- Enforced idempotency checks before re-chunking: if a document already possesses sub-chunks (`_sub_` in ID or word count <= 500), migration marks the job completed and returns immediately without duplicate data creation.

### Automated Tests Performed and Results
- `python -m pytest tests/test_legacy_migration.py`: **Passed (1/1 passed)** in 0.85s.
- `python -m pytest tests/test_chunker_generalization.py tests/test_anydoc_adapter.py tests/test_knowledge_graph.py tests/test_document_worker.py tests/test_legacy_migration.py`: **Passed (28/28 passed)** in 3.63s.
- `npx tsc --noEmit` (Frontend): **Passed (0 errors)**.

### Manual QA Validation
| Test | How to Conduct | Expected Behavior |
| :--- | :--- | :--- |
| **Boot Recovery & FTS5 Backfill Test** | 1. Insert a legacy chunk into SQLite `transcript_chunks` with `word_count > 500`.<br>2. Restart backend container (`docker compose restart backend`).<br>3. Inspect SQLite tables `transcript_chunks_fts` and `artifact_jobs`. | `transcript_chunks_fts` contains the backfilled chunk, and a `rechunk_ingestion` job is queued and processed idempotently. |

### Validation Status
- **PASSED & VALIDATED BY USER** (Explicit manual QA approval received).

---

# Milestone 2 — Prompt Reform & Multi-Source Synthesis

## Phase 2.1 — Prompt Reform & Direct Answer Extraction

### Phase Summary
Implemented explicit prompt system instructions for direct, concise answer extraction when evidence exists, introduced presentation-order scoring (`prompt_priority_score = bm25 * 0.7 + cosine * 0.3`) for context chunk arrangement, and enforced explicit empty evidence fallback messaging.

### What Was Implemented
- Direct answer instruction added to prompt context template in `MultiStageRetriever._assemble_prompt()`: `"If the context contains a direct answer, provide it CONCISELY without additional reasoning."`
- Presentation-order scoring in `MultiStageRetriever._compress_context()` using `prompt_priority_score = bm25_score * 0.7 + cosine_score * 0.3` to prioritize exact lexical matches at the top of LLM context windows.
- Empty context fallback in `WorkspaceIntelligenceManager.query_workspace()`: if no chunks, triples, or active context are retrieved, response text is prepended with `"No relevant context found in workspace materials. "`.
- Added unit test suite `test_prompt_reform.py` testing prompt instructions, presentation ordering, and empty evidence fallback.

### Root Cause Addressed
- Previously, system prompts lacked explicit instructions for direct concise answers or fallback instructions when context is empty/insufficient, causing hallucination or verbose tangents.

### Files/Components Changed
- [`backend/app/infrastructure/retrieval/multi_stage_retriever.py`](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py): Added direct answer system instruction to prompt template and updated `_compress_context()` with `prompt_priority_score` sorting.
- [`backend/app/application/services/workspace_intelligence.py`](file:///e:/repos/athenus/backend/app/application/services/workspace_intelligence.py): Added empty evidence fallback check prepending `"No relevant context found in workspace materials. "`.
- [`backend/tests/test_prompt_reform.py`](file:///e:/repos/athenus/backend/tests/test_prompt_reform.py): Added automated test suite for Phase 2.1.

### Important Implementation Decisions
- Separated Stage 6 reranker scoring (`rerank_score = cosine*0.4 + bm25*0.3 + overlap*0.3`) from Stage 8 presentation ordering (`prompt_priority_score = bm25*0.7 + cosine*0.3`). Stage 6 filters candidate hits, while Stage 8 presentation ordering places high-exact-match lexical chunks at the top of the LLM context window to optimize grounding.

### Automated Tests Performed and Results
- `python -m pytest tests/test_prompt_reform.py`: **Passed (2/2 passed)** in 1.20s.
- `python -m pytest tests/test_chunker_generalization.py tests/test_anydoc_adapter.py tests/test_knowledge_graph.py tests/test_document_worker.py tests/test_legacy_migration.py tests/test_prompt_reform.py`: **Passed (30/30 passed)** in 3.16s.
- `npx tsc --noEmit` (Frontend): **Passed (0 errors)**.

### Manual QA Validation
| Test | How to Conduct | Expected Behavior |
| :--- | :--- | :--- |
| **Direct Answer Extraction Test** | 1. Upload a document containing a specific fact (e.g. *"The target operating frequency is 2.4 GHz"*).<br>2. Ask chat: *"What is the operating frequency?"* | The AI returns a concise, direct answer (*"The operating frequency is 2.4 GHz [Document Page X]"*) without unnecessary preamble or tangents. |
| **Empty Evidence Fallback Test** | 1. In a workspace with no materials or querying an entirely unrelated concept not in the workspace.<br>2. Ask chat: *"What is Quantum Superposition?"* | Response explicitly starts with `"No relevant context found in workspace materials. "` before providing general pretrained knowledge. |

### Validation Status
- **PASSED & VALIDATED BY USER** (Explicit manual QA approval received).

---
