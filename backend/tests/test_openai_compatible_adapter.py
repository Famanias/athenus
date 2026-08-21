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

        from app.domain.ai.exceptions import LLMProviderAuthError, LLMProviderRateLimitError, LLMProviderUnavailableError, LLMProviderTimeoutError
        with pytest.raises(LLMProviderAuthError) as exc_info:
            await adapter.generate(TextGenerationRequest(prompt="Hello"))
        assert "Missing API key" in str(exc_info.value)

    asyncio.run(run())


def test_openai_compatible_adapter_error_integrity_status_codes():
    async def run():
        from app.domain.ai.exceptions import LLMProviderAuthError, LLMProviderRateLimitError, LLMProviderUnavailableError

        # 401 Unauthorized
        transport_401 = httpx.MockTransport(lambda req: httpx.Response(401, text='{"error": "Invalid API key"}'))
        client_401 = httpx.AsyncClient(transport=transport_401)
        adapter_401 = OpenAICompatibleProviderAdapter("groq", "Groq API", "https://api.groq.com/openai/v1", "bad-key", "model-a", http_client=client_401)
        with pytest.raises(LLMProviderAuthError) as exc:
            await adapter_401.generate(TextGenerationRequest(prompt="test"))
        assert exc.value.status_code == 401
        await client_401.aclose()

        # 429 Rate Limit with Retry-After
        headers_429 = {"retry-after": "4.5"}
        transport_429 = httpx.MockTransport(lambda req: httpx.Response(429, headers=headers_429, text='{"error": "Rate limit reached (TPM)"}'))
        client_429 = httpx.AsyncClient(transport=transport_429)
        adapter_429 = OpenAICompatibleProviderAdapter("groq", "Groq API", "https://api.groq.com/openai/v1", "key", "model-a", http_client=client_429)
        with pytest.raises(LLMProviderRateLimitError) as exc:
            await adapter_429.generate(TextGenerationRequest(prompt="test"))
        assert exc.value.status_code == 429
        assert exc.value.retry_after == 4.5
        await client_429.aclose()

        # 503 Service Unavailable
        transport_503 = httpx.MockTransport(lambda req: httpx.Response(503, text='Service overloaded'))
        client_503 = httpx.AsyncClient(transport=transport_503)
        adapter_503 = OpenAICompatibleProviderAdapter("groq", "Groq API", "https://api.groq.com/openai/v1", "key", "model-a", http_client=client_503)
        with pytest.raises(LLMProviderUnavailableError) as exc:
            await adapter_503.generate(TextGenerationRequest(prompt="test"))
        assert exc.value.status_code == 503
        await client_503.aclose()

    asyncio.run(run())

