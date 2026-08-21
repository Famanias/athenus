import json
import logging
import random
import re
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtractedNoteSection:
    heading: str
    body: str
    key_takeaways: List[str] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    source_chunk_ids: List[str] = field(default_factory=list)


@dataclass
class ExtractedNotes:
    title: str
    summary: str
    sections: List[ExtractedNoteSection] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# LLM prompt assembly & response parsing
# ---------------------------------------------------------------------------
def build_notes_prompt(
    chunks: List[dict],
    concepts: Optional[List[dict]] = None,
    custom_instruction: Optional[str] = None,
) -> str:
    """Build a structured prompt instructing the LLM to output notes strictly in JSON format."""
    concept_blob = ""
    if concepts:
        concept_blob = "\nExtracted Concepts & Keywords:\n" + "\n".join(
            f"- {c.get('name', '')}: {c.get('description', '')} [chunks: {', '.join(c.get('source_chunk_ids', []))}]"
            for c in concepts if c.get("name")
        )

    chunk_blob = "\n".join(
        f"[chunk:{c.get('id', '')}] ({float(c.get('start_time', 0.0)):.1f}s - {float(c.get('end_time', 0.0)):.1f}s) {c.get('text', '')}"
        for c in chunks
    )

    extra_instruction = f"\nAdditional User Formatting Instructions: {custom_instruction}\n" if custom_instruction else ""

    return f"""Transform the provided transcript into clean, well-structured notes in markdown. Preserve the user's intent and all substantive information. Remove filler, small talk, false starts, and redundant content. For personal notes, improve grammar and structure for readability. For meeting transcripts, extract key discussion points, decisions, action items, and follow-ups.
{extra_instruction}
Requirements:
1. "title": A clear, informative topic or meeting title for these notes.
2. "summary": A concise high-level overview synthesizing the core discussion and takeaways.
3. "sections": Group the content into logical, chronological, or thematic sections. For each section:
   - "heading": Descriptive section heading.
   - "body": Clean, well-structured notes in markdown (use bullet points, headings, or short paragraphs).
   - "key_takeaways": 2-4 concise bullet points highlighting crucial facts, decisions, or conclusions.
   - "start_time": The start timestamp (in seconds) representing this section from the referenced chunks.
   - "end_time": The end timestamp (in seconds) representing this section from the referenced chunks.
   - "source_chunk_ids": List of chunk IDs referenced in this section (e.g. ["chunk_0", "chunk_1"]).
4. "action_items": Key action items, decisions, and follow-up tasks.

Respond with ONLY a valid JSON object matching exactly this schema:
{{
  "title": "Topic or Meeting Title",
  "summary": "High-level summary of the entire session...",
  "sections": [
    {{
      "heading": "Section Heading",
      "body": "Markdown notes with key details...",
      "key_takeaways": ["Takeaway 1", "Takeaway 2"],
      "start_time": 0.0,
      "end_time": 125.4,
      "source_chunk_ids": ["chunk_0", "chunk_1"]
    }}
  ],
  "action_items": [
    "Action item or follow-up 1",
    "Action item or follow-up 2"
  ]
}}
{concept_blob}

Transcript Chunks:
{chunk_blob}
"""


def parse_llm_notes(text: str) -> Optional[ExtractedNotes]:
    """Parse JSON notes response from LLM, handling markdown code fences and minor formatting anomalies."""
    if not text or not text.strip():
        return None

    cleaned_text = text.strip()
    # Strip markdown code blocks if present
    if cleaned_text.startswith("```"):
        cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text)

    try:
        match = re.search(r"\{.*\}", cleaned_text, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(0))
    except Exception as exc:
        logger.warning("parse_llm_notes: JSON decoding failed — %s", exc)
        return None

    if not isinstance(data, dict):
        return None

    title = str(data.get("title") or "Lecture Study Notes").strip()
    summary = str(data.get("summary") or "").strip()
    action_items = [str(a).strip() for a in (data.get("action_items") or []) if str(a).strip()]

    raw_sections = data.get("sections") or []
    sections: List[ExtractedNoteSection] = []

    for s in raw_sections:
        if not isinstance(s, dict):
            continue
        heading = str(s.get("heading") or "").strip()
        body = str(s.get("body") or "").strip()
        if not heading and not body:
            continue

        raw_takeaways = s.get("key_takeaways") or []
        takeaways = [str(t).strip() for t in raw_takeaways if str(t).strip()]

        start_time = None
        end_time = None
        if s.get("start_time") is not None:
            try:
                start_time = float(s["start_time"])
            except (ValueError, TypeError):
                pass
        if s.get("end_time") is not None:
            try:
                end_time = float(s["end_time"])
            except (ValueError, TypeError):
                pass

        raw_chunk_ids = s.get("source_chunk_ids") or []
        chunk_ids = [str(c).strip() for c in raw_chunk_ids if str(c).strip()]

        sections.append(
            ExtractedNoteSection(
                heading=heading or "Key Discussion",
                body=body,
                key_takeaways=takeaways,
                start_time=start_time,
                end_time=end_time,
                source_chunk_ids=chunk_ids,
            )
        )

    if not sections and not summary:
        return None

    return ExtractedNotes(
        title=title,
        summary=summary,
        sections=sections,
        action_items=action_items,
    )


