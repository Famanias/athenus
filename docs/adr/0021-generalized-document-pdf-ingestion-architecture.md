# ADR 0021: Generalized Document & PDF Ingestion Architecture

- **Status**: Approved (Finalized & Implementation-Ready)
- **Date**: 2026-08-09
- **Deciders**: Athenus Architecture Team

## Context & Problem Statement

Athenus was originally designed around video/audio lecture ingestion. To support first-class PDF and multi-format document ingestion (text-based PDFs, scanned PDFs, Word, PowerPoint, Excel, OpenDocument, EPUB, CSV) without breaking existing video functionality or violating local-first constraints, we required a clear, validated architectural design.

## Decision Drivers

1. **Local-First & Offline Privacy**: The application must run 100% offline on local hardware (Windows/Tauri desktop) without requiring cloud OCR or parsing APIs.
2. **Unified Data & Citation Representation**: Provenance and locations across videos, PDFs, and documents must be represented uniformly to avoid permanent dual-branching across database models, vector search, retrieval, and UI citation components.
3. **Resource-Bounded Concurrency**: Ingestion queue scheduling must prevent hardware lockups (RAM/VRAM thrashing and OOM crashes) on unconstrained user desktop environments while enabling fast document processing.
4. **License Compliance**: Avoid dependencies with AGPL restrictions (e.g. PyMuPDF).

## Decided Architectural Choices

### 1. Unified Provenance Schema (`location_json`)
* **Decision**: Add a single `location_json` structured field to database tables (`TranscriptChunkTable`, `KnowledgeConceptTable`, `FlashcardTable`, `QuizQuestionTable`) rather than adding separate nullable columns (`start_page`, `end_page`, `section_title`) alongside `start_time`/`end_time`.
* **Format**:
  * Video location: `{"type": "video", "start_time": 14.2, "end_time": 45.0}`
  * Document location: `{"type": "document", "page": 12, "section": "3.1 Inflation", "bbox": null}`
* **Bounding Box (`bbox`) Policy**: `bbox` is included as a nullable schema field (`Optional[Tuple[float, float, float, float]]`) for forward compatibility, but **`bbox` computation is explicitly deferred** until PDF canvas highlight rendering is scheduled in the UI. Parsers will emit `bbox: null` for initial MVP.

### 2. Document Parser & OCR Engine Selection
* **Text Parser**: Integrate **Firecrawl AnyDoc** (via local Rust/Python `firecrawl-anydoc` bindings) for native text-based PDFs, Office documents, and spreadsheets.
* **Page Classification**: Use AnyDoc's built-in `pdf-inspector` for native per-page PDF classification (`TextBased`, `Scanned`, `ImageBased`, `Mixed`) to avoid custom classifiers or PyMuPDF dependencies.
* **Scanned OCR Engine**: Route scanned PDF pages and standalone photographed text pages to **RapidOCR (ONNX Runtime)** for lightweight, standalone local offline OCR on Windows without heavy deep learning framework overhead (e.g. raw PaddlePaddle).
* **OCR Language Coverage**: Bundled ONNX models default to English and standard Latin script (`en_PP-OCRv4` / `ch_PP-OCRv4` ~15MB). Additional language packs are explicitly deferred.

### 3. Resource-Bounded Queue Scheduling & Heavy Path Isolation
* **Queue Investigation Finding**: `PersistentIngestionWorker` uses `asyncio.Lock()` specifically to bound CPU/VRAM usage and prevent hardware lockups during heavy Whisper ASR and embedding passes.
* **Decision**: Implement a **Resource-Bounded Dual-Path Scheduler**:
  * **Fast Text Path**: AnyDoc text-based conversions (median 4.4ms) execute immediately in lightweight CPU worker threads without acquiring heavy ML locks.
  * **Heavy ML Path**: Heavy RapidOCR ONNX passes and Faster-Whisper ASR passes share a single global ML hardware semaphore default of **`asyncio.Semaphore(max_concurrent_tasks=1)`**. This guarantees strictly one heavy ML task (either Whisper speech ASR or RapidOCR ONNX image pass) executes at a time, preserving full hardware safety on low-end or CPU-only desktop systems.
  * **Future Optimization Gate**: Raising the heavy ML semaphore from 1 to 2 is explicitly gated behind future hardware auto-detection (e.g. verifying dedicated GPU VRAM for Whisper while RapidOCR runs on a separate CPU worker pool).
* **Progress Tracking**: Support granular per-page progress updates in `ArtifactJobTable`.

### 4. Comprehensive Ingestion Guardrails & Product Over-Cap Policy
* **Decision**: Enforce strict safety guardrails on all document uploads:
  * File size cap: 100MB
  * Page count cap: 200 pages per document (local desktop safety limit)
  * Zip decompression ratio checks for `.docx`, `.pptx`, `.epub`, `.odt` to prevent zip-bomb attacks.
* **Product Behavior on Over-Cap Files**: Documents exceeding 100MB or 200 pages are **hard-rejected during the validation stage** with `status: "failed"`, `stage: "validation"`, and an explicit error message: *"Document exceeds safety limit (200 pages / 100MB)."* Partial ingestion is rejected to prevent corrupt chunk states; the UI will present an actionable prompt allowing users to split the file before re-uploading.

### 5. Deferred Scope Declarations
* **Document Versioning & Re-uploads**: *Deliberately deferred*. Re-uploading an existing file creates a distinct document asset (`id: doc_xxx`), preserving existing grounded chunks and concept pointers.
* **Hierarchical Section Indexing**: *Deliberately deferred*. Initial MVP chunks documents using page boundaries and heading anchors.

### 6. Interactive Citation Deep-Linking
* **Decision**: `MultiStageRetriever` returns structured location metadata. The chat interface renders document citations as interactive links (e.g. `[Economic_Report.pdf, p. 12]`) that open the integrated Tauri PDF viewer directly at the cited page.

## Consequences

* **Positive**:
  * Zero breaking changes to existing video ingestion pipelines.
  * Strict single-slot heavy ML semaphore (`Semaphore=1`) guarantees 100% protection against CPU/VRAM thrashing and OOM crashes on unconstrained desktop environments.
  * Fast text documents (4ms median) bypass heavy locks and process instantly.
  * 100% offline, local-first compliance with lightweight binary packaging.
  * Clean, unified RAG retrieval and citation engine across all source types.
* **Negative / Risks**:
  * Requires adding RapidOCR ONNX model assets (~15MB) to the application runtime bundle.
  * MultiStageRetriever requires updating prompt assembly templates for mixed-source context.
