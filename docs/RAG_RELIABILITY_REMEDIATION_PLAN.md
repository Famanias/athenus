# Document 2 — RAG Reliability Remediation Plan (Athenus)

> **Status**: Verified against codebase as of 2026-08-10. Approved with strict phase gates and explicit failure classification.
> **Objective**: Address 413 errors, hallucination looping, retrieval quality, citation integrity, cross-source scope, and legacy content migration with **minimal architectural changes**.

---

## **Core Engineering Principles & Failure Taxonomy**

### **1. Failure Classification Taxonomy**
To make system behavior measurable and diagnosable, all verification tests must categorize failures into four distinct classes:
- **Class A — Retrieval Failure**: Correct evidence exists in the workspace but does not enter the candidate set (dense top-10 or BM25 top-10).
- **Class B — Context Assembly Failure**: Correct evidence was retrieved but was truncated, filtered out, reordered poorly, or omitted during prompt assembly.
- **Class C — Generation / Grounding Failure**: Correct evidence was present in the assembled prompt, but the LLM hallucinated, looped, or produced an inaccurate response.
- **Class D — Citation Validation Failure**: The response text is accurate, but inline citations are missing, malformed, ungrounded, or map to incorrect metadata.

### **2. Strict Phase Gate Protocol**
No phase may begin until the preceding phase has passed automated verification **AND** received explicit manual QA validation from the user.
- **Phase 1.1** → Investigate → Implement → Unit/Integration Tests → **STOP for User Manual QA**
- **Phase 1.2** → Investigate → Implement → Unit/Integration Tests → **STOP for User Manual QA**
- **Phase 1.3** → Investigate → Implement → Unit/Integration Tests → **STOP for User Manual QA**
- **Phase 1.4** → Investigate → Implement → Unit/Integration Tests → **STOP for User Manual QA**

---

## **Milestone 1 — Context Size Control & 413 Error Prevention**
**Problem**: Simple queries trigger 413 errors due to oversized LLM requests caused by:
- Whole-page document chunks (thousands of tokens).
- Unbounded knowledge-graph triples injected into every prompt.
- No token counting, truncation, or compression.
- Unmigrated legacy content stored as giant page chunks.

**Phases**:

### **Phase 1.1 — Document Chunk Splitting & Hard Token Ceiling**
**Objective**: Split document pages into sub-page chunks enforcing a target size and a hard maximum token ceiling.
**Root Cause**: `SemanticChunker.chunk_document_pages()` in `backend/app/domain/knowledge/chunker.py` creates one chunk per page, allowing multi-thousand-word chunks.
**Implementation & Invariants**:
- Target chunk size: **~500 words**.
- **Hard Maximum Ceiling: ≤750 tokens**. Chunker MUST enforce the 750 token ceiling explicitly rather than relying solely on word count.
- Sub-chunks MUST preserve `location["page"]` and `page_number` in Qdrant payloads and SQLite `transcript_chunks` table so frontend badges (`📄 Page 176`) remain fully compatible.
- Maintain deterministic point IDs via `uuid5(NAMESPACE_URL, unit.id)` so re-ingestion overwrites existing vectors cleanly.
**Verification**:
- Automated: Unit test verifying target word counts, hard token limit (≤750 tokens), and location metadata preservation.
- Manual QA: Upload a 5,000-word PDF; verify all chunks are ≤750 tokens and citation badges render accurately.
**Expected Behavior**: All document chunks ≤750 tokens with preserved citation metadata.

### **Phase 1.2 — Knowledge Graph Triple Relevance Filtering & Zero-Match Guard**
**Objective**: Limit KG triples injected into prompts to **query-relevant concepts**, withholding triples if zero relevant concepts exist.
**Root Cause**: `get_workspace_triples()` in `backend/app/domain/knowledge/knowledge_graph_service.py` returns all relations unfiltered, flooding prompts with irrelevant triples.
**Implementation & Guardrails**:
- Add `query_filter` parameter to `get_workspace_triples()`.
- Use a **hybrid relevance matching strategy**:
  1. **Semantic Embedding Similarity**: Compute cosine similarity between query vector and `knowledge_concepts.embedding` (384-dim JSON vectors in SQLite) for workspace concepts with similarity ≥ 0.6.
  2. **Text / Term Matching**: Match concepts appearing in query tokens OR retrieved chunk text.
- **Zero-Match Guardrail**:
  - Relevant concepts found → include relevant triples, bounded by maximum cap (≤30 triples).
  - Partially relevant concepts found → supplement up to maximum cap with closely related triples sorted by `weight DESC`.
  - **Zero relevant concepts found → DO NOT inject arbitrary KG triples** (avoid polluting prompt with unrelated facts).
