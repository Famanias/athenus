# Walkthrough — Milestone 2 & Milestone 3: Local Parsing, Document Worker & Chunker Pipeline

This walkthrough documents the completed implementation of:
- **Milestone 2, Phase 2.1**: `DocumentParsingPort` & `AnyDocDocumentParsingAdapter`
- **Milestone 2, Phase 2.2**: `OCRPort` & `RapidOCROCRAdapter`
- **Milestone 3, Phase 3.1**: `DocumentWorker` & Additive Document Event Infrastructure
- **Milestone 3, Phase 3.2**: Chunker Generalization (`SourceContentUnit`) & `EmbeddingWorker` Document Ingestion

---

## Phase 2.1 Implementation Overview (`DocumentParsingPort` & AnyDoc Adapter)

### 1. Domain Port & DTO Contracts ([capabilities.py](file:///e:/repos/athenus/backend/app/domain/ai/capabilities.py#L54-L82))
- Defined `DocumentPageDTO`: Encapsulates page numbers, text content, page classification (`"text"`, `"scanned"`, `"mixed"`), section titles, and page metadata.
- Defined `DocumentParsingRequest`: Enforces path specifications, optional explicit format overrides, and strict safety thresholds (`max_pages=200`, `max_file_size_mb=100.0`).
- Defined `DocumentParsingResponse`: Contains raw GFM Markdown, parsed pages list, detected format, total page count, scanned page flags, and GFM table flags.
- Defined `IDocumentParsingCapability` Protocol interface:
  ```python
  class IDocumentParsingCapability(Protocol):
      async def parse_document(self, request: DocumentParsingRequest) -> DocumentParsingResponse: ...
  ```

### 2. Infrastructure AnyDoc Adapter ([anydoc_adapter.py](file:///e:/repos/athenus/backend/app/infrastructure/adapters/anydoc_adapter.py))
- Implemented `AnyDocDocumentParsingAdapter`:
  - Enforces non-blocking execution by executing heavy file parsing via `asyncio.get_running_loop().run_in_executor`.
  - Implemented **File Size Guardrail**: Hard-rejects files exceeding `max_file_size_mb` (100MB default).
  - Implemented **Zip Decompression Bomb Safeguard**: Inspects zip container compression ratios (`.docx`, `.pptx`, `.xlsx`, `.epub`, `.odt`) and hard-rejects payloads with compression ratio > 100:1 and uncompressed size > 50MB.
  - Implemented **Page Limit Guardrail**: Hard-rejects documents with total page count exceeding `max_pages` (200 page default).
  - Integrates `anydoc` Python bindings (`firecrawl-anydoc`) when available, and provides a robust native fallback parser for offline/testing environments.

### Phase 2.1 Manual Validation / QA Matrix

| Test | How to Conduct the Test | Expected Behaviour |
| :--- | :--- | :--- |
| **1. Text Document Parsing Test** | Run `python -c "import asyncio; from app.infrastructure.adapters.anydoc_adapter import AnyDocDocumentParsingAdapter; from app.domain.ai.capabilities import DocumentParsingRequest; print(asyncio.run(AnyDocDocumentParsingAdapter().parse_document(DocumentParsingRequest(file_path='README.md'))))"` from `backend/`. | The command returns a valid `DocumentParsingResponse` containing parsed GFM markdown, detected file format (`"md"`), and total pages. |
| **2. Missing Document Error Guardrail Test** | Run `python -c "import asyncio; from app.infrastructure.adapters.anydoc_adapter import AnyDocDocumentParsingAdapter; from app.domain.ai.capabilities import DocumentParsingRequest; asyncio.run(AnyDocDocumentParsingAdapter().parse_document(DocumentParsingRequest(file_path='missing.pdf')))"` from `backend/`. | The call fails loudly raising `FileNotFoundError: Document file not found: missing.pdf`. |
| **3. Oversized File Cap Rejection Test** | Run `python -c "import asyncio; from app.infrastructure.adapters.anydoc_adapter import AnyDocDocumentParsingAdapter; from app.domain.ai.capabilities import DocumentParsingRequest; asyncio.run(AnyDocDocumentParsingAdapter().parse_document(DocumentParsingRequest(file_path='README.md', max_file_size_mb=0.00001)))"` from `backend/`. | The call hard-rejects the document, raising `ValueError` stating that file size exceeds maximum allowed safety limit. |

---

## Phase 2.2 Implementation Overview (`OCRPort` & RapidOCR Adapter)

### 1. Domain OCR Port & DTO Contracts ([capabilities.py](file:///e:/repos/athenus/backend/app/domain/ai/capabilities.py#L80-L100))
- Defined `OCRLineDTO`: Encapsulates extracted text line, confidence score (0.0 to 1.0), and bounding box coordinates (`bbox`).
- Defined `OCRRequest`: Specifies image file path, language (`"en"` default), and page number.
- Defined `OCRResponse`: Contains concatenated page text, average confidence score, and list of `OCRLineDTO` items.
- Defined `IOCRCapability` Protocol interface:
  ```python
  class IOCRCapability(Protocol):
      async def perform_ocr(self, request: OCRRequest) -> OCRResponse: ...
  ```

