import re
from typing import Any, Dict, List


def parse_chat_citations(text: str) -> List[Dict[str, Any]]:
    """Parse both video timestamp badges ([MM:SS]) and document page badges ([Page X] / [Document Page X]) from AI response text."""
    citations: List[Dict[str, Any]] = []

    # 1. Regex for video timestamp badges: [MM:SS] or [MM:SS - MM:SS]
    video_pattern = re.compile(r"\[(\d{1,2}:\d{2})(?:\s*-\s*(\d{1,2}:\d{2}))?\]")
    for match in video_pattern.finditer(text):
        start_str = match.group(1)
        end_str = match.group(2) or start_str

        def _to_seconds(ts: str) -> float:
            parts = ts.split(":")
            return float(int(parts[0]) * 60 + int(parts[1]))

        citations.append({
            "source_type": "video",
            "badge_text": match.group(0),
            "start_time": _to_seconds(start_str),
            "end_time": _to_seconds(end_str),
            "page_number": None,
        })

    # 2. Regex for document page badges: [Document Page X], [Page X], [Doc p.X]
    doc_pattern = re.compile(r"\[(?:Document\s+Page|Page|Doc,\s*p\.)\s*(\d+)(?:\s*\((.*?)\))?\]", re.IGNORECASE)
    for match in doc_pattern.finditer(text):
        page_num = int(match.group(1))
        section = match.group(2) or f"Page {page_num}"
        citations.append({
            "source_type": "pdf",
            "badge_text": match.group(0),
            "start_time": None,
            "end_time": None,
            "page_number": page_num,
            "section_title": section,
        })

    return citations
