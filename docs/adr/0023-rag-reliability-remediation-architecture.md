# 23. RAG Reliability Remediation & Multi-Stage Retrieval Architecture

* **Status**: Implemented / Accepted
* **Date**: 2026-08-10
* **Deciders**: Athenus Core Architecture Team

---

## Context & Problem Statement

Prior to this architectural remediation, the Athenus RAG retrieval engine exhibited critical reliability and grounding failure modes:
1. **Whole-Page Chunk Truncation**: PDF documents were ingested as single multi-thousand-word page chunks (~7,500 tokens), causing prompt context starvation and truncation.
2. **Binary PDF Syntax Pollution**: Plain-text fallback reading opened `.pdf` binaries directly, indexing raw PDF stream objects (`endstream`, `endobj`) and base64 XMP XML metadata tags into Qdrant/SQLite.
3. **Unbounded Knowledge Graph Pollution**: `KnowledgeGraphService.get_workspace_triples()` unconditionally injected ALL graph relationships in the workspace into every prompt turn regardless of query relevance.
4. **Lack of Token Budget Safeguards**: Prompt assembly lacked token counting and context limit checks, leading to starved LLM output token allocations (`max_tokens` starved or cut off).
5. **No Noise Filtering or Active Context Prioritization**: Qdrant dense vector search lacked similarity thresholds (`score_threshold`), accepting low-similarity noise, and active viewer documents received no retrieval score preference over inactive workspace files.
6. **Conversational Citation Hallucination**: Diagnostic RAG fallback text (`"No relevant context found..."`) was forcibly prepended onto user responses, polluting casual pleasantries (`"Hi"`, `"Hello"`) with spurious citations.

---

## Decision Drivers

- **Grounding Accuracy**: Prevent citation hallucination and evidence fabrication across all document and video types.
- **Local-First Efficiency**: Operate entirely on host hardware within embedded SQLite and Qdrant without cloud dependencies.
- **Token Budget Invariant**: Guarantee LLM output generation capacity ($\text{reserved\_output\_tokens} = 2,048$) under the hard constraint:
  $$\text{input\_tokens} + \text{reserved\_output\_tokens} \le \text{model\_context\_limit}$$
- **Zero Regression on Video Ingestion**: Preserve video speech-to-text ASR pipelines while maintaining unified chunk location metadata (`location_json`).

---

## Considered Alternatives

1. **Cloud PostgreSQL + `pgvector` Migration**: Transitioning to PostgreSQL with `pgvector`. *Rejected*: Violates Athenus's core local-first desktop architectural constraint.
2. **Whole-Page Document Chunking**: Retaining full pages as individual chunks. *Rejected*: Causes severe context dilution and LLM prompt limit overflows.
3. **Unbounded Knowledge Graph Injection**: Injecting all workspace graph triples into every prompt turn. *Rejected*: Pollutes LLM context windows with unrelated concept noise.

---

## Architectural Decisions

### 1. Sub-Chunking (~500 Words, ≤750 Token Ceiling) & Clean Text Extraction
- **Sub-Chunking Engine**: Implemented `SemanticChunker.chunk_document_pages()` dividing document pages into ~500-word sub-chunks with a strict hard ceiling of **$\le 750$ tokens** per chunk via `count_tokens()`. Sub-chunk IDs follow `{document_id}_chunk_{index}`.
- **Clean PDF Text Parsing**: Upgraded `AnyDocDocumentParsingAdapter._parse_with_fallback()` using `pypdf.PdfReader` to extract clean page text while filtering out binary PDF stream objects and XMP metadata XML tags (`<x:xmpmeta>`). Expanded maximum document ceiling to **2,000 pages**.

### 2. SQLite FTS5 Virtual Table & Native Database Triggers
- **Schema**: Created `transcript_chunks_fts` virtual table (`chunk_id UNINDEXED`, `workspace_id UNINDEXED`, `text`).
- **Database Triggers**: Attached native SQLite triggers (`transcript_chunks_ai`, `transcript_chunks_au`, `transcript_chunks_ad`) to mirror all `INSERT`, `UPDATE`, and `DELETE` operations on `transcript_chunks` directly into `transcript_chunks_fts`.

### 3. Multi-Stage Hybrid Search & Reciprocal Rank Fusion (RRF)
- **Active-Item 1.5x Score Boosting**: Dense vector hits matching the active `document_id` or `media_id` receive a **1.5x score multiplier**.
- **Full-Corpus FTS5 BM25 Search**: Implemented `BM25Retriever.search_fts5()` executing full-text BM25 queries across the workspace corpus.
- **Reciprocal Rank Fusion (RRF, $k=60$)**: Merges dense Qdrant vector hits and sparse BM25 hits using $\text{RRF}(c) = \frac{1}{60 + \text{rank}_{\text{dense}}} + \frac{1}{60 + \text{rank}_{\text{sparse}}}$, deduplicating by `chunk_id` and capping candidates at top $N=15$.
- **Vector Score Thresholding**: Enforced `score_threshold = 0.2` (cosine similarity) in `EmbeddedQdrantVectorStoreAdapter.search()`.

### 4. Zero-Match Knowledge Graph Guardrail
- Updated `KnowledgeGraphService.get_workspace_triples()` to tokenise query keywords and match graph concepts. If zero concepts match, `get_workspace_triples()` returns `[]`, preventing arbitrary concept injection.

### 5. Token Budget Enforcement & Output Capacity Reservation
- Implemented `MultiStageRetriever.enforce_token_budget()`, reserving $\text{reserved\_output\_tokens} = 2,048$ tokens and dynamically trimming lower-priority chunks if input prompt tokens exceed `model_context_limit - 2048`.
- Set presentation-order priority sorting using `prompt_priority_score = bm25_score * 0.7 + cosine_score * 0.3` to place exact lexical matches at the top of LLM context windows.

### 6. Active Document Page Text Concatenation
- Updated `MultiStageRetriever._extract_document_page_context()` to query SQLite `transcript_chunks` for `start_time <= current_page <= end_time`, joining all page sub-chunks in `chunk_index ASC` order with double newlines.

### 7. Grounding & Citation Separation
- Separated internal context state (`has_relevant_context: bool`) from user-facing presentation text. Diagnostic text (`"No relevant context found..."`) is removed from user responses, allowing casual pleasantries (`"Hi"`, `"Hello"`) to return clean natural answers with zero citations.

---

## Consequences & Trade-offs

### Positive Consequences
- **Eliminated Grounding Failures**: Zero citation hallucinations or spurious citation chips on casual conversational turns or unsupported queries.
- **Precision Retrieval**: High-precision hybrid search with RRF ($k=60$) and active-item 1.5x score boosting.
- **Robust Large Document Support**: Supports PDF textbooks up to 2,000 pages cleanly.
- **Database Trigger Reliability**: Automatic, instant FTS5 index synchronization without manual re-indexing scripts.

### Known Limitations & Trade-offs
- **CPU Embedding Throughput on Large Books**: For 900+ page textbooks (~2,000 sub-chunks), unbatched CPU embedding calculation takes ~6–10 minutes inside Docker containers on host CPU.
