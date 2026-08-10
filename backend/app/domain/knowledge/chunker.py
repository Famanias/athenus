from typing import Any, Dict, List
from app.domain.ai.capabilities import TranscriptSegmentDTO
from app.domain.knowledge.entities import SourceContentUnit, TranscriptChunk

def count_tokens(text: str) -> int:
    """Accurately count tokens using tiktoken BPE if available, or conservative 1.35x word-to-token / character fallback."""
    if not text:
        return 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        words = len(text.split())
        chars = len(text)
        return max(int(words * 1.35), int(chars / 3.2))


def split_text_into_subchunks(text: str, target_words: int = 500, max_tokens: int = 750) -> List[str]:
    """Split page text into sub-page chunks with ~500 words target and hard ceiling of 750 tokens."""
    text = text.strip()
    if not text:
        return []

    if count_tokens(text) <= max_tokens and len(text.split()) <= target_words:
        return [text]

    import re
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    units_to_pack: List[str] = []
    for p in paragraphs:
        if count_tokens(p) > max_tokens:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', p) if s.strip()]
            for s in sentences:
                if count_tokens(s) > max_tokens:
                    words = s.split()
                    current_w: List[str] = []
                    for w in words:
                        current_w.append(w)
                        if count_tokens(" ".join(current_w)) >= max_tokens - 10:
                            units_to_pack.append(" ".join(current_w))
                            current_w = []
                    if current_w:
                        units_to_pack.append(" ".join(current_w))
                else:
                    units_to_pack.append(s)
        else:
            units_to_pack.append(p)

    subchunks: List[str] = []
    current_pack: List[str] = []

    for block in units_to_pack:
        candidate = "\n\n".join(current_pack + [block]) if current_pack else block
        cand_words = len(candidate.split())
        cand_tokens = count_tokens(candidate)

        if current_pack and (cand_words > target_words or cand_tokens > max_tokens):
            subchunks.append("\n\n".join(current_pack))
            current_pack = [block]
        else:
            current_pack.append(block)

    if current_pack:
        subchunks.append("\n\n".join(current_pack))

    final_subchunks: List[str] = []
    for sc in subchunks:
        if count_tokens(sc) <= max_tokens:
            final_subchunks.append(sc)
        else:
            words = sc.split()
            current_w = []
            for w in words:
                current_w.append(w)
                if count_tokens(" ".join(current_w)) >= max_tokens - 10:
                    final_subchunks.append(" ".join(current_w))
                    current_w = []
            if current_w:
                final_subchunks.append(" ".join(current_w))

    return final_subchunks


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

    def chunk_document_pages(
        self,
        pages: List[Dict[str, Any]],
        document_id: str,
        workspace_id: str,
        target_word_count: int = 500,
        max_tokens: int = 750
    ) -> List[SourceContentUnit]:
        """Chunk document pages into ~500-word sub-page chunks enforcing a hard ceiling of 750 tokens, preserving location metadata."""
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

            sub_texts = split_text_into_subchunks(text, target_words=target_word_count, max_tokens=max_tokens)
            total_subchunks = len(sub_texts)

            for sub_idx, sub_text in enumerate(sub_texts):
                words = sub_text.split()
                location = {
                    "type": "document",
                    "page": page_num,
                    "section": section,
                    "page_type": page_type,
                    "sub_chunk_index": sub_idx,
                    "total_sub_chunks": total_subchunks,
                    "bbox": None
                }

                units.append(
                    SourceContentUnit(
                        id=f"{document_id}_chunk_{chunk_idx}",
                        source_id=document_id,
                        workspace_id=workspace_id,
                        text=sub_text,
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

