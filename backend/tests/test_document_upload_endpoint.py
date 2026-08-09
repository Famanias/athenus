import os
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_upload_document_success(tmp_path):
    pdf_file = tmp_path / "sample.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 sample content for document testing")

    with open(pdf_file, "rb") as f:
        response = client.post(
            "/api/v1/media/upload",
            files={"file": ("sample.pdf", f, "application/pdf")},
            data={"workspace_id": "default"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["media_id"].startswith("doc_")
    assert data["status"] == "uploaded"

def test_upload_oversized_document_rejection(tmp_path, monkeypatch):
    large_pdf = tmp_path / "huge.pdf"
    # Create fake content larger than 100MB limit logic
    content = b"x" * (100 * 1024 * 1024 + 1)
    large_pdf.write_bytes(content)

    with open(large_pdf, "rb") as f:
        response = client.post(
            "/api/v1/media/upload",
            files={"file": ("huge.pdf", f, "application/pdf")},
            data={"workspace_id": "default"}
        )

    assert response.status_code == 413
    assert "exceeds maximum allowed safety limit of 100MB" in response.json()["detail"]
