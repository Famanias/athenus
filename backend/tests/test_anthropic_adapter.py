import pytest
import asyncio
import httpx
from app.domain.ai.capabilities import TextGenerationRequest
from app.infrastructure.adapters.anthropic_adapter import AnthropicProviderAdapter

def test_anthropic_adapter_generation():
    async def run():
        def mock_handler(request: httpx.Request) -> httpx.Response:
            assert request.headers.get("x-api-key") == "sk-ant-test"
            assert request.headers.get("anthropic-version") == "2023-06-01"
            
            body = json.loads(request.content)
            assert body.get("system") == "You are Athenus AI Assistant."
            assert body.get("max_tokens") == 2048

            data = {
                "content": [{"type": "text", "text": "Hello from Claude native API"}],
                "usage": {"input_tokens": 15, "output_tokens": 8},
                "stop_reason": "end_turn"
            }
            return httpx.Response(200, json=data)

        import json
        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport)

        adapter = AnthropicProviderAdapter(
            api_key="sk-ant-test",
            default_model="claude-3-5-sonnet-latest",
            http_client=client
        )

        health = await adapter.check_health()
        assert health.is_configured is True
        assert health.is_available is True
        assert health.provider_id == "anthropic"

        res = await adapter.generate(TextGenerationRequest(prompt="Hello Claude"))
        assert res.text == "Hello from Claude native API"
        assert res.prompt_tokens == 15
        assert res.completion_tokens == 8

        await client.aclose()

    asyncio.run(run())


def test_anthropic_adapter_missing_key():
    async def run():
        adapter = AnthropicProviderAdapter(api_key="")
        health = await adapter.check_health()
        assert health.is_configured is False
        assert health.is_available is False
        assert health.error_message == "Missing API key in .env"

        from app.domain.ai.exceptions import LLMProviderAuthError, LLMProviderRateLimitError, LLMProviderUnavailableError
        with pytest.raises(LLMProviderAuthError) as exc_info:
            await adapter.generate(TextGenerationRequest(prompt="Hello"))
        assert "Missing API key" in str(exc_info.value)

    asyncio.run(run())


def test_anthropic_adapter_error_integrity_status_codes():
    async def run():
        from app.domain.ai.exceptions import LLMProviderAuthError, LLMProviderRateLimitError, LLMProviderUnavailableError

        # 401
        transport_401 = httpx.MockTransport(lambda req: httpx.Response(401, text='{"error": {"type": "authentication_error"}}'))
        client_401 = httpx.AsyncClient(transport=transport_401)
        adapter_401 = AnthropicProviderAdapter(api_key="bad-key", http_client=client_401)
        with pytest.raises(LLMProviderAuthError) as exc:
            await adapter_401.generate(TextGenerationRequest(prompt="test"))
        assert exc.value.status_code == 401
        await client_401.aclose()

        # 429
        transport_429 = httpx.MockTransport(lambda req: httpx.Response(429, headers={"retry-after": "2.0"}, text='{"error": {"type": "rate_limit_error"}}'))
        client_429 = httpx.AsyncClient(transport=transport_429)
        adapter_429 = AnthropicProviderAdapter(api_key="key", http_client=client_429)
        with pytest.raises(LLMProviderRateLimitError) as exc:
            await adapter_429.generate(TextGenerationRequest(prompt="test"))
        assert exc.value.status_code == 429
        assert exc.value.retry_after == 2.0
        await client_429.aclose()

    asyncio.run(run())

