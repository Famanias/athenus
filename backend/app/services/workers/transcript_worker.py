import os
from typing import Optional
from app.domain.ai.capabilities import SpeechToTextRequest
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.events.event_bus import EventBus, DomainEvent
from app.infrastructure.media.ffmpeg_extractor import FFmpegAudioExtractor

class TranscriptWorker:
    """Worker handling audio extraction and Faster-Whisper transcription."""
    
    def __init__(
        self,
        event_bus: EventBus,
        ai_service_bus: AIServiceBus,
        audio_extractor: Optional[FFmpegAudioExtractor] = None
    ) -> None:
        self.event_bus = event_bus
        self.ai_service_bus = ai_service_bus
        self.audio_extractor = audio_extractor or FFmpegAudioExtractor()
        
        # Subscribe to MediaUploadedEvent
        self.event_bus.subscribe("MediaUploadedEvent", self.handle_media_uploaded)

    async def handle_media_uploaded(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        media_path = event.payload.get("file_path")
        workspace_id = event.payload.get("workspace_id")

        if not media_path:
            return

        # 1. Extract audio WAV file
        audio_path = f"{media_path}.wav"
        try:
            await self.audio_extractor.extract_audio(media_path, audio_path)
            
            # 2. Execute STT capability via AI Service Bus
            stt_capability = self.ai_service_bus.get_stt_capability()
            response = await stt_capability.transcribe(
                SpeechToTextRequest(audio_file_path=audio_path, word_timestamps=True)
            )

            # 3. Emit TranscriptCompletedEvent
            await self.event_bus.publish(DomainEvent(
                event_type="TranscriptCompletedEvent",
                aggregate_id=media_id,
                payload={
                    "media_id": media_id,
                    "workspace_id": workspace_id,
                    "full_text": response.text,
                    "segments": [
                        {"start_time": s.start_time, "end_time": s.end_time, "text": s.text}
                        for s in response.segments
                    ]
                }
            ))
        except Exception as e:
            await self.event_bus.publish(DomainEvent(
                event_type="ProcessingFailedEvent",
                aggregate_id=media_id,
                payload={"media_id": media_id, "error": str(e)}
            ))
