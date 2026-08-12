import asyncio
import pytest
import httpx
from app.infrastructure.adapters.ollama_provider import OllamaProviderAdapter
from app.infrastructure.adapters.ollama_adapter import OllamaTextGenAdapter
from app.domain.ai.capabilities import TextGenerationRequest

def test_ollama_provider_status_success(monkeypatch):
    async def mock_get(self, url):
        if url.endswith("/api/version"):
            return httpx.Response(200, json={"version": "0.12.2"})
        return httpx.Response(404)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    adapter = OllamaProviderAdapter(base_url="http://localhost:11434")
    status = asyncio.run(adapter.get_status())

    assert status.connected is True
    assert status.version == "0.12.2"
    assert status.provider_id == "ollama"
    assert status.error is None

def test_ollama_provider_list_models_success(monkeypatch):
    async def mock_get(self, url):
        if url.endswith("/api/tags"):
            return httpx.Response(200, json={
                "models": [
                    {"name": "llama3:8b", "size": 4661224676},
                    {"name": "qwen2.5:latest", "size": 3100000000}
                ]
            })
        return httpx.Response(404)

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    adapter = OllamaProviderAdapter(base_url="http://localhost:11434")
    catalog = asyncio.run(adapter.list_models())

    assert catalog.count == 2
    assert catalog.models[0].full_id == "llama3:8b"
    assert catalog.models[0].name == "llama3"
    assert catalog.models[0].tag == "8b"
    assert catalog.models[0].size_bytes == 4661224676
    assert catalog.models[1].full_id == "qwen2.5:latest"

def test_ollama_provider_offline_graceful_handling(monkeypatch):
    async def mock_get_error(self, url):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get_error)

    adapter = OllamaProviderAdapter(base_url="http://localhost:11434")
    status = asyncio.run(adapter.get_status())

    assert status.connected is False
    assert "unreachable" in status.error

    catalog = asyncio.run(adapter.list_models())
    assert catalog.count == 0
    assert len(catalog.models) == 0

def test_ollama_text_gen_adapter_generate_success(monkeypatch):
    async def mock_post(self, url, json=None):
        return httpx.Response(200, json={
            "response": "Hello world from Ollama",
            "prompt_eval_count": 10,
            "eval_count": 5
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    adapter = OllamaTextGenAdapter(base_url="http://localhost:11434", default_model="llama3:8b")
    req = TextGenerationRequest(prompt="hi")
    res = asyncio.run(adapter.generate(req))

    assert res.text == "Hello world from Ollama"
    assert res.prompt_tokens == 10
    assert res.completion_tokens == 5

def test_ollama_text_gen_adapter_raises_on_failure(monkeypatch):
    async def mock_post(self, url, json=None):
        raise httpx.ConnectError("Ollama daemon unreachable")

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    adapter = OllamaTextGenAdapter(base_url="http://localhost:11434", default_model="llama3:8b")
    req = TextGenerationRequest(prompt="hi")

    with pytest.raises(ValueError) as exc_info:
        asyncio.run(adapter.generate(req))

    assert "Failed connecting to Ollama" in str(exc_info.value)
    # Ensure fake fallback text is NOT returned
    assert "Offline Fallback" not in str(exc_info.value)


