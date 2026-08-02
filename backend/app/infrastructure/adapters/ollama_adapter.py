import httpx
from typing import AsyncGenerator
from app.core.config import settings
from app.domain.ai.capabilities import (
    ITextGenerationCapability,
    TextGenerationRequest,
    TextGenerationResponse,
)

class OllamaTextGenAdapter(ITextGenerationCapability):
    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, default_model: str = settings.DEFAULT_LLM_MODEL) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.default_model,
            "prompt": request.prompt,
            "system": request.system_prompt or "",
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            }
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                raise RuntimeError(f"Ollama error ({response.status_code}): {response.text}")
            data = response.json()
            return TextGenerationResponse(
                text=data.get("response", ""),
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
            )

    async def stream(self, request: TextGenerationRequest) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.default_model,
            "prompt": request.prompt,
            "system": request.system_prompt or "",
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                async for line in response.aiter_lines():
                    if line:
                        import json
                        chunk = json.loads(line)
                        yield chunk.get("response", "")
