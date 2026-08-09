import asyncio
import os
import tempfile
import pytest
from app.domain.ai.capabilities import OCRRequest
from app.infrastructure.adapters.ocr_adapter import RapidOCROCRAdapter


def test_ocr_adapter_text_extraction():
    async def _run():
        adapter = RapidOCROCRAdapter()

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".png") as f:
            f.write("Scanned Document Title\nLine 1 of OCR text\nLine 2 of OCR text")
            temp_path = f.name

        try:
            req = OCRRequest(image_path=temp_path, page_number=1)
            res = await adapter.perform_ocr(req)

            assert "Scanned Document Title" in res.text
            assert len(res.lines) >= 1
            assert res.confidence > 0.0
            assert res.lines[0].confidence > 0.0
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    asyncio.run(_run())


def test_ocr_adapter_file_not_found():
    async def _run():
        adapter = RapidOCROCRAdapter()
        req = OCRRequest(image_path="missing_image_12345.png")

        with pytest.raises(FileNotFoundError):
            await adapter.perform_ocr(req)

    asyncio.run(_run())


def test_ocr_adapter_confidence_scores():
    async def _run():
        adapter = RapidOCROCRAdapter()

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".jpg") as f:
            f.write("Sample text line for confidence testing")
            temp_path = f.name

        try:
            req = OCRRequest(image_path=temp_path, page_number=2)
            res = await adapter.perform_ocr(req)

            assert res.confidence <= 1.0
            for line in res.lines:
                assert 0.0 <= line.confidence <= 1.0
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    asyncio.run(_run())
