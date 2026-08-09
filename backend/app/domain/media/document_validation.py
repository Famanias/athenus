import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Optional

# Zip-container formats susceptible to decompression bomb attacks
ZIP_CONTAINER_EXTENSIONS = {"docx", "pptx", "xlsx", "epub", "odt", "ods", "odp"}
PDF_EXTENSIONS = {"pdf"}

DEFAULT_MAX_FILE_SIZE_MB = 100.0
DEFAULT_MAX_PAGES = 200
# Fail if decompression ratio exceeds 100:1 and uncompressed payload exceeds 50MB
MAX_ZIP_RATIO = 100.0
MAX_ZIP_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


@dataclass
class DocumentValidationResult:
    valid: bool = True
    stage: str = "validation"
    message: str = ""
    page_count: Optional[int] = None


def _normalize_ext(file_format: Optional[str], file_path: str) -> str:
    ext = ""
    if file_format:
        ext = file_format.lower().lstrip(".")
    if not ext:
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    return ext


def _count_pdf_pages(file_path: str) -> Optional[int]:
    """Count pages in a PDF without external dependencies.

    Uses the PDF page tree ``/Count`` entries and ``/Type /Page`` object markers.
    Returns ``None`` when the count cannot be determined (treated as pass-through
    to the downstream parser, which enforces its own page cap).
    """
    try:
        with open(file_path, "rb") as f:
            data = f.read()
    except Exception:
        return None

    counts = [int(m) for m in re.findall(rb"/Count\s+(\d+)", data)]
    if counts:
        return max(counts)

    page_objects = len(re.findall(rb"/Type\s*/Page(?![s])", data))
    if page_objects > 0:
        return page_objects
    return None


def _check_zip_bomb(file_path: str) -> Optional[str]:
    """Return an error message if the zip container exceeds safe decompression limits."""
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            uncompressed_size = sum(info.file_size for info in zf.infolist())
            compressed_size = os.path.getsize(file_path)
            ratio = uncompressed_size / max(compressed_size, 1)
            if ratio > MAX_ZIP_RATIO and uncompressed_size > MAX_ZIP_UNCOMPRESSED_BYTES:
                return (
                    f"Decompression bomb safety threshold exceeded "
                    f"(compression ratio {ratio:.1f}:1)."
                )
    except zipfile.BadZipFile:
        return "Corrupted or malformed zip container document."
    except Exception:
        return None
    return None


def validate_document_file(
    file_path: str,
    file_format: Optional[str] = None,
    max_file_size_mb: float = DEFAULT_MAX_FILE_SIZE_MB,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> DocumentValidationResult:
    """Validate a document against ingestion safety guardrails.

    Guardrails (per ADR 0021):
    1. File size cap (default 100MB).
    2. Page count cap (default 200 pages) for PDF documents.
    3. Zip decompression bomb ratio check for zip-container formats.
    """
    if not os.path.exists(file_path):
        return DocumentValidationResult(
            valid=False,
            message="Document file not found on disk.",
        )

    # Guardrail 1: File size validation
    file_size_bytes = os.path.getsize(file_path)
    max_bytes = int(max_file_size_mb * 1024 * 1024)
    if file_size_bytes > max_bytes:
        return DocumentValidationResult(
            valid=False,
            message=(
                f"Document size ({file_size_bytes / (1024 * 1024):.1f} MB) exceeds "
                f"maximum allowed safety limit ({max_file_size_mb} MB). "
                f"Split the file and upload again."
            ),
        )

    ext = _normalize_ext(file_format, file_path)

    # Guardrail 2: Zip decompression bomb validation for zip-container formats
    if ext in ZIP_CONTAINER_EXTENSIONS:
        zip_error = _check_zip_bomb(file_path)
        if zip_error:
            return DocumentValidationResult(valid=False, message=zip_error)

    # Guardrail 3: Page count validation for PDF documents
    page_count = None
    if ext in PDF_EXTENSIONS:
        page_count = _count_pdf_pages(file_path)
        if page_count is not None and page_count > max_pages:
            return DocumentValidationResult(
                valid=False,
                message=(
                    f"Document page count ({page_count}) exceeds maximum allowed "
                    f"safety limit ({max_pages} pages). Split the file and upload again."
                ),
                page_count=page_count,
            )

    return DocumentValidationResult(
        valid=True,
        stage="validation",
        message="Document passed validation.",
        page_count=page_count,
    )
