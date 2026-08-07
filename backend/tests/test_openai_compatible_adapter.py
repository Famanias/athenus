import pytest
import asyncio
import json
import httpx
from app.domain.ai.capabilities import TextGenerationRequest
from app.infrastructure.adapters.openai_compatible_adapter import (
    OpenAICompatibleProviderAdapter,
    default_is_chat_model,
    LLMStreamException
)

def test_is_chat_model_predicate():
    # Chat models should pass
    assert default_is_chat_model("llama-3.3-70b-versatile") is True
    assert default_is_chat_model("google/gemini-2.5-flash") is True
    assert default_is_chat_model("gpt-4o-mini") is True
    assert default_is_chat_model("deepseek-r1") is True

    # Non-chat models (embeddings, rerankers, speech, guardrails) should be filtered out
    assert default_is_chat_model("text-embedding-3-small") is False
    assert default_is_chat_model("bge-large-en-v1.5") is False
    assert default_is_chat_model("bge-reranker-large") is False
    assert default_is_chat_model("whisper-large-v3") is False
    assert default_is_chat_model("llama-guard-3-8b") is False


def test_openai_compatible_adapter_generation():
    async def run():
        # Test mock HTTP transport
        def mock_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/models"):
                data = {
                    "data": [
                        {"id": "llama-3.3-70b-versatile", "context_length": 128000},
                        {"id": "text-embedding-3-small", "context_length": 8192}, # Filtered
                        {"id": "deepseek-r1", "context_length": 64000}
                    ]
                }
                return httpx.Response(200, json=data)
            elif request.url.path.endswith("/chat/completions"):
                data = {
                    "choices": [{"message": {"content": "Hello from mock OpenAI API"}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 6}
                }
                return httpx.Response(200, json=data)
            return httpx.Response(404)

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport)

        adapter = OpenAICompatibleProviderAdapter(
            provider_id="openrouter",
            name="OpenRouter Test",
            base_url="https://openrouter.ai/api/v1",
            api_key="sk-test-key",
            default_model="llama-3.3-70b-versatile",
            http_client=client
        )

        # Health check
        health = await adapter.check_health()
        assert health.is_configured is True
        assert health.is_available is True

        # List models with is_chat_model filtering
        models = await adapter.list_models()
        model_ids = [m.id for m in models]
        assert "llama-3.3-70b-versatile" in model_ids
        assert "deepseek-r1" in model_ids
        assert "text-embedding-3-small" not in model_ids # Correctly filtered!

        # Non-streaming text generation
        res = await adapter.generate(TextGenerationRequest(prompt="Hello"))
        assert res.text == "Hello from mock OpenAI API"
        assert res.prompt_tokens == 10
        assert res.completion_tokens == 6

        await client.aclose()

    asyncio.run(run())


def test_openai_compatible_adapter_missing_key():
    async def run():
        adapter = OpenAICompatibleProviderAdapter(
            provider_id="groq",
            name="Groq API",
            base_url="https://api.groq.com/openai/v1",
            api_key="",
            default_model="llama-3.3-70b-versatile"
        )
        health = await adapter.check_health()
        assert health.is_configured is False
        assert health.is_available is False
        assert health.error_message == "Missing API key in .env"

        res = await adapter.generate(TextGenerationRequest(prompt="Hello"))
        assert "API Key Missing" in res.text

    asyncio.run(run())
