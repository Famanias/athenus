# Walkthrough — Milestone 2, Phase 2.1: DocumentParsingPort & AnyDoc Adapter

This walkthrough documents the completed implementation of **Milestone 2, Phase 2.1**: `DocumentParsingPort` and `AnyDocDocumentParsingAdapter`.

---

## Completed Implementation Overview

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

---

## Automated Verification & Testing

### Test Suite Execution
Executed unit test suite in `backend/tests/test_anydoc_adapter.py`:

```bash
python -m pytest tests/test_anydoc_adapter.py -v
```

### Test Results
```text
============================= test session starts =============================
platform win32 -- Python 3.11.5, pytest-8.3.5, pluggy-1.5.0
rootdir: E:\repos\athenus\backend
collected 5 items

tests/test_anydoc_adapter.py::test_anydoc_adapter_text_document_parsing PASSED [ 20%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_file_not_found PASSED  [ 40%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_oversized_file_rejection PASSED [ 60%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_page_limit_rejection PASSED [ 80%]
tests/test_anydoc_adapter.py::test_anydoc_adapter_table_detection PASSED [100%]

============================== 5 passed in 0.11s ==============================
```

---

## Manual Validation / QA

Perform the following verification tests to manually validate the Phase 2.1 implementation:

| Test | How to Conduct the Test | Expected Behaviour |
| :--- | :--- | :--- |
| **1. Text Document Parsing Test** | Run `python -c "import asyncio; from app.infrastructure.adapters.anydoc_adapter import AnyDocDocumentParsingAdapter; from app.domain.ai.capabilities import DocumentParsingRequest; print(asyncio.run(AnyDocDocumentParsingAdapter().parse_document(DocumentParsingRequest(file_path='README.md'))))"` from `backend/`. | The command returns a valid `DocumentParsingResponse` containing parsed GFM markdown, detected file format (`"md"`), and total pages. |
| **2. Missing File Error Guardrail Test** | Run `python -c "import asyncio; from app.infrastructure.adapters.anydoc_adapter import AnyDocDocumentParsingAdapter; from app.domain.ai.capabilities import DocumentParsingRequest; asyncio.run(AnyDocDocumentParsingAdapter().parse_document(DocumentParsingRequest(file_path='missing.pdf')))"` from `backend/`. | The call fails loudly raising `FileNotFoundError: Document file not found: missing.pdf`. |
| **3. Oversized File Cap Rejection Test** | Run `python -c "import asyncio; from app.infrastructure.adapters.anydoc_adapter import AnyDocDocumentParsingAdapter; from app.domain.ai.capabilities import DocumentParsingRequest; asyncio.run(AnyDocDocumentParsingAdapter().parse_document(DocumentParsingRequest(file_path='README.md', max_file_size_mb=0.00001)))"` from `backend/`. | The call hard-rejects the document, raising `ValueError` stating that file size exceeds maximum allowed safety limit. |

---

## Discovered Issues & Known Limitations

1. **Scanned PDF Text Extraction**: Phase 2.1 detects scanned pages (`page_type="scanned"`), but does not run OCR text extraction. Scanned OCR extraction is scheduled for **Phase 2.2 (`OCRPort` + RapidOCR adapter)**.
