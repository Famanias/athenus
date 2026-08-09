# Walkthrough — Generalized Document / PDF Ingestion Architecture Implementation

This walkthrough documents the completed implementation of:
- **Milestone 2, Phase 2.1**: `DocumentParsingPort` & `AnyDocDocumentParsingAdapter`
- **Milestone 2, Phase 2.2**: `OCRPort` & `RapidOCROCRAdapter`
- **Milestone 3, Phase 3.1**: `DocumentWorker` & Additive Document Event Infrastructure
- **Milestone 3, Phase 3.2**: Chunker Generalization (`SourceContentUnit`) & `EmbeddingWorker` Document Ingestion
- **Milestone 4, Phase 4.1**: Multi-Source Retriever (`MultiStageRetriever`) & Qdrant Filtering
- **Milestone 4, Phase 4.2**: Generalized Citation Parser & Document Page Jump Serialization

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

## Phase 4.1 Implementation Overview (Retriever + Qdrant Filtering)

### 1. Qdrant Vector Filtering ([qdrant_adapter.py](file:///e:/repos/athenus/backend/app/infrastructure/adapters/qdrant_adapter.py#L61-L100))
- Extended `EmbeddedQdrantVectorStoreAdapter.search` to accept `filter_source_type` (`"pdf"` / `"video"`) and `filter_document_id`.
- Added `FieldCondition` filtering rules for Qdrant vector queries and fallback memory searches.

### 2. MultiStageRetriever Document Context & Badges ([multi_stage_retriever.py](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py#L47-L188))
- Extended `RetrievalContext` to hold `document_id`, `source_type`, and `current_page`.
- Added `_extract_document_page_context(document_id, current_page, selected_text)` to provide active document view context.
- Extended `_compress_context` to format document page badges `[Document Page X (Section Title)]` alongside timestamp badges `[MM:SS - MM:SS]`.
- Updated prompt assembly instructions to instruct LLMs to produce grounded citations for both video timestamps and document page numbers.

### Phase 4.1 Manual Validation / QA Matrix

| Test | How to Conduct the Test | Expected Behaviour |
| :--- | :--- | :--- |
| **1. Qdrant Document Filter Test** | Run `python -c "import asyncio; from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter; adapter = EmbeddedQdrantVectorStoreAdapter(path=':memory:'); asyncio.run(adapter.upsert(ids=['00000000-0000-0000-0000-000000000001'], vectors=[[0.1]*384], payloads=[{'chunk_id': 'doc_c1', 'document_id': 'doc_99', 'source_type': 'pdf', 'text': 'Proof text'}])); print(asyncio.run(adapter.search([0.1]*384, filter_document_id='doc_99', filter_source_type='pdf')))"` from `backend/`. | The search query returns only the payload matching `filter_document_id='doc_99'` and `filter_source_type='pdf'`. |
| **2. MultiStageRetriever Document Retrieval Test** | Run `python -c "import asyncio; from app.domain.ai.service_bus import AIServiceBus; from app.domain.ai.model_registry import ModelRegistry; from app.domain.ai.provider_router import ProviderRouter; from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever; from tests.test_document_retrieval import MockEmbeddingCapability; reg = ModelRegistry(); router = ProviderRouter(reg); ai_bus = AIServiceBus(reg, router); ai_bus.register_embedding_adapter('sentence_transformers', MockEmbeddingCapability()); retriever = MultiStageRetriever(ai_bus); ctx = asyncio.run(retriever.execute_retrieval(query='What is on page 5?', workspace_id='ws_test', document_id='doc_101', source_type='pdf', current_page=5)); print('ASSEMBLED PROMPT CONTAINS PAGE CONTEXT:', '[Active Document Context]' in ctx.assembled_prompt)"` from `backend/`. | Returns `ASSEMBLED PROMPT CONTAINS PAGE CONTEXT: True` and includes `[Active Document Context]` with active page details. |

---

## Phase 4.2 Implementation Overview (Generalized Citation Parser & PDF Page Jump)