# ---------------------------------------------------------------------------
# Deterministic heuristic fallback (offline / no-LLM)
# ---------------------------------------------------------------------------
def generate_notes_heuristic(
    chunks: List[dict],
    concepts: Optional[List[dict]] = None,
    version: int = 1,
) -> ExtractedNotes:
    """Generate structured study notes deterministically from transcript chunks and concepts without an LLM."""
    if not chunks:
        return ExtractedNotes(
            title="Empty Notes",
            summary="No transcript chunks provided for note generation.",
            sections=[],
            action_items=[],
        )

    # Sort chunks by chunk_index or start_time
    sorted_chunks = sorted(chunks, key=lambda c: (c.get("chunk_index", 0), float(c.get("start_time", 0.0))))
    concept_names = [c["name"] for c in (concepts or []) if c.get("name")]

    # Determine title
    if concept_names:
        title = f"Study Notes: {', '.join(concept_names[:3])}"
    else:
        first_text = sorted_chunks[0].get("text", "").strip()
        first_words = first_text.split()[:6]
        title = f"Study Notes: {' '.join(first_words)}…" if first_words else "Lecture Study Notes"

    # Cluster chunks into sections (group ~3-5 chunks per section)
    group_size = 4 if len(sorted_chunks) >= 8 else max(1, len(sorted_chunks) // 2 or 1)
    sections: List[ExtractedNoteSection] = []

    for i in range(0, len(sorted_chunks), group_size):
        group = sorted_chunks[i : i + group_size]
        if not group:
            continue

        start_time = float(group[0].get("start_time", 0.0))
        end_time = float(group[-1].get("end_time", 0.0))
        chunk_ids = [str(c.get("id")) for c in group if c.get("id")]

        # Match concepts present in this group
        group_text = " ".join(c.get("text", "") for c in group)
        matched_concepts = [c for c in concept_names if c.lower() in group_text.lower()]

        if matched_concepts:
            heading = f"Discussion: {', '.join(matched_concepts[:2])}"
        else:
            sec_idx = (i // group_size) + 1
            heading = f"Section {sec_idx}: Overview ({start_time:.0f}s - {end_time:.0f}s)"

        # Build body with bullet points from chunks
        bullets = []
        takeaways = []
        for c in group:
            t = c.get("text", "").strip()
            if not t:
                continue
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]
            for s in sentences:
                if len(s) > 15:
                    bullets.append(f"- {s}")
            if sentences:
                takeaways.append(sentences[0])

        body_text = "\n".join(bullets[:6]) if bullets else group_text[:500]
        selected_takeaways = takeaways[:3] if takeaways else ["Review discussion points in this section."]

        sections.append(
            ExtractedNoteSection(
                heading=heading,
                body=body_text,
                key_takeaways=selected_takeaways,
                start_time=start_time,
                end_time=end_time,
                source_chunk_ids=chunk_ids,
            )
        )

    summary = (
        f"Structured synthesis of {len(sorted_chunks)} transcript segments covering "
        f"key educational concepts from {sorted_chunks[0].get('start_time', 0):.0f}s to "
        f"{sorted_chunks[-1].get('end_time', 0):.0f}s."
    )

    action_items = [
        f"Review detailed notes on {sections[0].heading if sections else 'the lecture'}.",
        "Verify understanding of key formulas and definitions mentioned in the transcript.",
        "Test recall using corresponding flashcards and quizzes for this workspace.",
    ]

    return ExtractedNotes(
        title=title,
        summary=summary,
        sections=sections,
        action_items=action_items,
    )
