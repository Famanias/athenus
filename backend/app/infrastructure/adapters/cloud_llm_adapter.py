import httpx
from typing import AsyncGenerator, Optional
from app.domain.ai.capabilities import (
    ITextGenerationCapability,
    TextGenerationRequest,
    TextGenerationResponse,
)

class CloudTextGenAdapter(ITextGenerationCapability):
    """Generic OpenAI-compatible Cloud LLM Adapter supporting OpenRouter, Groq, OpenAI, etc."""

    def __init__(
        self,
        provider_name: str,
        base_url: str,
        default_model: str,
        api_key: Optional[str] = None
    ) -> None:
        self.provider_name = provider_name
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.api_key = api_key or ""

    def set_api_key(self, api_key: str) -> None:
        self.api_key = api_key

    def set_model(self, model: str) -> None:
        self.default_model = model

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        if not self.api_key:
            return TextGenerationResponse(
                text=f"⚠️ {self.provider_name} API Key Missing: Please enter your {self.provider_name} API Key in System Settings.",
                prompt_tokens=0,
                completion_tokens=0
            )

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://athenus.local",
            "X-Title": "Athenus Knowledge OS",
        }
        payload = {
            "model": self.default_model,
            "messages": [
                {"role": "system", "content": request.system_prompt or "You are Athenus AI Assistant."},
                {"role": "user", "content": request.prompt}
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens or 512
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    choices = data.get("choices", [])
                    content = choices[0]["message"]["content"] if choices else ""
                    usage = data.get("usage", {})
                    return TextGenerationResponse(
                        text=content,
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0)
                    )
                else:
                    err_detail = response.text[:200]
                    return TextGenerationResponse(
                        text=f"⚠️ {self.provider_name} API Error ({response.status_code}): {err_detail}",
                        prompt_tokens=0,
                        completion_tokens=0
                    )
        except Exception as e:
            return TextGenerationResponse(
                text=f"⚠️ {self.provider_name} Network Error: Failed to reach cloud API endpoint ({str(e)}).",
                prompt_tokens=0,
                completion_tokens=0
            )

    async def stream(self, request: TextGenerationRequest) -> AsyncGenerator[str, None]:
        res = await self.generate(request)
        yield res.text
