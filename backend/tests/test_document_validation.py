import os
import tempfile
import zipfile

from app.domain.media.document_validation import (
    DEFAULT_MAX_FILE_SIZE_MB,
    DEFAULT_MAX_PAGES,
    MAX_ZIP_UNCOMPRESSED_BYTES,
    MAX_ZIP_RATIO,
    validate_document_file,
)


def _write_temp(suffix: str, content: bytes = b"sample content") -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


def test_validation_passes_small_text_document():
    path = _write_temp(".txt", b"hello world" * 100)
    try:
        result = validate_document_file(path, file_format="txt")
        assert result.valid is True
        assert result.stage == "validation"
        assert result.page_count is None
    finally:
        os.remove(path)


def test_validation_rejects_missing_file():
    result = validate_document_file("does_not_exist_1234.pdf")
    assert result.valid is False
    assert "not found" in result.message.lower()


def test_validation_rejects_oversized_file():
    path = _write_temp(".pdf", b"\x00" * 1024)
    try:
        result = validate_document_file(path, file_format="pdf", max_file_size_mb=0.000001)
        assert result.valid is False
        assert "exceeds" in result.message.lower()
    finally:
        os.remove(path)


def test_validation_rejects_over_page_count_pdf():
    # Craft a minimal PDF with a /Count of 500 to exceed the 200-page cap.
    pdf = b"%PDF-1.4\n"
    pdf += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    pdf += b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 500 >>\nendobj\n"
    pdf += b"3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n"
    pdf += b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
    path = _write_temp(".pdf", pdf)
    try:
        result = validate_document_file(path, file_format="pdf")
        assert result.valid is False
        assert "page count" in result.message.lower()
        assert result.page_count == 500
    finally:
        os.remove(path)


def test_validation_passes_under_page_count_pdf():
    pdf = b"%PDF-1.4\n"
    pdf += b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    pdf += b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 12 >>\nendobj\n"
    pdf += b"3 0 obj\n<< /Type /Page /Parent 2 0 R >>\nendobj\n"
    pdf += b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
    path = _write_temp(".pdf", pdf)
    try:
        result = validate_document_file(path, file_format="pdf")
        assert result.valid is True
        assert result.page_count == 12
    finally:
        os.remove(path)


def test_validation_rejects_zip_bomb_docx():
    # Build a zip with a high compression ratio to exceed the 100:1 threshold.
    fd, path = tempfile.mkstemp(suffix=".docx")
    os.close(fd)
    try:
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            payload = b"A" * (MAX_ZIP_UNCOMPRESSED_BYTES + 1)
            zf.writestr("word/document.xml", payload)
        result = validate_document_file(path, file_format="docx")
        assert result.valid is False
        assert "bomb" in result.message.lower() or "decompression" in result.message.lower()
    finally:
        os.remove(path)


def test_validation_rejects_corrupt_zip():
    path = _write_temp(".docx", b"this is not a real zip archive")
    try:
        result = validate_document_file(path, file_format="docx")
        assert result.valid is False
        assert "corrupt" in result.message.lower()
    finally:
        os.remove(path)


def test_validation_skips_non_zip_non_pdf_extensions():
    path = _write_temp(".md", b"# Heading\n\nJust a markdown file.")
    try:
        result = validate_document_file(path, file_format="md")
        assert result.valid is True
    finally:
        os.remove(path)