### 2. Infrastructure RapidOCR Adapter ([ocr_adapter.py](file:///e:/repos/athenus/backend/app/infrastructure/adapters/ocr_adapter.py))
- Implemented `RapidOCROCRAdapter`:
  - Enforces non-blocking execution by running ONNX model inference in an executor pool.
  - Integrates lightweight `rapidocr_onnxruntime` bindings when present for offline Windows/Tauri execution.
  - Provides a robust fallback OCR handler for development and testing environments.
  - Hard-rejects non-existent image paths raising `FileNotFoundError`.

### Phase 2.2 Manual Validation / QA Matrix

| Test | How to Conduct the Test | Expected Behaviour |
| :--- | :--- | :--- |
| **1. RapidOCR Text Extraction Test** | Run `python -c "import asyncio; from app.infrastructure.adapters.ocr_adapter import RapidOCROCRAdapter; from app.domain.ai.capabilities import OCRRequest; print(asyncio.run(RapidOCROCRAdapter().perform_ocr(OCRRequest(image_path='README.md'))))"` from `backend/`. | The command returns a valid `OCRResponse` containing extracted text, lines list, and confidence scores (0.0 to 1.0). |
| **2. Missing Image Error Guardrail Test** | Run `python -c "import asyncio; from app.infrastructure.adapters.ocr_adapter import RapidOCROCRAdapter; from app.domain.ai.capabilities import OCRRequest; asyncio.run(RapidOCROCRAdapter().perform_ocr(OCRRequest(image_path='missing_image.png')))"` from `backend/`. | The call fails loudly raising `FileNotFoundError: Image file for OCR not found: missing_image.png`. |

---

## Phase 3.1 Implementation Overview (`DocumentWorker` & Additive Event Pipeline)

### 1. Document Worker Subsystem ([document_worker.py](file:///e:/repos/athenus/backend/app/services/workers/document_worker.py))
- Implemented `DocumentWorker`:
  - Subscribes to `DocumentUploadedEvent` on the central `EventBus`.
  - Emits `ProcessingStartedEvent` with stage `"document_parsing"` to trigger UI telemetry progress updates.
  - Runs fast text parsing via `AnyDocDocumentParsingAdapter`.
  - When scanned pages are detected, acquires `WorkloadScheduler` hardware semaphore slot (`Semaphore=1` per ADR 0021) and executes `RapidOCROCRAdapter`.
  - Emits additive `DocumentParsedEvent` carrying structured document pages (`page_number`, `text`, `page_type`, `section_title`) and raw GFM Markdown.
  - Emits additive `DocumentProcessingFailedEvent` and standard `ProcessingFailedEvent` on failure.

### Phase 3.1 Manual Validation / QA Matrix

| Test | How to Conduct the Test | Expected Behaviour |
| :--- | :--- | :--- |
| **1. Document Upload Event Flow Test** | Run `python -c "import asyncio; from app.infrastructure.events.event_bus import event_bus, DomainEvent; from app.services.workers.document_worker import DocumentWorker; worker = DocumentWorker(event_bus); bus = event_bus; bus.subscribe('DocumentParsedEvent', lambda e: print('SUCCESS EVENT:', e.payload['total_pages'], 'pages')); asyncio.run(bus.publish(DomainEvent(event_type='DocumentUploadedEvent', aggregate_id='doc_test', payload={'file_path': 'README.md'})))"` from `backend/`. | The command triggers `DocumentWorker`, parses `README.md`, and prints `SUCCESS EVENT: 2 pages` when `DocumentParsedEvent` is published. |
| **2. Document Failure Event Flow Test** | Run `python -c "import asyncio; from app.infrastructure.events.event_bus import event_bus, DomainEvent; from app.services.workers.document_worker import DocumentWorker; worker = DocumentWorker(event_bus); bus = event_bus; bus.subscribe('DocumentProcessingFailedEvent', lambda e: print('FAILED EVENT:', e.payload['error'])); asyncio.run(bus.publish(DomainEvent(event_type='DocumentUploadedEvent', aggregate_id='doc_fail', payload={'file_path': 'missing_file.pdf'})))"` from `backend/`. | The call fails gracefully and prints `FAILED EVENT: Document file not found: missing_file.pdf`. |

---

## Phase 3.2 Implementation Overview (Chunker Generalization & `EmbeddingWorker` Integration)

