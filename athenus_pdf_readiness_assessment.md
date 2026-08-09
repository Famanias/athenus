# Athenus — Architecture Readiness Assessment for Generalized Document/PDF Ingestion

## Executive Summary

This readiness assessment evaluates the architectural preparedness of **Athenus Knowledge OS** for evolving from a video/audio-centric lecture ingestion platform into a generalized, multi-source learning OS with first-class PDF and document support.

### Key Assessment Findings
1. **Overall Architecture Readiness Verdict**: **`Mostly Ready — Minor Architectural Preparation Required`**
2. **Current Strengths**:
   - The AI Service Bus ([backend/app/main.py](file:///e:/repos/athenus/backend/app/main.py#L101-L114)) cleanly abstracts LLMs, STT, and embeddings, enabling easy addition of OCR or document parsing capabilities without touching downstream consumers.
   - Vector database infrastructure ([qdrant_adapter.py](file:///e:/repos/athenus/backend/app/infrastructure/adapters/qdrant_adapter.py)) already supports heterogeneous payload indexing and metadata filtering.
   - Downstream learning artifacts (Flashcards, Quizzes, Concept Masteries) already decouple artifact generation from direct video dependencies; they consume canonical text chunks, concept entities, and relations.
3. **Core Architectural Bottlenecks & Video Coupling**:
   - **Database Model**: `MediaItemTable` ([models.py](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py#L32)) assumes `media_type="video"` and `duration_seconds: float`. Chunks are stored in `TranscriptChunkTable` with mandatory `start_time` and `end_time`.
   - **Ingestion Pipeline**: Events are named `MediaUploadedEvent`, `TranscriptCompletedEvent`, `ChunksIndexedEvent` ([persistent_ingestion_queue.py](file:///e:/repos/athenus/backend/app/domain/ingestion/persistent_ingestion_queue.py#L107)), hardcoding an assumption of speech-to-text.
   - **Retrieval Layer**: `MultiStageRetriever` ([multi_stage_retriever.py](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py#L67-L70)) specifically extracts 30-second video playback windows and injects timestamp badges `[MM:SS - MM:SS]`.
4. **AnyDoc / Firecrawl Ecosystem Evaluation**:
   - AnyDoc ([E:\repos\anydoc](file:///E:/repos/anydoc)) is a ultra-fast (median 4.4ms), pure-Rust/Python parser supporting 14 office formats (Word, PPT, Excel, PDF).
   - **Critical Limitation for Athenus**: AnyDoc's local Rust/Python engine **does not perform OCR** on scanned/image-only PDFs. It returns `ConvertError::Unsupported` for scanned PDFs and delegates OCR to Firecrawl's hosted cloud API (`Firecrawl Parse`).
   - **Recommendation**: Firecrawl AnyDoc is recommended as the local text-based document parser, but MUST be paired with a local-first OCR engine (such as **PaddleOCR-VL** or **RapidOCR**) to handle scanned and mixed PDFs while maintaining Athenus's strict **local-first, offline-ready philosophy**.

---

## 1. Existing Architecture Reconstruction (Milestone 1)

### Component Hierarchy & Module Boundaries
Athenus follows clean Domain-Driven Design (DDD) layered with Hexagonal/Ports-and-Adapters boundaries:

```text
[ Frontend React / Vite / Tauri ]
               │
               ▼ REST API / Server-Sent Events (SSE)
[ Presentation Layer: FastAPI Routers ] (v1/media, v1/chat, v1/learning, v1/graph)
               │
               ▼ Event Bus & Workload Scheduler
[ Application & Domain Layer ]
   ├── Persistent Ingestion Queue Worker (Sequential hardware-constrained worker)
   ├── Workers: TranscriptWorker, EmbeddingWorker, GraphExtractionWorker, FlashcardWorker
   ├── Services: AIServiceBus, KnowledgeGraphService, ConceptMergingService, SettingsService
   └── Domain Entities: MediaItem, TranscriptChunk, Concept, Relation, Flashcard, Quiz
               │
               ▼ Ports & Infrastructure Adapters
[ Infrastructure Layer ]
   ├── Relational DB: SQLite via SQLModel / SQLAlchemy (models.py)
   ├── Vector Storage: Embedded Qdrant (qdrant_adapter.py)
   ├── AI Capabilities: Ollama, OpenRouter, Groq, OpenAI, Anthropic, Faster-Whisper, SentenceTransformers
   └── Storage / Local FS: ffmpeg, media directories
```

### Source Representation in Data Models
Currently, sources are tightly named after media assets:
- **`MediaItemTable`** ([models.py:32-44](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py#L32-L44)): Primary relational record representing an ingested asset (`id`, `workspace_id`, `title`, `file_path`, `media_type`, `file_size_bytes`, `duration_seconds`, `status`, `error_message`).
- **`TranscriptChunkTable`** ([models.py:46-57](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py#L46-L57)): Relational storage of chunked text (`id`, `media_id`, `workspace_id`, `text`, `start_time`, `end_time`, `chunk_index`, `word_count`).
- **`TranscriptSegmentTable`** ([models.py:59-65](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py#L59-L65)): Raw Whisper segment outputs (`id`, `media_id`, `start_time`, `end_time`, `text`).

---

## 2. Video/Audio Ingestion Deep Trace (Milestone 2)

### Current Ingestion Execution Flow
When a user uploads a video file, the system follows an asynchronous, event-driven sequential pipeline:

```text
1. User POST /api/v1/media/upload
   ↓
2. Save file to disk -> MediaItemTable created with status="pending"
   ↓
3. PersistentIngestionWorker.enqueue_media(media_id, workspace_id, file_path)
   ↓ (Job enqueued in ArtifactJobTable: artifact_type="ingestion", status="queued")
4. PersistentIngestionWorker.process_next_job() -> Publishes DomainEvent("MediaUploadedEvent")
   ↓
5. TranscriptWorker handles "MediaUploadedEvent"
   ├─► FFmpegAudioExtractor.extract_audio() -> 16kHz WAV
   ├─► AIServiceBus.get_stt_capability().transcribe() -> Faster-Whisper ASR
   └─► Publishes DomainEvent("TranscriptCompletedEvent")
   ↓
6. EmbeddingWorker handles "TranscriptCompletedEvent"
   ├─► SemanticChunker.chunk_transcript() -> 250-word sliding window chunks
   ├─► AIServiceBus.get_embedding_capability().embed_texts() -> SentenceTransformers (384-dim)
   ├─► SQLite TranscriptChunkTable persistence
   ├─► EmbeddedQdrantVectorStoreAdapter.upsert() -> Qdrant Collection
   └─► Publishes DomainEvent("ChunksIndexedEvent")
   ↓
7. GraphExtractionWorker handles "ChunksIndexedEvent"
   ├─► Extract concepts & relationships via LLM (or fallback heuristic)
   ├─► ConceptMergingService.resolve_concept() -> Vector-based deduplication & merging
   ├─► KnowledgeGraphService.add_relation() -> Network graph construction
   └─► Publishes DomainEvent("ConceptGraphUpdatedEvent")
   ↓
8. PersistentIngestionWorker handles "ConceptGraphUpdatedEvent"
   └─► Marks ingestion job "completed" (status="ready", progress=100) -> Processes next job
```

### Component Coupling & Reuse Analysis Table

| Component / Subsystem | Current Video/Audio Coupling | Reusable for Document / PDF? | Required Generalization |
| :--- | :--- | :--- | :--- |
| `PersistentIngestionWorker` | Low (Triggered by `MediaUploadedEvent`, fetches file path) | **Yes (90%)** | Rename event or add support for `SourceIngestionEvent`. Queueing logic is completely reusable. |
| `TranscriptWorker` | High (Uses FFmpeg audio extraction and Faster-Whisper ASR) | **No (0%)** | Keep as Video/Audio-specific worker. Introduce `DocumentWorker` alongside it. |
| `SemanticChunker` | Medium (Expects `TranscriptSegmentDTO` with `start_time` / `end_time`) | **Yes (70%)** | Generalize chunker interface to accept `SourceContentDTO` with either timestamps or page numbers/sections. |
| `EmbeddingWorker` | Medium (Subscribes to `TranscriptCompletedEvent`, payload contains `start_time`/`end_time`) | **Yes (85%)** | Generalize event to `SourceContentExtractedEvent` carrying generic `location` metadata. |
| `QdrantAdapter` | Low (Payload payload includes `media_id`, `start_time`, `end_time`) | **Yes (95%)** | Extend payload schema to support `page_number`, `section_title`, `source_type`. Vector size (384) is completely source-agnostic. |
| `GraphExtractionWorker` | Low (Subscribes to `ChunksIndexedEvent`, loads chunks by ID) | **Yes (95%)** | Fully reusable. Concept & relation extraction operates on text chunks regardless of source modality. |
| `FlashcardWorker` / `QuizWorker` | Low (Generates cards/quizzes from canonical concepts & chunks) | **Yes (100%)** | Fully reusable. Downstream artifact generation is already modality-agnostic. |

---

## 3. Data & Vector Architecture Readiness (Milestone 3)

### Relational Schema Extensibility
- **`MediaItemTable`**: Currently holds `media_type: str = "video"` and `duration_seconds: float = 0.0`. Can be extended with `total_pages: Optional[int]`, `author: Optional[str]`, or generalized into `LearningSourceTable`.
- **`TranscriptChunkTable`**: Currently assumes `start_time` and `end_time`. For documents, `start_page` and `end_page` or `section_title` are required.
- **`KnowledgeConceptTable` & `FlashcardTable` & `QuizQuestionTable`**: Already contain generic provenance fields: `media_id`, `source_chunk_ids`, `start_time`, `end_time`. Replacing/augmenting `start_time`/`end_time` with a unified `location_json` or adding `page_number` allows instant compatibility across all learning artifacts!

### Qdrant Vector Payload Schema
Currently, [qdrant_adapter.py:86-97](file:///e:/repos/athenus/backend/app/infrastructure/adapters/qdrant_adapter.py#L86-L97) stores:
```json
{
  "chunk_id": "chunk_123",
  "media_id": "media_456",
  "workspace_id": "ws_789",
  "text": "Extracted text content...",
  "start_time": 12.5,
  "end_time": 45.0,
  "chunk_index": 0
}
```
**Vector/Data Readiness Answer**:
> **YES.** Athenus can ALREADY store heterogeneous learning-source chunks in Qdrant without redesigning the collection or vector model (size=384, COSINE distance). By adding optional metadata fields (`source_type: "pdf"`, `page_number: 12`, `section_title: "Neural Networks"`), Qdrant indexing and payload filtering will immediately support mixed-modality retrieval.

---

## 4. PDF / Document Ingestion Compatibility & Parser Evaluation (Milestone 4)

### Parser Technical Comparison Matrix

| Criteria | Firecrawl AnyDoc (Local Engine) | Firecrawl AnyDoc (Hosted API) | Docling (IBM) | PyMuPDF (fitz) | PaddleOCR / RapidOCR |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Execution Mode** | Local Rust / Python | Cloud REST API | Local Python / C++ | Local Python / C | Local Python / ONNX |
| **Local-First & Offline** | **100% Yes** | No (Cloud API dependency) | **100% Yes** | **100% Yes** | **100% Yes** |
| **Speed / Overhead** | **Ultra-Fast (4.4ms)** | Network Latency (1-3s) | Heavy (500ms - 2s/page) | **Fast (10-30ms)** | Medium (100-300ms/page) |
| **Text PDF Support** | Excellent (via pdf-inspector) | Excellent | Excellent | Excellent | N/A (Image OCR only) |
| **Scanned PDF Support** | **NO (Returns Error)** | Excellent (Cloud OCR) | Excellent (Built-in OCR) | No (Pure layout text) | **Excellent (Local OCR)** |
| **Table Structure** | Excellent (GFM Tables) | Excellent | Excellent (Docling JSON) | Basic | Good (Table Rec) |
| **Page Provenance** | Good (Page breaks) | Good | Excellent (BBoxes/Pages) | Excellent (Rects/Pages) | Good (Line BBoxes) |
| **License** | MIT | Proprietary Hosted Service | MIT | AGPL v3 (License Risk) | Apache 2.0 |
| **Athenus Fit** | **Primary Local Text Parser** | Not Recommended (Cloud) | Heavy Fallback | Licensing Risk | **Primary Local OCR Engine** |

### Recommended Hybrid Parsing Strategy for Athenus
To maintain Athenus's **local-first philosophy** while handling all 3 PDF types:

```text
Incoming PDF Document
        │
        ▼
PDF Type Classifier (Fast PyMuPDF / AnyDoc inspection)
        │
        ├── Type A: Native Text PDF ──────────► AnyDoc Local Rust Engine -> GFM Markdown + Structural Trees
        │
        ├── Type B: Scanned Image PDF ────────► RapidOCR / PaddleOCR ONNX -> Page Layout Text + Bounding Boxes
        │
        └── Type C: Mixed PDF ────────────────► Page-by-Page Dispatcher:
                                                  - Text pages -> AnyDoc
                                                  - Image pages -> RapidOCR
```

---

## 5. Generalized Learning-Source Architecture (Milestone 5)

### Recommended Abstraction Taxonomy

```text
                        ┌────────────────────────┐
                        │     LearningSource     │ (Unified DB Entity)
                        └───────────┬────────────┘
                                    │
           ┌────────────────────────┴────────────────────────┐
           ▼                                                 ▼
┌──────────────────────┐                          ┌──────────────────────┐
│  MediaSource (Video) │                          │  DocumentSource(PDF) │
└──────────┬───────────┘                          └──────────┬───────────┘
           │                                                 │
           ▼                                                 ▼
┌──────────────────────┐                          ┌──────────────────────┐
│  Audio & Transcript  │                          │ AnyDoc / RapidOCR    │
└──────────┬───────────┘                          └──────────┬───────────┘
           │                                                 │
           └────────────────────────┬────────────────────────┘
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │   SourceContentUnit    │ (Normalized Representation)
                        └───────────┬────────────┘
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │    Semantic Chunker    │
                        └───────────┬────────────┘
                                    │
                                    ▼
                        ┌────────────────────────┐
                        │ Qdrant Vector Payload  │ (Heterogeneous Storage)
                        └────────────────────────┘
```

### Generalization Decision Boundaries

| Subsystem | MUST Generalize Now | SHOULD Generalize Later | Keep Modality-Specific | DO NOT TOUCH |
| :--- | :--- | :--- | :--- | :--- |
| **Database Entities** | Add `source_type`, `location_json` to Chunks/Artifacts. | Refactor `MediaItemTable` into `LearningSourceTable`. | Keep video-specific fields (`duration_seconds`, `media_type`). | `SystemSettings`, `WorkspaceTable`, `ChatSessionTable`. |
| **Ingestion Events** | Standardize `SourceContentIndexedEvent` for downstream workers. | Refactor persistent queue worker event names. | Keep `FFmpegAudioExtractor` and Whisper ASR worker intact. | `AIServiceBus` provider registry and routing logic. |
| **Retrieval Engine** | Extend `MultiStageRetriever` filter logic to support document filtering. | Add section-aware & page-range expansion in retrieval. | Keep 30s video timestamp context extractor for video sources. | BM25 sparse index scoring and CrossEncoder reranker. |
| **Learning Artifacts** | Ground Flashcards and Quizzes using generic chunk provenance. | Add page-number citations to quiz question explanations. | Keep timestamp playback links in UI for video sources. | SM-2 spaced-repetition algorithm implementation (`sm2.py`). |

---

## 6. Unified Retrieval & Future RAG Architecture (Milestone 6)

### Multi-Stage Unified Retrieval Pipeline

```text
User Question: "What are the three main causes of inflation in lecture materials?"
                                  │
                                  ▼
Stage 1: Query Expansion & Intent Detection
                                  │
                                  ▼
Stage 2: Active Context Sensing (Detects if user is on Video @ 04:12 OR PDF @ Page 18)
                                  │
                                  ▼
Stage 3: Hybrid Search (Embedded Qdrant + BM25 Sparse Index)
         ┌───────────────────────────────────────────────────────────┐
         │ Filters: workspace_id, optional source_ids / source_types │
         └─────────────────────────────┬─────────────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
Video Transcript Chunks       PDF Document Chunks         Knowledge Graph Triples
(Source: Video #1, MM:SS)     (Source: PDF #2, Page 14)   (Concepts: Inflation, Supply)
         └─────────────────────────────┼─────────────────────────────┘
                                       │
                                       ▼
Stage 4: Cross-Encoder Reranking & Context Compression
                                       │
                                       ▼
Stage 5: Traceable Citation Context Assembly
```

### Traceable Citation Model Strategy
To enable seamless UI citations across all source types:

```markdown
[Unified Context Payload]
Source 1 (Video): "Macroeconomics 101.mp4", Timestamp: 14:20 - 16:05
Excerpt: "...demand-pull inflation occurs when aggregate demand exceeds supply..."

Source 2 (PDF): "Economic_Theory.pdf", Page 42, Section 3.1 "Monetary Policy"
Excerpt: "...cost-push inflation is driven by supply shocks in key commodities..."

Answer:
The three main causes discussed are:
1. Demand-pull inflation ([Macroeconomics 101.mp4 @ 14:20](file:///media/1#t=860)).
2. Supply shock cost-push inflation ([Economic_Theory.pdf, p. 42](file:///docs/2#page=42)).
```

---

## 7. Gap Analysis & Readiness Scoring (Milestone 7)

### Categorized System Gaps
- **CRITICAL (Must Address Before PDF Support)**:
  1. No document parsing worker or backend PDF file validation.
  2. Database models lack `page_number` / `section_title` fields on chunks and concept grounding.
  3. UI chat citation renderer only supports `[MM:SS]` timestamp regexes.
- **IMPORTANT (Should Address for Robustness)**:
  1. Event Bus events are named explicitly after media (`MediaUploadedEvent`, `TranscriptCompletedEvent`).
  2. `MultiStageRetriever` context window extraction is hardcoded to query `TranscriptSegmentTable`.
- **OPTIONAL (Nice to Have)**:
  1. OCR bounding-box highlight rendering on PDF canvas in Tauri frontend.
  2. Hierarchical document section indexing.
- **DO NOT CHANGE**:
  1. `AIServiceBus` and model provider architecture.
  2. Embedded Qdrant vector database initialization and cosine index.
  3. `KnowledgeGraphService`, `ConceptMergingService`, and SM-2 spaced repetition engine.

### Readiness Scoring Matrix

| Assessment Area | Score (0-100) | Empirical Codebase Justification |
| :--- | :---: | :--- |
| **Overall Architecture Readiness** | **82 / 100** | High DDD modularity; AI service bus and vector DB fully abstracted. Minor entity extensions needed. |
| **Source Abstraction** | **65 / 100** | Database models currently hardcode `MediaItemTable` with video durations and speech transcript chunks. |
| **Ingestion Pipeline** | **78 / 100** | Event-driven sequential queue worker is 90% reusable; needs `DocumentWorker` addition. |
| **Database Readiness** | **75 / 100** | SQLModel schema uses `media_id` and timestamp fields; easy to add page/location columns without breaking migrations. |
| **Qdrant / Vector Readiness** | **95 / 100** | Collection size (384), Cosine distance, and payload upsert mechanisms are 100% source-agnostic. |
| **Embedding Pipeline** | **95 / 100** | `SentenceTransformersEmbeddingAdapter` embeds raw string batches; completely independent of modality. |
| **Artifact Generation** | **90 / 100** | Flashcards and Quizzes are generated from canonical concepts and text chunks, not raw video files. |
| **RAG Readiness** | **80 / 100** | Multi-stage retriever exists and ranks dense/sparse hits; needs context assembly generalization. |
| **Citation / Provenance** | **70 / 100** | Grounding metadata exists on entities (`source_chunk_ids`); needs page number payload formatting. |
| **Testing Readiness** | **72 / 100** | Backend test suite covers workers and database models; unit tests needed for document parsers. |
| **Local-First Compatibility** | **95 / 100** | Architecture runs completely local (SQLite, Embedded Qdrant, Ollama, Faster-Whisper, SentenceTransformers). |
| **Overall PDF Readiness** | **78 / 100** | Excellent foundation. Adding AnyDoc + RapidOCR and extending chunk schemas yields instant PDF capability. |

---

## 8. Recommended Implementation Plan & Staged Roadmap (Milestone 8)

```text
Phase 1: Database & Entity Foundation (Non-Breaking Extensions)
├── Add optional `page_number`, `section_title`, and `source_type` columns to database models
└── Ensure SQLModel migrations preserve backward compatibility for existing video assets.

Phase 2: Local Document Parsing Subsystem
├── Integrate AnyDoc local Python binding (`firecrawl-anydoc`) for text-based PDFs and office docs
└── Integrate RapidOCR (ONNX runtime) for offline local scanned PDF page OCR.

Phase 3: Document Ingestion Worker & Normalization Pipeline
├── Create `DocumentWorker` listening to `DocumentUploadedEvent`
├── Implement `DocumentChunker` producing standardized `SourceContentUnit` DTOs
└── Upsert document chunks into Embedded Qdrant with `source_type: "pdf"` metadata.

Phase 4: Unified Retrieval & Multi-Source RAG Context Assembly
├── Update `MultiStageRetriever` to extract both video playback and active PDF page context
└── Update citation formatting to emit traceable PDF page links (`[Doc.pdf, p. 12]`).

Phase 5: UI & Learning Artifact Integration
├── Update Tauri/React frontend to support PDF file upload and document viewing
└── Ensure Flashcards, Quizzes, and Knowledge Graph seamlessly display document provenance.
```

---

## Final Recommendation & Verdict

> **VERDICT: `Mostly Ready — Minor Architectural Preparation Required`**

### Summary Justification
Athenus possesses an exceptionally clean, modular architecture. The **AI Service Bus**, **Embedded Qdrant Adapter**, **Event Bus**, and **Knowledge Graph & Artifact Generation Services** are already 85-100% ready for generalized learning sources.

The required preparation is strictly non-breaking:
1. Augment database chunk and provenance schemas with page/location metadata.
2. Add a local-first `DocumentWorker` pairing AnyDoc (for fast text parsing) with RapidOCR (for offline scanned page OCR).
3. Extend the RAG prompt assembler to output document citations alongside timestamp citations.

No architectural rewrites are required. PDF support can be delivered cleanly and incrementally.

---

## 18. Supported File Types & Architectural Revision Classification Matrix

This matrix categorizes file types into three tiers based on Athenus's current architecture and proposed extensions:

### Tier 1: Supported with Little to No Code Revisions
*File types natively handled by the existing FFmpeg + Faster-Whisper ASR pipeline or direct text ingestion with zero structural modifications:*

| File Category | Extensions | Underlying Processing Engine | Extensibility Impact |
| :--- | :--- | :--- | :--- |
| **Video Files** | `.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.m4v` | FFmpeg Audio Extraction + Faster-Whisper ASR | **0 Revisions** (Already supported natively) |
| **Audio Files** | `.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`, `.ogg`, `.opus`, `.wma` | Faster-Whisper ASR Direct Processing | **0 Revisions** (Already supported natively) |
| **Plain Text / Subtitles** | `.txt`, `.srt`, `.vtt` | Direct Semantic Chunker Intake | **Minimal** (Simple file upload extension whitelist) |

---

### Tier 2: Supported with Minor Code Revisions
*File types supported cleanly by adding the proposed `DocumentWorker` + AnyDoc Python parser (`firecrawl-anydoc`) + minor SQLModel schema page metadata extensions:*

| File Category | Extensions | Underlying Processing Engine | Required Architectural Addition |
| :--- | :--- | :--- | :--- |
| **Text-based PDFs** | `.pdf` (Native selectable text) | AnyDoc (`pdf-inspector` Rust Core) | `DocumentWorker` + `page_number` DB column |
| **Word Documents** | `.docx`, `.doc`, `.docm` | AnyDoc Rust Engine | `DocumentWorker` (Converts to GFM Markdown) |
| **PowerPoint Presentations** | `.pptx`, `.ppt`, `.pps`, `.pot`, `.pptm`, `.ppsx`, `.ppsm` | AnyDoc Rust Engine | `DocumentWorker` (Converts slides to structured Markdown) |
| **Excel Spreadsheets** | `.xlsx`, `.xls`, `.xlsm`, `.xlsb` | AnyDoc (`calamine` Rust Core) | `DocumentWorker` (Converts sheets to GFM Tables) |
| **OpenDocument Formats** | `.odt`, `.ods`, `.odp` | AnyDoc Rust Engine | `DocumentWorker` (Direct GFM Markdown pipeline) |
| **Rich Text & eBooks** | `.rtf`, `.epub` | AnyDoc Rust Engine | `DocumentWorker` (Direct GFM Markdown pipeline) |
| **Structured Tables & Data** | `.csv`, `.tsv` | AnyDoc (`csv` Rust Core) / Python `csv` | `DocumentWorker` (Direct table chunking) |
| **Markdown / Web Documents** | `.md`, `.markdown`, `.html`, `.htm` | Native GFM Parser / BeautifulSoup | `DocumentWorker` (Heading-based structural chunking) |

---

### Tier 3: Not Supported (Requires Major Code Revisions)
*File types that require major architectural additions, new ML models, visual rendering pipelines, or custom runtime environments:*

| File Category | Extensions | Why Major Revisions Are Required | Architectural Prerequisite |
| :--- | :--- | :--- | :--- |
| **Scanned / Image-Only PDFs** | `.pdf` (Scanned without text layer) | AnyDoc returns `Unsupported` error; requires integrated local OCR layout engine | Local ONNX OCR Engine (`RapidOCR` / `PaddleOCR-VL`) |
| **Standalone Images & Diagrams** | `.jpg`, `.jpeg`, `.png`, `.webp`, `.svg`, `.bmp`, `.tiff` | Requires Vision-Language Multimodal models (VQA / OCR / Diagram extraction) | Local Multimodal VLM Adapter (`Qwen2-VL` / `MiniCPM-V`) |
| **CAD & Engineering Models** | `.dwg`, `.dxf`, `.step`, `.igs` | Proprietary binary geometry vectors requiring specialized rendering engines | Custom CAD parsing software & 3D mesh extractor |
| **Executables & Binaries** | `.exe`, `.dll`, `.so`, `.bin`, `.wasm`, `.class` | Binary machine code requiring disassemblers / decompiler AST frameworks | Reverse engineering framework (`Ghidra` / `Radare2`) |
| **Archive Packages** | `.zip`, `.tar.gz`, `.7z`, `.rar` | Requires multi-file unpackers, recursive file traversal, and batch queuing | Recursive Archive Extraction Service |
| **Code Repositories & Notebooks** | `.ipynb`, `.py`, `.js`, `.rs`, `.cpp`, `.go` | Requires Tree-Sitter AST parsers, code chunking, and code-specific embeddings | Code Graph AST Parser & Code Vector Embedder |

