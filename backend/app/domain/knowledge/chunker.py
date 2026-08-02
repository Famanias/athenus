from typing import List
from app.domain.ai.capabilities import TranscriptSegmentDTO
from app.domain.knowledge.entities import TranscriptChunk

class SemanticChunker:
    """Timestamp-aware semantic chunker grouping transcript segments while preserving exact time windows."""
    
    def __init__(self, target_word_count: int = 250, min_word_count: int = 50) -> None:
        self.target_word_count = target_word_count
        self.min_word_count = min_word_count

    def chunk_transcript(self, segments: List[TranscriptSegmentDTO], media_id: str, workspace_id: str) -> List[TranscriptChunk]:
        if not segments:
            return []

        chunks: List[TranscriptChunk] = []
        current_words: List[str] = []
        current_segments: List[TranscriptSegmentDTO] = []
        chunk_idx = 0

        for seg in segments:
            seg_words = seg.text.split()
            if not seg_words:
                continue

            current_segments.append(seg)
            current_words.extend(seg_words)

            if len(current_words) >= self.target_word_count:
                chunks.append(self._create_chunk(current_segments, current_words, media_id, workspace_id, chunk_idx))
                chunk_idx += 1
                current_segments = []
                current_words = []

        if current_segments:
            chunks.append(self._create_chunk(current_segments, current_words, media_id, workspace_id, chunk_idx))

        return chunks

    def _create_chunk(
        self,
        segments: List[TranscriptSegmentDTO],
        words: List[str],
        media_id: str,
        workspace_id: str,
        chunk_idx: int
    ) -> TranscriptChunk:
        start_time = segments[0].start_time if segments else 0.0
        end_time = segments[-1].end_time if segments else 0.0
        text = " ".join([s.text for s in segments])

        return TranscriptChunk(
            id=f"{media_id}_chunk_{chunk_idx}",
            media_id=media_id,
            workspace_id=workspace_id,
            text=text,
            start_time=start_time,
            end_time=end_time,
            chunk_index=chunk_idx,
            word_count=len(words)
        )
