import asyncio
import os
import tempfile
import pytest

from app.domain.ai.capabilities import (
    DocumentPageDTO,
    DocumentParsingRequest,
    DocumentParsingResponse,
    IDocumentParsingCapability,
    IOCRCapability,
    OCRRequest,
    OCRResponse,
)
from app.infrastructure.events.event_bus import DomainEvent, EventBus
from app.services.workers.document_worker import DocumentWorker


class MockDocumentParser(IDocumentParsingCapability):
    def __init__(self, has_scanned: bool = False, should_fail: bool = False) -> None:
        self.has_scanned = has_scanned
        self.should_fail = should_fail

    async def parse_document(self, request: DocumentParsingRequest) -> DocumentParsingResponse:
        if self.should_fail:
            raise ValueError("Invalid corrupted document container.")

        pages = [
            DocumentPageDTO(
                page_number=1,
                text="Scanned Page Content" if self.has_scanned else "Text Page Content",
                page_type="scanned" if self.has_scanned else "text",
                section_title="Page 1",
            )
        ]
        return DocumentParsingResponse(
            markdown="# Document Title\n\nContent",
            pages=pages,
            file_format="pdf",
            total_pages=1,
            has_scanned_pages=self.has_scanned,
            has_tables=False,
        )


class MockOCRAdapter(IOCRCapability):
    async def perform_ocr(self, request: OCRRequest) -> OCRResponse:
        return OCRResponse(
            text="Extracted OCR Text from scanned page",
            confidence=0.98,
            lines=[],
        )


def test_document_worker_text_document_flow():
    async def _run():
        bus = EventBus()
        parser = MockDocumentParser(has_scanned=False)
        ocr = MockOCRAdapter()
        worker = DocumentWorker(event_bus=bus, doc_parser=parser, ocr_capability=ocr)

        events_received = []

        async def _capture_parsed(event: DomainEvent):
            events_received.append(event)

        bus.subscribe("DocumentParsedEvent", _capture_parsed)

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".pdf") as f:
            f.write("Sample PDF content")
            temp_path = f.name

        try:
            upload_event = DomainEvent(
                event_type="DocumentUploadedEvent",
                aggregate_id="doc_123",
                payload={"file_path": temp_path, "workspace_id": "ws_default", "file_format": "pdf"},
            )
            await bus.publish(upload_event)

            assert len(events_received) == 1
            res_event = events_received[0]
            assert res_event.event_type == "DocumentParsedEvent"
            assert res_event.aggregate_id == "doc_123"
            assert res_event.payload["total_pages"] == 1
            assert res_event.payload["pages"][0]["text"] == "Text Page Content"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    asyncio.run(_run())


def test_document_worker_scanned_document_flow():
    async def _run():
        bus = EventBus()
        parser = MockDocumentParser(has_scanned=True)
        ocr = MockOCRAdapter()
        worker = DocumentWorker(event_bus=bus, doc_parser=parser, ocr_capability=ocr)

        events_received = []

        async def _capture_parsed(event: DomainEvent):
            events_received.append(event)

        bus.subscribe("DocumentParsedEvent", _capture_parsed)

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".pdf") as f:
            f.write("Sample Scanned PDF content")
            temp_path = f.name

        try:
            upload_event = DomainEvent(
                event_type="DocumentUploadedEvent",
                aggregate_id="doc_456",
                payload={"file_path": temp_path, "workspace_id": "ws_default", "file_format": "pdf"},
            )
            await bus.publish(upload_event)

            assert len(events_received) == 1
            res_event = events_received[0]
            assert res_event.payload["pages"][0]["text"] == "Extracted OCR Text from scanned page"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    asyncio.run(_run())


def test_document_worker_failure_handling():
    async def _run():
        bus = EventBus()
        parser = MockDocumentParser(should_fail=True)
        ocr = MockOCRAdapter()
        worker = DocumentWorker(event_bus=bus, doc_parser=parser, ocr_capability=ocr)

        failed_events = []

        async def _capture_failed(event: DomainEvent):
            failed_events.append(event)

        bus.subscribe("DocumentProcessingFailedEvent", _capture_failed)

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".pdf") as f:
            f.write("Corrupted content")
            temp_path = f.name

        try:
            upload_event = DomainEvent(
                event_type="DocumentUploadedEvent",
                aggregate_id="doc_789",
                payload={"file_path": temp_path, "workspace_id": "ws_default", "file_format": "pdf"},
            )
            await bus.publish(upload_event)

            assert len(failed_events) == 1
            assert failed_events[0].event_type == "DocumentProcessingFailedEvent"
            assert "Invalid corrupted document" in failed_events[0].payload["error"]
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    asyncio.run(_run())