**Verification**:
- Automated: Test query with matching concepts vs. query with zero matching concepts; verify zero KG triples injected when no relevance exists.
- Manual QA: Query specific topic; verify prompt KG context is strictly bounded and relevant.
**Expected Behavior**: Prompts contain ≤30 KG triples when relevant, and 0 triples when no concept match exists.

### **Phase 1.3 — Token Budget Enforcement & Reserved Output Capacity**
**Objective**: Prevent oversized LLM requests across all supported model providers while guaranteeing output token capacity.
**Root Cause**: No token counting or truncation anywhere in retrieval or prompt assembly.
**Implementation**:
- Add a **per-provider token counter** — strategy for **all five** active providers:
  | Provider | Token counter |
  |---|---|
  | Groq (`llama-3.3-70b-versatile`) | Llama tokenizer via `transformers` (fallback `chars/3.5`) |
  | OpenAI | `tiktoken` (OpenAI BPE) |
  | Anthropic | Anthropic `count_tokens` API endpoint / `chars/3.5` fallback |
  | OpenRouter | Conservative `chars/3.5` + headroom |
  | Ollama | Local model tokenizer when available, else `chars/3.5` |
- Update `WorkspaceIntelligenceManager.query_workspace()` in `backend/app/application/services/workspace_intelligence.py` to resolve active LLM provider limits via `AIServiceBus.get_text_capability()` / `get_capabilities()`.
- **Hard Capacity Invariant**: Enforce `input_tokens + reserved_output_tokens <= model_context_limit`.
- In `MultiStageRetriever._assemble_prompt()`, compute total prompt tokens and truncate if total exceeds **75%** of the active model's available input context window. Truncation priority order:
  - Keep **active context** → then **retrieved chunks** → then **KG triples**.
**Verification**:
- Automated: Simulate oversized contexts for each provider; verify input + output tokens stay strictly within provider context limits.
- Manual QA: Force a large context pre-fix; confirm 413 errors disappear.
**Expected Behavior**: All LLM requests satisfy input + output token budget constraints.

### **Phase 1.4 — Legacy Content Backfill & Safe Queue Migration**
**Objective**: Guarantee single-tier retrieval quality across legacy and newly ingested materials safely and idempotently.
**Root Cause**: Existing documents ingested prior to Phase 1.1 retain giant single-page chunks in Qdrant/SQLite and are missing from FTS5 indexes.
**Implementation & Crash Safety**:
- **Invocation Trigger**: Executed automatically during `PersistentIngestionWorker.boot_recovery()` on backend startup.
- **Fast FTS5 Backfill**: Run a `LEFT JOIN` query during `boot_recovery()`:
  ```sql
  INSERT INTO transcript_chunks_fts(chunk_id, workspace_id, text)
  SELECT tc.id, tc.workspace_id, tc.text
  FROM transcript_chunks tc
  LEFT JOIN transcript_chunks_fts fts ON tc.id = fts.chunk_id
  WHERE fts.chunk_id IS NULL;
  ```
- **Queue-Routed Legacy Re-chunking**:
  1. During `boot_recovery()`, scan SQLite `media_items` for document items whose `transcript_chunks` have whole-page chunks (`word_count > 500` or 1 chunk per page).
  2. Enqueue legacy documents into `PersistentIngestionWorker` as `rechunk_ingestion` jobs (`artifact_type="rechunk_ingestion"`).
  3. Re-chunking executes sequentially under `PersistentIngestionWorker._lock` (`asyncio.Lock`), deleting legacy page-level points from Qdrant/SQLite and re-running `chunk_document_pages()`.
  4. **Idempotency Guarantee**: Migration checks existing chunk structures before running; if interrupted mid-migration, rebooting safely resumes without corrupting data or duplicating points.
**Verification**:
- Automated: Test `boot_recovery()` against legacy pre-populated SQLite DB; simulate crash halfway through and verify clean recovery.
- Manual QA: Boot backend with legacy database; confirm legacy documents are re-chunked and searchable via BM25.
**Expected Behavior**: All legacy workspace materials are safely and idempotently migrated to sub-chunks and FTS5 searchability.

---

## **Milestone 2 — Hallucination & Answer Grounding**
**Problem**: The model loops on reasoning or invents citations instead of answering directly from evidence.

