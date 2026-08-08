import asyncio
import pytest
import httpx
from app.domain.ai.capabilities import TextGenerationRequest, TextGenerationResponse
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.provider_registry import LLMProviderRegistry
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.adapters.ollama_adapter import OllamaTextGenAdapter
from app.infrastructure.adapters.openai_compatible_adapter import OpenAICompatibleProviderAdapter

def test_ollama_provider_and_model_routing(monkeypatch):
    last_requested_payload = {}

    async def mock_post(self, url, json=None, headers=None):
        nonlocal last_requested_payload
        last_requested_payload = json or {}
        return httpx.Response(200, json={
            "response": "Ollama generated output",
            "prompt_eval_count": 12,
            "eval_count": 8
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    ollama_adapter = OllamaTextGenAdapter(base_url="http://localhost:11434", default_model="llama3:8b")
    registry = LLMProviderRegistry()
    registry.register(ollama_adapter)

    bus = AIServiceBus(ModelRegistry(), ProviderRouter(ModelRegistry()), llm_registry=registry)

    provider = bus.get_text_capability()
    assert provider.provider_id == "ollama"

    req = TextGenerationRequest(prompt="Test quiz prompt")
    res = asyncio.run(provider.generate(req))

    assert res.text == "Ollama generated output"
    assert last_requested_payload.get("model") == "llama3:8b"

def test_cloud_groq_provider_and_model_routing(monkeypatch):
    last_requested_payload = {}

    async def mock_post(self, url, json=None, headers=None):
        nonlocal last_requested_payload
        last_requested_payload = json or {}
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Groq generated output"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 10}
        })

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    groq_adapter = OpenAICompatibleProviderAdapter(
        provider_id="groq",
        name="Groq Cloud",
        base_url="https://api.groq.com/openai/v1",
        api_key="gsk_test_key",
        default_model="llama-3.3-70b-versatile"
    )

    registry = LLMProviderRegistry()
    registry.register(groq_adapter)
    # Mock config resolver active provider ID to 'groq'
    monkeypatch.setattr(registry.config_resolver, "get_active_provider_id", lambda: "groq")

    bus = AIServiceBus(ModelRegistry(), ProviderRouter(ModelRegistry()), llm_registry=registry)

    provider = bus.get_text_capability()
    assert provider.provider_id == "groq"

    req = TextGenerationRequest(prompt="Test chat query")
    res = asyncio.run(provider.generate(req))

    assert res.text == "Groq generated output"
    assert last_requested_payload.get("model") == "llama-3.3-70b-versatile"

def test_active_model_runtime_override(monkeypatch):
    last_requested_payload = {}

    async def mock_post(self, url, json=None, headers=None):
        nonlocal last_requested_payload
        last_requested_payload = json or {}
        return httpx.Response(200, json={"response": "Custom model output"})

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    ollama_adapter = OllamaTextGenAdapter(base_url="http://localhost:11434", default_model="llama3:8b")
    ollama_adapter.set_model("qwen3.6:latest")

    registry = LLMProviderRegistry()
    registry.register(ollama_adapter)

    bus = AIServiceBus(ModelRegistry(), ProviderRouter(ModelRegistry()), llm_registry=registry)
    provider = bus.get_text_capability()

    req = TextGenerationRequest(prompt="Test prompt")
    res = asyncio.run(provider.generate(req))

    assert res.text == "Custom model output"
    assert last_requested_payload.get("model") == "qwen3.6:latest"
