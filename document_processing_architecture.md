# Athenus Knowledge OS — Document Processing Architecture (AnyDoc & RapidOCR Integration)

This document details the architectural roles, responsibilities, runtime integration, and design rationale for **AnyDoc** and **PaddleOCR / RapidOCR** in the Athenus Knowledge OS document ingestion pipeline as of commit `6b86b0f`.

---

## 1. Actual Current Document Pipeline Trace

The active, executable document ingestion pipeline processes files through two parallel paths: a **Processing Path** (for AI vector indexing and Knowledge Graph extraction) and a **Presentation Path** (for human visual rendering).

```text
                               Original Document File (.pdf, .docx, .pptx, etc.)
                                                       │
                           ┌───────────────────────────┴───────────────────────────┐
                           │                                                       │
                    Processing Path                                         Presentation Path
                           │                                                       │
            AnyDoc Structural Parser                                 Document Viewer Component
       (AnyDocDocumentParsingAdapter)                                   (DocumentViewer.tsx)
                           │                                                       │
      ┌────────────────────┴────────────────────┐                         Renders Original PDF Binary
      │                                         │                          (High-Fidelity Page Layout,
  Native Text                             Scanned Pages                     Zoom, and Jump Target)
   (Extracted)                             (Detected)
      │                                         │
      │                                  RapidOCR Engine
      │                           (RapidOCROCRAdapter on-demand)
      │                                         │
      └────────────────────┬────────────────────┘
                           │
             Page-Aware Structured Markdown
                           │
                 Semantic Document Chunker
             (SemanticChunker.chunk_document_pages)
                           │
             SentenceTransformers Embedding Worker
             (EmbeddingWorker + BAAI/bge-small-en-v1.5)
                           │
             Embedded Qdrant Vector Collection & SQLite
             (EmbeddedQdrantVectorStoreAdapter & TranscriptChunkTable)
                           │
             Knowledge Graph Concept & Relation Extractor
                  (GraphExtractionWorker)
                           │
             Grounding & Multi-Stage RAG Chat Agent
                     (MultiStageRetriever)
```

---

## 2. AnyDoc's Architectural Purpose

### Why Introduced
AnyDoc (`Firecrawl AnyDoc` engine wrapper) was introduced to solve the problem of **macro-level document structure extraction**. Raw text extractors (such as basic PyPDF text dumpers) discard document geometry, headings, markdown table formatting, and page boundaries, rendering the content unreadable for structured RAG chunking.

