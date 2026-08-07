import httpx
import json
from typing import AsyncGenerator, Dict, List, Optional
from app.domain.ai.capabilities import TextGenerationRequest, TextGenerationResponse
from app.domain.ai.provider_interface import BaseLLMProvider, LLMProviderCapabilities, LLMModelMetadataDTO

class AnthropicProviderAdapter(BaseLLMProvider):
    """Tier 2 Adapter implementing Anthropic's native `/v1/messages` REST API specification."""

    def __init__(
        self,
        api_key: Optional[str],
        base_url: str = "https://api.anthropic.com/v1",
        default_model: str = "claude-3-5-sonnet-latest",
        http_client: Optional[httpx.AsyncClient] = None
    ) -> None:
        self._env_api_key = (api_key or "").strip()
        self.api_key = self._env_api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._http_client = http_client

    @property
    def provider_id(self) -> str:
        return "anthropic"

    @property
    def name(self) -> str:
        return "Anthropic Claude API"

    @property
    def is_local(self) -> bool:
        return False

    def set_api_key(self, api_key: Optional[str]) -> None:
        if api_key and api_key.strip():
            self.api_key = api_key.strip()
        else:
            self.api_key = self._env_api_key

    def set_model(self, model: str) -> None:
        self.default_model = model

    def _resolve_model(self) -> str:
        """Resolve the active model from persisted per-provider settings, falling back to default."""
        try:
            from app.domain.settings.settings_service import SettingsService
            active_models = SettingsService().get_settings().active_models
            selected = (active_models or {}).get(self.provider_id)
            if selected:
                return selected
        except Exception:
            pass
        return self.default_model

    def _get_client(self) -> httpx.AsyncClient:
        return self._http_client or httpx.AsyncClient(timeout=30.0)

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def get_capabilities(self) -> LLMProviderCapabilities:
        return LLMProviderCapabilities(
            supports_streaming=True,
            supports_vision=True,
            supports_function_calling=True,
            supports_model_discovery=True,
            max_context_window=200000
        )

    async def list_models(self, force_refresh: bool = False) -> List[LLMModelMetadataDTO]:
        return [
            LLMModelMetadataDTO(id="claude-3-5-sonnet-latest", name="Claude 3.5 Sonnet", context_window=200000),
            LLMModelMetadataDTO(id="claude-3-5-haiku-latest", name="Claude 3.5 Haiku", context_window=200000),
            LLMModelMetadataDTO(id="claude-3-opus-latest", name="Claude 3 Opus", context_window=200000),
        ]

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        if not self.api_key:
            return TextGenerationResponse(
                text="⚠️ Anthropic API Key Missing: Please enter your Anthropic API Key in .env.",
                prompt_tokens=0,
                completion_tokens=0
            )

        url = f"{self.base_url}/messages"
        headers = self._build_headers()
        payload = {
            "model": self._resolve_model(),
            "system": request.system_prompt or "You are Athenus AI Assistant.",
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens or 1024,
            "temperature": request.temperature
        }

        client = self._get_client()
        should_close = self._http_client is None

        try:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                content_blocks = data.get("content", [])
                text = content_blocks[0].get("text", "") if content_blocks else ""
                usage = data.get("usage", {})
                return TextGenerationResponse(
                    text=text,
                    prompt_tokens=usage.get("input_tokens", 0),
                    completion_tokens=usage.get("output_tokens", 0),
                    finish_reason=data.get("stop_reason", "end_turn")
                )
            else:
                err_detail = resp.text[:200]
                return TextGenerationResponse(
                    text=f"⚠️ Anthropic API Error ({resp.status_code}): {err_detail}",
                    prompt_tokens=0,
                    completion_tokens=0
                )
        except Exception as e:
            return TextGenerationResponse(
                text=f"⚠️ Anthropic Network Error: Failed to reach Anthropic API ({str(e)}).",
                prompt_tokens=0,
                completion_tokens=0
            )
        finally:
            if should_close:
                await client.aclose()

    async def stream(self, request: TextGenerationRequest) -> AsyncGenerator[str, None]:
        if not self.api_key:
            yield "⚠️ Anthropic API Key Missing: Please enter your Anthropic API Key in .env."
            return

        url = f"{self.base_url}/messages"
        headers = self._build_headers()
        payload = {
            "model": self._resolve_model(),
            "system": request.system_prompt or "You are Athenus AI Assistant.",
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens or 1024,
            "temperature": request.temperature,
            "stream": True
        }

        client = self._get_client()
        should_close = self._http_client is None

        try:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    yield f"⚠️ Anthropic API Error ({resp.status_code})"
                    return

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    line_data = line[5:].strip()
                    try:
                        event_data = json.loads(line_data)
                        event_type = event_data.get("type")
                        if event_type == "content_block_delta":
                            delta = event_data.get("delta", {})
                            text = delta.get("text", "")
                            if text:
                                yield text
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            yield f"⚠️ Anthropic Streaming Error: {str(e)}"
        finally:
            if should_close:
                await client.aclose()
