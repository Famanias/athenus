import os
from typing import Any, Dict, List, Optional

from app.domain.ai.capabilities import (
    DocumentParsingRequest,
    IDocumentParsingCapability,
    IOCRCapability,
    OCRRequest,
)
from app.infrastructure.adapters.anydoc_adapter import AnyDocDocumentParsingAdapter
from app.infrastructure.adapters.ocr_adapter import RapidOCROCRAdapter
from app.infrastructure.events.event_bus import DomainEvent, EventBus
from app.infrastructure.scheduler.workload_scheduler import workload_scheduler


class DocumentWorker:
    """Worker handling document parsing (AnyDoc) and scanned page OCR (RapidOCR)."""

    def __init__(
        self,
        event_bus: EventBus,
        doc_parser: Optional[IDocumentParsingCapability] = None,
        ocr_capability: Optional[IOCRCapability] = None,
    ) -> None:
        self.event_bus = event_bus
        self.doc_parser = doc_parser or AnyDocDocumentParsingAdapter()
        self.ocr_capability = ocr_capability or RapidOCROCRAdapter()

        # Subscribe to DocumentUploadedEvent
        self.event_bus.subscribe("DocumentUploadedEvent", self.handle_document_uploaded)

    async def handle_document_uploaded(self, event: DomainEvent) -> None:
        document_id = event.aggregate_id
        file_path = event.payload.get("file_path")
        workspace_id = event.payload.get("workspace_id", "default")
        file_format = event.payload.get("file_format")

        if not file_path:
            return

        current_stage = "document_parsing"
        try:
            # 1. Emit ProcessingStartedEvent
            await self.event_bus.publish(
                DomainEvent(
                    event_type="ProcessingStartedEvent",
                    aggregate_id=document_id,
                    payload={
                        "media_id": document_id,
                        "workspace_id": workspace_id,
                        "stage": "document_parsing",
                        "progress": 25,
                        "message": "Parsing document structure with AnyDoc...",
                    },
                )
            )

            # 2. Execute fast document parsing (lightweight CPU thread)
            request = DocumentParsingRequest(
                file_path=file_path,
                file_format=file_format,
                max_pages=200,
                max_file_size_mb=100.0,
            )
            parse_response = await self.doc_parser.parse_document(request)

            current_stage = "ocr_processing"
            parsed_pages: List[Dict[str, Any]] = []

            # 3. If scanned pages detected, process OCR under resource-bounded hardware semaphore
            if parse_response.has_scanned_pages:
                await self.event_bus.publish(
                    DomainEvent(
                        event_type="StageProgressEvent",
                        aggregate_id=document_id,
                        payload={
                            "media_id": document_id,
                            "workspace_id": workspace_id,
                            "stage": "ocr_processing",
                            "progress": 50,
                            "message": "Extracting text from scanned pages using RapidOCR...",
                        },
                    )
                )

                # Acquire hardware semaphore (Semaphore=1 per ADR 0021) for heavy OCR pass
                async with workload_scheduler._semaphore:
                    for p in parse_response.pages:
                        page_text = p.text
                        if p.page_type == "scanned" or not page_text.strip():
                            ocr_res = await self.ocr_capability.perform_ocr(
                                OCRRequest(image_path=file_path, page_number=p.page_number)
                            )
                            if ocr_res.text.strip():
                                page_text = ocr_res.text.strip()

                        parsed_pages.append(
                            {
                                "page_number": p.page_number,
                                "text": page_text,
                                "page_type": p.page_type,
                                "section_title": p.section_title or f"Page {p.page_number}",
                            }
                        )
            else:
                for p in parse_response.pages:
                    parsed_pages.append(
                        {
                            "page_number": p.page_number,
                            "text": p.text,
                            "page_type": p.page_type,
                            "section_title": p.section_title or f"Page {p.page_number}",
                        }
                    )

            # 4. Emit DocumentParsedEvent (additive event)
            await self.event_bus.publish(
                DomainEvent(
                    event_type="DocumentParsedEvent",
                    aggregate_id=document_id,
                    payload={
                        "document_id": document_id,
                        "workspace_id": workspace_id,
                        "file_path": file_path,
                        "file_format": parse_response.file_format,
                        "markdown": parse_response.markdown,
                        "pages": parsed_pages,
                        "total_pages": parse_response.total_pages,
                        "has_tables": parse_response.has_tables,
                    },
                )
            )

        except Exception as e:
            err_msg = str(e).strip() or repr(e)
            # Emit additive DocumentProcessingFailedEvent and standard ProcessingFailedEvent
            await self.event_bus.publish(
                DomainEvent(
                    event_type="DocumentProcessingFailedEvent",
                    aggregate_id=document_id,
                    payload={
                        "document_id": document_id,
                        "workspace_id": workspace_id,
                        "stage": current_stage,
                        "error": err_msg,
                    },
                )
            )
            await self.event_bus.publish(
                DomainEvent(
                    event_type="ProcessingFailedEvent",
                    aggregate_id=document_id,
                    payload={
                        "media_id": document_id,
                        "workspace_id": workspace_id,
                        "stage": current_stage,
                        "error": err_msg,
                    },
                )
            )
