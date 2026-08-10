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
