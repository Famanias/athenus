from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional, Protocol

@dataclass
class TextGenerationRequest:
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1024
    stop_sequences: List[str] = field(default_factory=list)

@dataclass
class TextGenerationResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    finish_reason: str = "stop"

@dataclass
class SpeechToTextRequest:
    audio_file_path: str
    language: Optional[str] = None
    word_timestamps: bool = True

@dataclass
class TranscriptSegmentDTO:
    start_time: float
    end_time: float
    text: str

@dataclass
class SpeechToTextResponse:
    text: str
    segments: List[TranscriptSegmentDTO]
    language_detected: str = "en"

class ITextGenerationCapability(Protocol):
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse: ...
    async def stream(self, request: TextGenerationRequest) -> AsyncGenerator[str, None]: ...

class ISpeechToTextCapability(Protocol):
    async def transcribe(self, request: SpeechToTextRequest) -> SpeechToTextResponse: ...

class IEmbeddingCapability(Protocol):
    async def embed_texts(self, texts: List[str]) -> List[List[float]]: ...
    async def embed_query(self, query: str) -> List[float]: ...

class IVisionCapability(Protocol):
    async def describe_image(self, image_path: str, prompt: str) -> str: ...

class IReasoningCapability(Protocol):
    async def evaluate_reasoning(self, premise: str, hypothesis: str) -> Dict[str, float]: ...
