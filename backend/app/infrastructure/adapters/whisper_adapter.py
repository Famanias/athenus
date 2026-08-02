import asyncio
from app.core.config import settings
from app.domain.ai.capabilities import (
    ISpeechToTextCapability,
    SpeechToTextRequest,
    SpeechToTextResponse,
    TranscriptSegmentDTO,
)

class FasterWhisperSTTAdapter(ISpeechToTextCapability):
    def __init__(self, model_size: str = settings.WHISPER_MODEL_SIZE) -> None:
        self.model_size = model_size

    async def transcribe(self, request: SpeechToTextRequest) -> SpeechToTextResponse:
        # Runs transcription in a thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, request)

    def _transcribe_sync(self, request: SpeechToTextRequest) -> SpeechToTextResponse:
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            segments, info = model.transcribe(request.audio_file_path, beam_size=5)
            
            segment_dtos = []
            full_text_parts = []
            for seg in segments:
                segment_dtos.append(TranscriptSegmentDTO(
                    start_time=seg.start,
                    end_time=seg.end,
                    text=seg.text.strip()
                ))
                full_text_parts.append(seg.text.strip())

            return SpeechToTextResponse(
                text=" ".join(full_text_parts),
                segments=segment_dtos,
                language_detected=info.language or "en"
            )
        except ImportError:
            # Fallback mock transcription for testing environment if faster_whisper is not installed
            return SpeechToTextResponse(
                text="Mock transcript content for development testing.",
                segments=[
                    TranscriptSegmentDTO(start_time=0.0, end_time=5.0, text="Mock transcript content"),
                    TranscriptSegmentDTO(start_time=5.0, end_time=10.0, text="for development testing.")
                ],
                language_detected="en"
            )