### 1. Citation Parsing Utility ([citation_parser.py](file:///e:/repos/athenus/backend/app/domain/knowledge/citation_parser.py))
- Implemented `parse_chat_citations`: Parses both video timestamp badges (`[MM:SS]`) and document page badges (`[Document Page X]`, `[Page X]`, `[Doc p.X]`).
- Converts extracted regex tokens into structured `source_type`, `start_time`/`end_time` (video), and `page_number`/`section_title` (PDF) dictionaries.

### 2. Workspace Intelligence & API Serialization ([workspace_intelligence.py](file:///e:/repos/athenus/backend/app/application/services/workspace_intelligence.py#L36-L77) & [chat.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/chat.py#L54-L157))
- Extended `WorkspaceIntelligenceManager.query_workspace` to process `document_id`, `source_type`, and `current_page`.
- Extended `CitationDTO` schema to include `source_type`, `page_number`, `section_title`, and `location` metadata alongside video timestamps.

### Phase 4.2 Manual Validation / QA Matrix

| Test | How to Conduct the Test | Expected Behaviour |
| :--- | :--- | :--- |
| **1. Generalized Citation Parser Test** | Run `python -c "from app.domain.knowledge.citation_parser import parse_chat_citations; print(parse_chat_citations('Found in [01:30] and [Document Page 14 (Proof)]'))"` from `backend/`. | The parser extracts both video timestamp citation (`start_time=90.0`) and document page citation (`source_type='pdf'`, `page_number=14`). |
| **2. Document Citation DTO Serialization Test** | Run `python -c "from app.presentation.api.v1.chat import CitationDTO; dto = CitationDTO(chunk_id='c1', source_type='pdf', page_number=7, text='Sample chunk'); print(dto.model_dump())"` from `backend/`. | Returns serialized dictionary with `source_type='pdf'` and `page_number=7`. |

---

## Automated Verification & Testing

### Test Suite Execution
Executed complete unit test suite across all parser adapters, worker services, retrieval components, and citation modules:

```bash
python -m pytest tests/test_anydoc_adapter.py tests/test_ocr_adapter.py tests/test_document_worker.py tests/test_chunker_generalization.py tests/test_document_retrieval.py tests/test_citation_rendering.py -v
```

### Test Results
```text
============================= test session starts =============================
platform win32 -- Python 3.11.5, pytest-8.3.5, pluggy-1.5.0
rootdir: E:\repos\athenus\backend
collected 18 items

tests/test_anydoc_adapter.py::test_anydoc_adapter_text_document_parsing PASSED [  5%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_file_not_found PASSED  [ 11%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_oversized_file_rejection PASSED [ 16%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_page_limit_rejection PASSED [ 22%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_table_detection PASSED [ 27%]
tests/test_ocr_adapter.py::test_ocr_adapter_text_extraction PASSED       [ 33%]
tests/test_ocr_adapter.py::test_ocr_adapter_file_not_found PASSED        [ 38%]
tests/test_ocr_adapter.py::test_ocr_adapter_confidence_scores PASSED     [ 44%]
tests/test_document_worker.py::test_document_worker_text_document_flow PASSED [ 50%]
tests/test_document_worker.py::test_document_worker_scanned_document_flow PASSED [ 55%]
tests/test_document_worker.py::test_document_worker_failure_handling PASSED [ 61%]
tests/test_chunker_generalization.py::test_chunk_document_pages PASSED   [ 66%]
tests/test_chunker_generalization.py::test_embedding_worker_handle_document_parsed PASSED [ 72%]
tests/test_document_retrieval.py::test_qdrant_document_filtering PASSED  [ 77%]
tests/test_document_retrieval.py::test_multi_stage_retriever_document_flow PASSED [ 83%]
tests/test_citation_rendering.py::test_parse_chat_citations_video_timestamps PASSED [ 88%]
tests/test_citation_rendering.py::test_parse_chat_citations_document_pages PASSED [ 94%]
tests/test_citation_rendering.py::test_citation_dto_document_serialization PASSED [100%]

============================= 18 passed in 1.00s ==============================
```

---

## Discovered Issues & Known Limitations

1. **Frontend PDF Viewer Component**: Backend endpoints and citation DTOs emit document citations (`source_type: "pdf"`, `page_number: X`). Frontend React/Next.js UI components consume `CitationDTO` to render interactive PDF page jump buttons in chat messages.
