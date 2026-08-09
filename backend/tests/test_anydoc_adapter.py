import asyncio
import os
import tempfile
import pytest
from app.domain.ai.capabilities import DocumentParsingRequest
from app.infrastructure.adapters.anydoc_adapter import AnyDocDocumentParsingAdapter


def test_anydoc_adapter_text_document_parsing():
    async def _run():
        adapter = AnyDocDocumentParsingAdapter()
        
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".md") as f:
            f.write("# Introduction to Economics\n\nThis is page 1.\n\n---\n\n## Section 2\n\nThis is page 2.")
            temp_path = f.name

        try:
            req = DocumentParsingRequest(file_path=temp_path, max_pages=10)
            res = await adapter.parse_document(req)

            assert res.total_pages == 2
            assert len(res.pages) == 2
            assert res.pages[0].page_number == 1
            assert "Introduction to Economics" in res.pages[0].text
            assert res.pages[1].page_number == 2
            assert "Section 2" in res.pages[1].text
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    asyncio.run(_run())


def test_anydoc_adapter_file_not_found():
    async def _run():
        adapter = AnyDocDocumentParsingAdapter()
        req = DocumentParsingRequest(file_path="non_existent_file_12345.pdf")

        with pytest.raises(FileNotFoundError):
            await adapter.parse_document(req)

    asyncio.run(_run())


def test_anydoc_adapter_oversized_file_rejection():
    async def _run():
        adapter = AnyDocDocumentParsingAdapter()

        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".pdf") as f:
            f.write(b"0" * 500)
            temp_path = f.name

        try:
            req = DocumentParsingRequest(file_path=temp_path, max_file_size_mb=0.0001)
            with pytest.raises(ValueError, match="exceeds maximum allowed safety limit"):
                await adapter.parse_document(req)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    asyncio.run(_run())


def test_anydoc_adapter_page_limit_rejection():
    async def _run():
        adapter = AnyDocDocumentParsingAdapter()

        pages_content = "\n\n---\n\n".join([f"Page {i}" for i in range(1, 15)])
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
            f.write(pages_content)
            temp_path = f.name

        try:
            req = DocumentParsingRequest(file_path=temp_path, max_pages=5)
            with pytest.raises(ValueError, match="exceeds maximum allowed safety limit"):
                await adapter.parse_document(req)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    asyncio.run(_run())


def test_anydoc_adapter_table_detection():
    async def _run():
        adapter = AnyDocDocumentParsingAdapter()

        table_content = "# Data Table\n\n| Col A | Col B |\n|---|---|\n| Val 1 | Val 2 |"
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".md") as f:
            f.write(table_content)
            temp_path = f.name

        try:
            req = DocumentParsingRequest(file_path=temp_path)
            res = await adapter.parse_document(req)
            assert res.has_tables is True
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    asyncio.run(_run())
