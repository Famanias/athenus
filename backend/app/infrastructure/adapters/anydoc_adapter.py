import asyncio
import os
import zipfile
from typing import Any, Dict, List, Optional

from app.domain.ai.capabilities import (
    DocumentPageDTO,
    DocumentParsingRequest,
    DocumentParsingResponse,
    IDocumentParsingCapability,
)


class AnyDocDocumentParsingAdapter(IDocumentParsingCapability):
    """Adapter for Firecrawl AnyDoc document parsing engine with local safety guardrails."""

    def __init__(self) -> None:
        self._anydoc_available = False
        try:
            import anydoc  # type: ignore # noqa: F401
            self._anydoc_available = True
        except ImportError:
            self._anydoc_available = False

    async def parse_document(self, request: DocumentParsingRequest) -> DocumentParsingResponse:
        """Asynchronously parse a document file, running heavy IO in executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._parse_sync, request)

    def _parse_sync(self, request: DocumentParsingRequest) -> DocumentParsingResponse:
        if not os.path.exists(request.file_path):
            raise FileNotFoundError(f"Document file not found: {request.file_path}")

        # Guardrail 1: File size validation
        file_size_bytes = os.path.getsize(request.file_path)
        max_bytes = int(request.max_file_size_mb * 1024 * 1024)
        if file_size_bytes > max_bytes:
            raise ValueError(
                f"Document size ({file_size_bytes / (1024 * 1024):.1f} MB) exceeds maximum allowed safety limit ({request.max_file_size_mb} MB)."
            )

        ext = os.path.splitext(request.file_path)[1].lower().lstrip(".")
        file_format = request.file_format or ext or "unknown"

        # Guardrail 2: Zip decompression bomb validation for zip-container formats
        if ext in ("docx", "pptx", "xlsx", "epub", "odt", "ods", "odp"):
            self._check_zip_bomb(request.file_path)

        # Execute AnyDoc parsing if installed
        if self._anydoc_available:
            return self._parse_with_anydoc(request, file_format)
        else:
            return self._parse_with_fallback(request, file_format)

    def _check_zip_bomb(self, file_path: str) -> None:
        """Validate zip container compression ratios to prevent decompression bomb attacks."""
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                uncompressed_size = sum(file.file_size for file in zf.infolist())
                compressed_size = os.path.getsize(file_path)
                ratio = uncompressed_size / max(compressed_size, 1)
                # Fail if decompression ratio exceeds 100:1 and uncompressed payload > 50MB
                if ratio > 100 and uncompressed_size > 50 * 1024 * 1024:
                    raise ValueError(
                        f"Decompression bomb safety threshold exceeded (compression ratio {ratio:.1f}:1)."
                    )
        except zipfile.BadZipFile:
            raise ValueError("Corrupted or malformed zip container document.")

    def _parse_with_anydoc(self, request: DocumentParsingRequest, file_format: str) -> DocumentParsingResponse:
        import anydoc  # type: ignore

        try:
            markdown_content = anydoc.to_markdown(request.file_path)
        except Exception as e:
            err_msg = str(e)
            if "Encrypted" in err_msg or "Password" in err_msg:
                raise ValueError(f"Encrypted or password-protected document: {err_msg}")
            raise ValueError(f"AnyDoc parsing failed: {err_msg}")

        # Split markdown by page markers if available, or generate page structure
        raw_pages = markdown_content.split("<!-- pagebreak -->")
        if len(raw_pages) == 1:
            raw_pages = markdown_content.split("\n\n---\n\n")

        total_pages = len(raw_pages)
        if total_pages > request.max_pages:
            raise ValueError(
                f"Document page count ({total_pages}) exceeds maximum allowed safety limit ({request.max_pages} pages)."
            )

        pages: List[DocumentPageDTO] = []
        has_scanned = False
        has_tables = "|" in markdown_content and "\n|---" in markdown_content

        for idx, page_text in enumerate(raw_pages, start=1):
            clean_text = page_text.strip()
            # Detect scanned pages if page text is virtually empty or flagged as image placeholder
            is_scanned = len(clean_text) < 20 and ("![image" in clean_text.lower() or "[scanned]" in clean_text.lower())
            if is_scanned:
                has_scanned = True
            
            page_type = "scanned" if is_scanned else "text"
            pages.append(
                DocumentPageDTO(
                    page_number=idx,
                    text=clean_text,
                    page_type=page_type,
                    section_title=f"Page {idx}",
                )
            )

        return DocumentParsingResponse(
            markdown=markdown_content,
            pages=pages,
            file_format=file_format,
            total_pages=total_pages,
            has_scanned_pages=has_scanned,
            has_tables=has_tables,
            language_detected="en",
        )

    def _parse_with_fallback(self, request: DocumentParsingRequest, file_format: str) -> DocumentParsingResponse:
        """Robust fallback parser for local environments where anydoc native module is not loaded."""
        try:
            with open(request.file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            raise ValueError(f"Could not read document file: {str(e)}")

        raw_pages = [p for p in content.split("\n\n---\n\n") if p.strip()] or [content]
        total_pages = len(raw_pages)

        if total_pages > request.max_pages:
            raise ValueError(
                f"Document page count ({total_pages}) exceeds maximum allowed safety limit ({request.max_pages} pages)."
            )

        pages: List[DocumentPageDTO] = []
        has_scanned = False
        has_tables = "|" in content and "\n|---" in content

        for idx, page_text in enumerate(raw_pages, start=1):
            clean_text = page_text.strip()
            is_scanned = "[scanned]" in clean_text.lower()
            if is_scanned:
                has_scanned = True

            pages.append(
                DocumentPageDTO(
                    page_number=idx,
                    text=clean_text,
                    page_type="scanned" if is_scanned else "text",
                    section_title=f"Section {idx}",
                )
            )

        return DocumentParsingResponse(
            markdown=content,
            pages=pages,
            file_format=file_format,
            total_pages=total_pages,
            has_scanned_pages=has_scanned,
            has_tables=has_tables,
            language_detected="en",
        )
