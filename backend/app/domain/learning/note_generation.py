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


def _extract_json_object(text: str) -> Optional[dict]:
    """Extract a dictionary JSON object from LLM response using multi-stage extraction."""
    if not text or not text.strip():
        return None
    cleaned = text.strip()

    # Strategy 1: Direct JSON parse
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Strategy 2: Code fence extraction
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence_match:
        try:
            data = json.loads(fence_match.group(1))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # Strategy 3: Balanced brace matching for top-level JSON objects
    start_idx = cleaned.find("{")
    while start_idx != -1:
        depth = 0
        in_string = False
        escape = False
        for idx in range(start_idx, len(cleaned)):
            char = cleaned[idx]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
            else:
                if char == '"':
                    in_string = True
                elif char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = cleaned[start_idx : idx + 1]
                        try:
                            data = json.loads(candidate)
                            if isinstance(data, dict):
                                return data
                        except Exception:
                            pass
                        break
        start_idx = cleaned.find("{", start_idx + 1)

    return None


def parse_llm_notes(text: str) -> Optional[ExtractedNotes]:
    """Parse JSON notes response from LLM, handling markdown code fences, prose, and minor schema variations."""
    if not text or not text.strip():
        logger.debug("parse_llm_notes: empty text received")
        return None

    data = _extract_json_object(text)
    if not data or not isinstance(data, dict):
        logger.warning("parse_llm_notes: failed to extract valid JSON object from raw response (len=%d)", len(text))
        return None

    # Flexible field extraction
    title = str(data.get("title") or data.get("topic") or "Lecture Study Notes").strip()

    raw_summary = data.get("summary") or data.get("overview") or ""
    if isinstance(raw_summary, list):
        summary = "\n".join(str(item).strip() for item in raw_summary if str(item).strip())
    else:
        summary = str(raw_summary).strip()

    raw_action_items = data.get("action_items") or data.get("actions") or data.get("next_steps") or data.get("follow_ups") or []
    if isinstance(raw_action_items, str):
        action_items = [line.strip().lstrip("-*• ") for line in raw_action_items.splitlines() if line.strip()]
    elif isinstance(raw_action_items, list):
        action_items = [str(a).strip().lstrip("-*• ") for a in raw_action_items if str(a).strip()]
    else:
        action_items = []

    raw_sections = data.get("sections") or data.get("subsections") or data.get("modules") or data.get("topics") or []
    if isinstance(raw_sections, dict):
        raw_sections = list(raw_sections.values())
    elif not isinstance(raw_sections, list):
        raw_sections = []

    sections: List[ExtractedNoteSection] = []

    for s in raw_sections:
        if not isinstance(s, dict):
            continue
        heading = str(s.get("heading") or s.get("title") or s.get("topic") or "").strip()
        body = str(s.get("body") or s.get("content") or s.get("notes") or s.get("text") or "").strip()
        if not heading and not body:
            continue

        raw_takeaways = s.get("key_takeaways") or s.get("takeaways") or s.get("points") or []
        if isinstance(raw_takeaways, str):
            takeaways = [line.strip().lstrip("-*• ") for line in raw_takeaways.splitlines() if line.strip()]
        elif isinstance(raw_takeaways, list):
            takeaways = [str(t).strip().lstrip("-*• ") for t in raw_takeaways if str(t).strip()]
        else:
            takeaways = []

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

        raw_chunk_ids = s.get("source_chunk_ids") or s.get("chunk_ids") or []
        if isinstance(raw_chunk_ids, str):
            chunk_ids = [c.strip() for c in raw_chunk_ids.split(",") if c.strip()]
        elif isinstance(raw_chunk_ids, list):
            chunk_ids = [str(c).strip() for c in raw_chunk_ids if str(c).strip()]
        else:
            chunk_ids = []

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
        logger.warning("parse_llm_notes: parsed JSON has neither sections nor summary")
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