### **Phase 2.1 — Prompt Reform & Answer Extraction**
**Objective**: Force direct answers when evidence exists and provide explicit fallback when evidence is missing.
**Implementation**:
- In `MultiStageRetriever._assemble_prompt()`:
  - **Add**: "If the context contains a direct answer, provide it CONCISELY without additional reasoning."
  - **Add**: Presentation-order priority for prompt chunks: `prompt_priority_score = bm25_score * 0.7 + cosine_score * 0.3`. (Distinct from Stage 6's `rerank_score = cosine*0.4 + bm25*0.3 + overlap*0.3`). Add inline code comments clarifying the separate roles of each formula.
- In `WorkspaceIntelligenceManager.query_workspace()`:
  - If retrieved chunks are empty, prepend "No relevant context found in workspace materials. " to the output or fallback prompt.
**Verification**:
- Automated: Classify test outcomes using Failure Taxonomy (Class B vs Class C). Verify concise answers when evidence exists.
- Manual QA: Replay failing queries; confirm model gives direct answer without looping.

### **Phase 2.2 — Inline Citation Validation**
**Objective**: Prevent fabricated inline citations.
**Implementation**:
- Wire the **existing** `parse_chat_citations()` in `backend/app/domain/knowledge/citation_parser.py` into the response path:
  - In `WorkspaceIntelligenceManager.query_workspace()`, parse the LLM's raw text response.
  - Validate inline citations against `retrieved_chunks` metadata (`page_number`, `start_time`/`end_time`).
  - Strip ungrounded/invalid citations before returning to the caller.
**Verification**:
- Automated: Inject fake citations in mock response; verify Class D failure triggers parsing and stripping.
- Manual QA: Attempt to force a fake inline citation; verify it is sanitized.

---

## **Milestone 3 — Retrieval Quality & Cross-Source Scope**
**Problem**: Active-item context is not used to boost search scores; BM25 only re-ranks the dense top-10; active document context lacks page text.

### **Phase 3.1 — Active-Item Context Boosting & SQLite FTS5 BM25 with DB Triggers**
**Objective**: Boost retrieval scores for active items with database-guaranteed FTS5 BM25 search across full corpus.
**Implementation**:
- **Active-item boosting**: In `MultiStageRetriever.execute_retrieval()`, multiply the cosine score of any payload whose `media_id` or `document_id` matches the active item by `1.5`.
- **SQLite FTS5 DB Triggers**: Attach native SQLite triggers (`AFTER INSERT`, `AFTER UPDATE`, `AFTER DELETE` on `transcript_chunks`) to mirror `transcript_chunks_fts`.
- **FTS5 Scoring Order**: Perform BM25 search querying `ORDER BY bm25(transcript_chunks_fts) ASC` (or `ORDER BY rank`) to select top-10 relevant hits correctly.
- **Explicit Fusion Step**: Dense search (Qdrant threshold 0.2 + active boost) + Sparse search (FTS5 BM25) → RRF merge (`k=60`) → Deduplicate by `chunk_id` → Cap at `N=15` before Stage 6 reranking.
**Verification**:
- Automated: Regression test suite covering INSERT, UPDATE, DELETE trigger sync and video/PDF/mixed search.
- Manual QA: Query active document; confirm active document chunks rank higher.

### **Phase 3.2 — Deduplication & Relevance Threshold**
**Objective**: Filter low-relevance noise and prevent duplicate context.
**Implementation**:
- In `EmbeddedQdrantVectorStoreAdapter.search()`, pass `score_threshold=0.2` (cosine) to dense vector search.
- Deduplicate candidate chunks post-RRF fusion by `chunk_id` before passing to Stage 6 reranker.

### **Phase 3.3 — Active Document Page Text Retrieval & Sub-Chunk Concatenation**
**Objective**: Supply complete, coherent page text for active document context.
**Implementation**:
- In `MultiStageRetriever._extract_document_page_context()`, query SQLite `transcript_chunks` table for `document_id` and `start_time <= current_page <= end_time`.
- Sort all matching sub-chunks for `current_page` by `chunk_index ASC` and join their `text` sequentially with newlines.

---

## **Regression Suite & Failure Classification Requirements**

To prevent regressions, the automated test suite must maintain explicit test coverage for:
1. **Video Retrieval Preservation**: Video-only queries, active video context (±30s window), and mixed PDF+video queries.
2. **Original Failure Modes**:
   - 413 oversized context queries.
   - Document direct answer retrieval.
   - Empty evidence fallback queries.
   - Hallucination / citation fabrication attempts.
   - Active PDF page queries & active video timestamp queries.
   - Cross-source multi-document retrieval.
   - Legacy document retrieval post-migration.

---

## **Phase Execution Protocol**
For **Phase 1.1 ONLY**:
1. **Investigate**: Codebase examination of chunking, schema flow, ID generation, and existing tests.
2. **Implementation Plan**: Present exact proposed changes before touching code.
3. **Implement**: Code Phase 1.1 only.
4. **Automated Verification**: Run `pytest` and `tsc`.
5. **Report Results**: Detail changed files, executed tests, and outputs.
6. **Manual QA Table**: Present structured manual QA matrix.
7. **STOP**: Await explicit user approval before Phase 1.2.