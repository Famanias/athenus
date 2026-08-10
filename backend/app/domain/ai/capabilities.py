from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Protocol

@dataclass
class TextGenerationRequest:
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2048
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

@dataclass
class DocumentPageDTO:
    page_number: int
    text: str
    page_type: str = "text"  # text | scanned | image | mixed
    section_title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DocumentParsingRequest:
    file_path: str
    file_format: Optional[str] = None
    max_pages: int = 2000
    max_file_size_mb: float = 100.0

@dataclass
class DocumentParsingResponse:
    markdown: str
    pages: List[DocumentPageDTO]
    file_format: str
    total_pages: int
    has_scanned_pages: bool = False
    has_tables: bool = False
    language_detected: str = "en"

class IDocumentParsingCapability(Protocol):
    async def parse_document(self, request: DocumentParsingRequest) -> DocumentParsingResponse: ...

@dataclass
class OCRLineDTO:
    text: str
    confidence: float = 1.0
    bbox: List[float] = field(default_factory=list)

@dataclass
class OCRRequest:
    image_path: str
    language: str = "en"
    page_number: int = 1

@dataclass
class OCRResponse:
    text: str
    confidence: float = 1.0
    lines: List[OCRLineDTO] = field(default_factory=list)

class IOCRCapability(Protocol):
    async def perform_ocr(self, request: OCRRequest) -> OCRResponse: ...


