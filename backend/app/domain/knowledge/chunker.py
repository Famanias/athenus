from typing import Any, Dict, List
from app.domain.ai.capabilities import TranscriptSegmentDTO
from app.domain.knowledge.entities import SourceContentUnit, TranscriptChunk

class SemanticChunker:
    """Timestamp & page-aware semantic chunker grouping segments or document pages while preserving location metadata."""
    
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

    def chunk_document_pages(self, pages: List[Dict[str, Any]], document_id: str, workspace_id: str) -> List[SourceContentUnit]:
        """Chunk document pages preserving page numbers, section titles, and location metadata."""
        if not pages:
            return []

        units: List[SourceContentUnit] = []
        chunk_idx = 0

        for page in pages:
            text = str(page.get("text", "")).strip()
            if not text:
                continue

            page_num = page.get("page_number", 1)
            section = page.get("section_title") or f"Page {page_num}"
            page_type = page.get("page_type", "text")
            words = text.split()

            location = {
                "type": "document",
                "page": page_num,
                "section": section,
                "page_type": page_type,
                "bbox": None
            }

            units.append(
                SourceContentUnit(
                    id=f"{document_id}_chunk_{chunk_idx}",
                    source_id=document_id,
                    workspace_id=workspace_id,
                    text=text,
                    location=location,
                    chunk_index=chunk_idx,
                    word_count=len(words)
                )
            )
            chunk_idx += 1

        return units

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

        location = {
            "type": "video",
            "start_time": start_time,
            "end_time": end_time
        }

        return TranscriptChunk(
            id=f"{media_id}_chunk_{chunk_idx}",
            media_id=media_id,
            workspace_id=workspace_id,
            text=text,
            start_time=start_time,
            end_time=end_time,
            chunk_index=chunk_idx,
            word_count=len(words),
            location=location
        )