### Inputs & Outputs
- **Input**: Document file path (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.epub`, `.md`, `.txt`), file format, `max_pages=200`, `max_file_size_mb=100.0`.
- **Output**: `DocumentParsingResponse` containing:
  - `markdown`: Full converted markdown string with explicit `<!-- pagebreak -->` delimiters.
  - `pages`: List of `DocumentPageDTO` items (`page_number`, `text`, `page_type`, `section_title`).
  - `has_scanned_pages`: Boolean flag indicating if scanned or empty pages were detected.
  - `has_tables`: Boolean flag indicating if Markdown tables (`| Col |`) were parsed.

### Technical Responsibilities
1. **Multi-Format Ingestion**: Supports PDF, Word (`.docx`), PowerPoint (`.pptx`), Excel (`.xlsx`), EPUB, Markdown (`.md`), and Plain Text (`.txt`).
2. **Structure & Hierarchy**: Extracts headings (`#`, `##`), section titles, and paragraphs.
3. **Table Formatting**: Preserves table layouts by converting rows and columns into standard Markdown grid tables (`| Header 1 | Header 2 |`).
4. **Page Boundary Preservation**: Splits content by explicit `<!-- pagebreak -->` or `---` section breaks to preserve true page numbers (`page_number=1, 2, 3...`).
5. **Scanned Page Detection**: Checks page text length and image stubs (`is_scanned = len(clean_text) < 20 and ("![image" in clean_text or "[scanned]" in clean_text)`). Flags `page_type = "scanned"`.
6. **Does NOT Perform OCR**: AnyDoc relies on native PDF text stream extraction. If a page is image-based or scanned, AnyDoc flags it as `"scanned"` and delegates character recognition to RapidOCR.

### Repository Reference
- Adapter Class: `AnyDocDocumentParsingAdapter` in [`backend/app/infrastructure/adapters/anydoc_adapter.py`](file:///e:/repos/athenus/backend/app/infrastructure/adapters/anydoc_adapter.py#L14)
- Port Capability Interface: `IDocumentParsingCapability` in [`backend/app/domain/ai/capabilities.py`](file:///e:/repos/athenus/backend/app/domain/ai/capabilities.py)

---

## 3. PaddleOCR / RapidOCR's Architectural Purpose

### Why OCR is Needed
When documents consist of scanned paper pages, flattened image PDFs, or embedded diagram photos, no native text streams exist. Without optical character recognition, AnyDoc extracts 0 characters for those pages.

### Why RapidOCR (ONNX Runtime)
RapidOCR (a lightweight ONNX-runtime port of PaddleOCR) was selected because:
1. It runs 100% locally on CPU without needing heavy GPU dependencies or cloud API calls.
2. It executes ONNX inference in milliseconds per page.
3. It complies with Athenus's **Local-First Architecture Strategy** (ADR 0003 & 0021).

### Conditional On-Demand Execution
OCR is **NOT** performed indiscriminately across all pages. `DocumentWorker` checks AnyDoc's structural response:
```python
if parse_response.has_scanned_pages:
    async with workload_scheduler._semaphore:  # Hardware Semaphore = 1 (ADR 0021)
        for p in parse_response.pages:
            if p.page_type == "scanned" or not p.text.strip():
                ocr_res = await self.ocr_capability.perform_ocr(...)
                page_text = ocr_res.text.strip()
```
- Pages containing native text stream bypass OCR completely.
- Only pages marked `p.page_type == "scanned"` or empty text trigger `RapidOCROCRAdapter`.

### Output & Merging
RapidOCR returns line-by-line bounding boxes (`OCRLineDTO`) and reconstructed page text. `DocumentWorker` replaces the empty page text with the OCR extracted text and emits a unified `DocumentParsedEvent`.

### Repository Reference
- Adapter Class: `RapidOCROCRAdapter` in [`backend/app/infrastructure/adapters/ocr_adapter.py`](file:///e:/repos/athenus/backend/app/infrastructure/adapters/ocr_adapter.py#L13)
- Execution Location: `DocumentWorker.handle_document_uploaded()` in [`backend/app/services/workers/document_worker.py`](file:///e:/repos/athenus/backend/app/services/workers/document_worker.py#L71-L96)

---

## 4. Why Both Components Exist (Complementary Roles)

AnyDoc and RapidOCR solve **two fundamentally different engineering challenges**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                              AnyDoc                                    │
│  Macro-level Structural Understanding & Native Stream Parser           │
│  - "What is the outline, section hierarchy, page count, and table      │
│     grid structure of this digital document?"                          │
└────────────────────────────────────────────────────────────────────────┘
                                   │
                         Scanned Pages Flagged
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        PaddleOCR / RapidOCR                            │
│  Micro-level Optical Character Recognition Engine                      │
│  - "What printed or handwritten letters exist inside the pixels of     │
│     this scanned image page?"                                          │
└────────────────────────────────────────────────────────────────────────┘
```

- **Without AnyDoc**: An OCR-only pipeline loses section headings, table grids, Markdown structure, and document metadata.
- **Without RapidOCR**: An AnyDoc-only pipeline fails completely on scanned books, PDFs from paper scanners, and image-heavy documents.
- **Together**: The pipeline achieves 100% format coverage while preserving structural fidelity for AI RAG retrieval.

---

## 5. Trace by Document Modality & Case

### Case A — Normal Selectable Text PDF
1. User uploads PDF.
2. `AnyDocDocumentParsingAdapter` extracts native text streams, page breaks (`<!-- pagebreak -->`), and headings.
3. `has_scanned_pages` returns `False`.
4. **RapidOCR is 100% BYPASSED** (0 OCR overhead).
5. `DocumentParsedEvent` emitted $\rightarrow$ `SemanticChunker` $\rightarrow$ Qdrant & SQLite.

### Case B — Scanned PDF (Flattened Images)
1. User uploads scanned PDF.
2. `AnyDocDocumentParsingAdapter` inspects pages, finds empty text / image placeholders, sets `page_type = "scanned"`, and flags `has_scanned_pages = True`.
3. `DocumentWorker` acquires hardware semaphore (`Semaphore=1`).
4. `RapidOCROCRAdapter` runs ONNX OCR on each scanned page.
5. Reconstructed text replaces empty page text.
6. `DocumentParsedEvent` emitted $\rightarrow$ `SemanticChunker` $\rightarrow$ Qdrant & SQLite.

### Case C — Mixed PDF (Text Pages + Scanned Image Pages)
1. User uploads hybrid PDF.
2. AnyDoc parses native pages (e.g. pages 1–5), and flags scanned image pages (e.g. pages 6–7) as `page_type = "scanned"`.
3. `DocumentWorker` iterates through pages: pages 1–5 retain native text, pages 6–7 trigger `RapidOCROCRAdapter`.
4. Page texts are merged into a single page list.
5. `DocumentParsedEvent` emitted $\rightarrow$ `SemanticChunker` $\rightarrow$ Qdrant & SQLite.

### Case D — Document Containing Tables
1. User uploads document with financial or technical tables.
2. AnyDoc detects table layouts (`| Col 1 | Col 2 |`) and converts them into Markdown grid tables.
3. `has_tables` flag set to `True`.
4. The AI receives **structured Markdown table data**, preserving column-to-value relationships for RAG vector search and LLM context.

---

## 6. Relationship to the AI Knowledge Base

The pipeline converts a visual binary document into three distinct operational representations:

```text
Original PDF File (.pdf binary)
  └── Source Representation: Used exclusively for visual display in DocumentViewer.tsx.

Parsed Markdown & Page DTOs
  └── Processing Representation: Page-bounded text, headings, and markdown tables.

512-token Vector Chunks & Knowledge Graph Concepts
  └── AI Representation: 384-d Qdrant embeddings (BAAI/bge-small-en-v1.5) and SQLite concepts/relations used by RAG Chat Agent.
```

---

## 7. Relationship to Document Viewing (Presentation vs. Processing Path)

> [!IMPORTANT]
> **Document Processing and Document Viewing are Completely Decoupled Concerns.**

```text
                 Original PDF File
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
      Processing Path         Presentation Path
             │                       │
      AnyDoc + RapidOCR       DocumentViewer.tsx
             │                       │
     Markdown & Chunks       Native PDF Renderer
             │               (Vector Canvas / Page
     Vector Index (Qdrant)    Highlight Overlay)
             │                       │
      AI RAG Agent       Human Reader UI (Visual)
```

- **Presentation Path (`DocumentViewer.tsx`)**: Renders the **original visual PDF binary file** so human users see original fonts, high-resolution graphics, diagrams, and exact page layout. When a user clicks a `📄 Page X` citation in chat, `DocumentViewer` jumps to page X and displays an accent highlight ring over page X.
- **Processing Path (`AnyDoc` + `RapidOCR`)**: Extracts structured Markdown, page chunks, and vector embeddings so the **AI Agent** can search, ground answers, and generate flashcards/quizzes.

---

## 8. Inefficiency & Redundancy Audit

1. **OCR Overhead**: **NO REDUNDANCY.** RapidOCR is executed conditionally (`if parse_response.has_scanned_pages` AND `p.page_type == "scanned" or not page_text.strip()`). Native text pages never invoke OCR.
2. **Double Parsing**: **NO REDUNDANCY.** AnyDoc runs once per document upload, emitting `DocumentParsedEvent` which is consumed asynchronously by `EmbeddingWorker` and `GraphExtractionWorker`.
3. **Hardware Isolation**: RapidOCR execution is wrapped in `async with workload_scheduler._semaphore` (`Semaphore=1`), preventing CPU/RAM spikes during multi-file ingestion.

---

## 9. Why We Don't Simply Display OCR / Extracted Text in the Viewer

Displaying raw OCR or extracted text in the document viewer would degrade user experience:
- **Loss of Visual Layout**: Margins, multi-column layouts, header images, and graphics are lost in raw text.
- **Loss of Math & Vector Diagrams**: Mathematical formulas, charts, graphs, and visual figures cannot be rendered as plain text.
- **Human vs. Machine Optimization**: Humans read visual documents best; AI agents process clean, tokenized Markdown best.

By serving the original PDF file in `DocumentViewer.tsx` while feeding extracted Markdown to Qdrant, Athenus satisfies both human readability and machine intelligence requirements simultaneously.

---

## 10. Final Architectural Assessment

### AnyDoc
- **Purpose**: Structural document parsing, heading extraction, table formatting, and native text stream extraction.
- **Input**: Document file path (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.epub`, `.md`, `.txt`).
- **Output**: Structured Markdown with page delimiters and `DocumentPageDTO` array.
- **Used by**: `DocumentWorker`.

### PaddleOCR / RapidOCR
- **Purpose**: Local optical character recognition for scanned image pages.
- **Input**: Image/PDF page path & page number.
- **Output**: Reconstructed page text (`OCRResponse` & `OCRLineDTO`).
- **Used by**: `DocumentWorker` (on-demand when AnyDoc flags `page_type == "scanned"`).

### Together
- **AnyDoc** handles macro-level document structure and native digital text.
- **RapidOCR** handles micro-level character recognition for scanned images.

### Document Viewer
- Responsible for displaying the **original document binary** visually to human users with page navigation and citation highlighting.

### AI Knowledge Pipeline
- Responsible for indexing extracted Markdown chunks into Qdrant vector store and extracting domain concepts into the SQLite Knowledge Graph for RAG chat retrieval.

---

### Direct Answer to Architecture Question

> **Are AnyDoc and PaddleOCR/RapidOCR solving complementary problems in the current architecture, or are we unnecessarily overlapping their responsibilities?**
>
> **ANSWER: They are solving 100% complementary problems.** AnyDoc extracts digital document structure and native text, while RapidOCR handles optical character recognition for scanned image pages. They operate conditionally in a pipeline sequence with zero redundant execution.
