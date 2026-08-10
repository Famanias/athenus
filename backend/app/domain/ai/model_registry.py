from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

class ModelCapabilityType(str, Enum):
    TEXT_GENERATION = "text_generation"
    SPEECH_TO_TEXT = "speech_to_text"
    EMBEDDINGS = "embeddings"
    VISION = "vision"
    REASONING = "reasoning"

class ModelProviderType(str, Enum):
    OLLAMA = "ollama"
    FASTER_WHISPER = "faster_whisper"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    QDRANT = "qdrant"
    GROQ = "groq"
    OPENROUTER = "openrouter"
    GEMINI = "gemini"
    CLAUDE = "claude"
    DEEPGRAM = "deepgram"

@dataclass
class ModelMetadata:
    model_id: str
    provider: ModelProviderType
    capabilities: List[ModelCapabilityType]
    context_window: int = 4096
    vram_required_mb: int = 0
    is_local: bool = True
    is_installed: bool = False
    display_name: str = ""

class ModelRegistry:
    def __init__(self) -> None:
        self._models: Dict[str, ModelMetadata] = {}
        self._register_default_models()

    def register(self, metadata: ModelMetadata) -> None:
        self._models[metadata.model_id] = metadata

    def get(self, model_id: str) -> Optional[ModelMetadata]:
        return self._models.get(model_id)

    def find_by_capability(self, capability: ModelCapabilityType, local_only: bool = False) -> List[ModelMetadata]:
        matches = []
        for model in self._models.values():
            if capability in model.capabilities:
                if local_only and not model.is_local:
                    continue
                matches.append(model)
        return matches

    def _register_default_models(self) -> None:
        self.register(ModelMetadata(
            model_id="llama3:8b",
            provider=ModelProviderType.OLLAMA,
            capabilities=[ModelCapabilityType.TEXT_GENERATION],
            context_window=8192,
            vram_required_mb=5120,
            is_local=True,
            is_installed=True,
            display_name="Llama 3 (8B Local)"
        ))
        self.register(ModelMetadata(
            model_id="whisper-base",
            provider=ModelProviderType.FASTER_WHISPER,
            capabilities=[ModelCapabilityType.SPEECH_TO_TEXT],
            context_window=0,
            vram_required_mb=1024,
            is_local=True,
            is_installed=True,
            display_name="Faster-Whisper (Base Local)"
        ))
        self.register(ModelMetadata(
            model_id="bge-small-en-v1.5",
            provider=ModelProviderType.SENTENCE_TRANSFORMERS,
            capabilities=[ModelCapabilityType.EMBEDDINGS],
            context_window=512,
            vram_required_mb=512,
            is_local=True,
            is_installed=True,
            display_name="BAAI BGE Small (Local Embeddings)"
        ))
        self.register(ModelMetadata(
            model_id="openrouter",
            provider=ModelProviderType.OPENROUTER,
            capabilities=[ModelCapabilityType.TEXT_GENERATION],
            context_window=131072,
            is_local=False,
            is_installed=True,
            display_name="OpenRouter Cloud API"
        ))
        self.register(ModelMetadata(
            model_id="groq",
            provider=ModelProviderType.GROQ,
            capabilities=[ModelCapabilityType.TEXT_GENERATION],
            context_window=128000,
            is_local=False,
            is_installed=True,
            display_name="Groq Llama 3.3 70B (128k Context)"
        ))
        self.register(ModelMetadata(
            model_id="claude",
            provider=ModelProviderType.CLAUDE,
            capabilities=[ModelCapabilityType.TEXT_GENERATION],
            context_window=200000,
            is_local=False,
            is_installed=True,
            display_name="Anthropic Claude 3.5 Sonnet (200k Context)"
        ))
        self.register(ModelMetadata(
            model_id="openai",
            provider=ModelProviderType.OPENROUTER,
            capabilities=[ModelCapabilityType.TEXT_GENERATION],
            context_window=128000,
            is_local=False,
            is_installed=True,
            display_name="OpenAI GPT-4o (128k Context)"
        ))