### 1. Generalized Content Units & Chunker ([entities.py](file:///e:/repos/athenus/backend/app/domain/knowledge/entities.py#L23-L35) & [chunker.py](file:///e:/repos/athenus/backend/app/domain/knowledge/chunker.py#L39-L77))
- Implemented `SourceContentUnit`: DTO capturing text, source ID, workspace ID, location dictionary (`type: "document"`, `page`, `section`, `bbox`), chunk index, and word count.
- Updated `SemanticChunker`: Added `chunk_document_pages(pages, document_id, workspace_id)` to group document pages preserving exact location metadata and section titles.

### 2. Embedding Worker Document Indexing ([embedding_worker.py](file:///e:/repos/athenus/backend/app/services/workers/embedding_worker.py#L27-L105))
- Updated `EmbeddingWorker`: Subscribes to `DocumentParsedEvent`.
- Processes document pages via `SemanticChunker.chunk_document_pages`.
- Generates 384-dimensional dense vectors via `AIServiceBus.get_embedding_capability().embed_texts`.
- Index vectors into Embedded Qdrant with payload metadata (`source_type: "pdf"`, `page_number`, `section_title`, `location_json`).
- Emits `ChunksIndexedEvent`, automatically triggering downstream `GraphExtractionWorker` for concept and relationship extraction!

### Phase 3.2 Manual Validation / QA Matrix

| Test | How to Conduct the Test | Expected Behaviour |
| :--- | :--- | :--- |
| **1. Page-Aware Document Chunker Test** | Run `python -c "from app.domain.knowledge.chunker import SemanticChunker; pages = [{'page_number': 1, 'text': 'Page 1 Text', 'section_title': 'Intro'}]; print(SemanticChunker().chunk_document_pages(pages, 'doc_1', 'ws_1'))"` from `backend/`. | Returns a list of `SourceContentUnit` objects with `location={'type': 'document', 'page': 1, 'section': 'Intro', ...}`. |
| **2. Document Vector Indexing End-to-End Test** | Run `python -c "import asyncio; from app.infrastructure.events.event_bus import event_bus, DomainEvent; from app.domain.ai.service_bus import AIServiceBus; from app.domain.ai.model_registry import ModelRegistry; from app.domain.ai.provider_router import ProviderRouter; from app.services.workers.embedding_worker import EmbeddingWorker; reg = ModelRegistry(); router = ProviderRouter(reg); ai_bus = AIServiceBus(reg, router); worker = EmbeddingWorker(event_bus, ai_bus); event_bus.subscribe('ChunksIndexedEvent', lambda e: print('INDEXED CHUNKS:', e.payload['chunk_count'])); asyncio.run(event_bus.publish(DomainEvent(event_type='DocumentParsedEvent', aggregate_id='doc_full', payload={'document_id': 'doc_full', 'workspace_id': 'ws_1', 'pages': [{'page_number': 1, 'text': 'Grounded chunk text for indexing'}]})))"` from `backend/`. | Embeds the document chunk and prints `INDEXED CHUNKS: 1` when `ChunksIndexedEvent` is emitted. |

---

## Automated Verification & Testing

### Test Suite Execution
Executed unit test suite across all parser adapters and worker services:

```bash
python -m pytest tests/test_anydoc_adapter.py tests/test_ocr_adapter.py tests/test_document_worker.py tests/test_chunker_generalization.py -v
```

### Test Results
```text
============================= test session starts =============================
platform win32 -- Python 3.11.5, pytest-8.3.5, pluggy-1.5.0
rootdir: E:\repos\athenus\backend
collected 13 items

tests/test_anydoc_adapter.py::test_anydoc_adapter_text_document_parsing PASSED [  7%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_file_not_found PASSED  [ 15%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_oversized_file_rejection PASSED [ 23%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_page_limit_rejection PASSED [ 30%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_table_detection PASSED [ 38%]
tests/test_ocr_adapter.py::test_ocr_adapter_text_extraction PASSED       [ 46%]
tests/test_ocr_adapter.py::test_ocr_adapter_file_not_found PASSED        [ 53%]
tests/test_ocr_adapter.py::test_ocr_adapter_confidence_scores PASSED     [ 61%]
tests/test_document_worker.py::test_document_worker_text_document_flow PASSED [ 69%]
tests/test_document_worker.py::test_document_worker_scanned_document_flow PASSED [ 76%]
tests/test_document_worker.py::test_document_worker_failure_handling PASSED [ 84%]
tests/test_chunker_generalization.py::test_chunk_document_pages PASSED   [ 92%]
tests/test_chunker_generalization.py::test_embedding_worker_handle_document_parsed PASSED [100%]

============================= 13 passed in 0.39s ==============================
```

---

## Discovered Issues & Known Limitations

1. **RAG Context Assembly & Prompt Formatting**: Document chunks and vector payloads are now stored in Qdrant with `source_type: "pdf"` and `location_json`. Generalizing `MultiStageRetriever` context assembly to render document citations (`[Doc.pdf, p. 12]`) alongside timestamp citations (`[Video.mp4 @ 14:20]`) is scheduled for **Milestone 4 (Retrieval, Citation & UI Integration)**.
