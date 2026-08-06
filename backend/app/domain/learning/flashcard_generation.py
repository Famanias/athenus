import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

CARD_TYPES = {"basic", "cloze", "definition", "true_false"}


@dataclass
class ExtractedFlashcard:
    card_type: str
    front: str
    back: Optional[str] = None
    cloze_text: Optional[str] = None
    options: Optional[List[str]] = None
    concept: Optional[str] = None
    source_chunk_ids: List[str] = field(default_factory=list)
    media_id: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


# ---------------------------------------------------------------------------
# LLM prompt assembly & response parsing
# ---------------------------------------------------------------------------
def build_flashcard_prompt(concepts: List[dict], chunks: List[dict]) -> str:
    concept_blob = "\n".join(
        f"- {c['name']}: {c.get('description', '')}  [chunks: {', '.join(c.get('source_chunk_ids', []))}]"
        for c in concepts
    )
    chunk_blob = "\n".join(
        f"[chunk:{c['id']}] ({c.get('start_time', 0.0):.1f}s - {c.get('end_time', 0.0):.1f}s) {c['text']}"
        for c in chunks
    )
    return f"""You are a spaced-repetition flashcard author for an educational video transcript.

Generate high-quality flashcards from the extracted concepts and transcript chunks below.
Create a balanced mix of card types: "basic" (front/back Q&A), "cloze" (fill-in-the-blank statement with {{{{c1::answer}}}}), "definition" (term -> concise definition), and "true_false" (statement requiring true/false, with options ["True", "False"]).

Rules:
- Every card MUST be grounded in the provided concepts and chunks.
- Include "concept" matching one of the provided concept names, and reference "source_chunk_ids" exactly as given.
- Distractors in "basic" and "definition" cards must be plausible but incorrect.

Respond with ONLY a JSON object in exactly this shape:
{{
  "cards": [
    {{"card_type": "basic", "front": "...", "back": "...", "concept": "Concept Name", "source_chunk_ids": ["chunk_0"]}},
    {{"card_type": "cloze", "cloze_text": "Statement with {{{{c1::answer}}}}", "back": "Explanation", "concept": "Concept Name", "source_chunk_ids": ["chunk_0"]}},
    {{"card_type": "definition", "front": "Term", "back": "Definition", "concept": "Concept Name", "source_chunk_ids": ["chunk_0"]}},
    {{"card_type": "true_false", "front": "Statement", "back": "True or False", "options": ["True", "False"], "concept": "Concept Name", "source_chunk_ids": ["chunk_0"]}}
  ]
}}

Extracted concepts:
{concept_blob}

Transcript chunks:
{chunk_blob}
"""


def parse_llm_flashcards(text: str) -> Optional[List[ExtractedFlashcard]]:
    if not text:
        return None
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(0))
    except Exception:
        return None

    raw_cards = data.get("cards") or []
    if not raw_cards:
        return None

    cards: List[ExtractedFlashcard] = []
    for c in raw_cards:
        card_type = str(c.get("card_type", "basic")).strip()
        if card_type not in CARD_TYPES:
            card_type = "basic"
        front = str(c.get("front", "")).strip()
        back = str(c.get("back", "") or c.get("cloze_text", "") or "").strip()
        if not front and not back:
            continue
        cards.append(
            ExtractedFlashcard(
                card_type=card_type,
                front=front,
                back=str(c.get("back", "") or "") or None,
                cloze_text=str(c.get("cloze_text", "") or "") or None,
                options=[str(x) for x in (c.get("options") or [])] or None,
                concept=str(c.get("concept", "") or "") or None,
                source_chunk_ids=[str(x) for x in (c.get("source_chunk_ids") or [])],
            )
        )
    return cards or None


# ---------------------------------------------------------------------------
# Deterministic heuristic fallback (no LLM required)
# ---------------------------------------------------------------------------
def _snippet_for_concept(concept_name: str, chunks: List[dict], max_len: int = 160) -> Tuple[Optional[str], Optional[float], Optional[float]]:
    """Return (snippet text, start_time, end_time) of the chunk mentioning the concept."""
    lowered = concept_name.lower()
    for chunk in chunks:
        text = str(chunk.get("text", ""))
        if lowered in text.lower():
            snippet = text.strip()
            if len(snippet) > max_len:
                snippet = snippet[:max_len].rsplit(" ", 1)[0] + "…"
            return snippet, float(chunk.get("start_time", 0.0) or 0.0), float(chunk.get("end_time", 0.0) or 0.0)
    return None, None, None


def generate_flashcards_heuristic(
    concepts: List[dict], chunks: List[dict], max_cards: int = 30
) -> List[ExtractedFlashcard]:
    """Deterministic concept-grounded card generation for offline environments."""
    if not concepts:
        return []

    chunk_by_id = {c["id"]: c for c in chunks}
    cards: List[ExtractedFlashcard] = []
    for concept in concepts:
        if len(cards) >= max_cards:
            break
        name = str(concept.get("name", "")).strip()
        if not name:
            continue
        description = str(concept.get("description", "") or "").strip()
        chunk_ids = concept.get("source_chunk_ids") or []
        if not chunk_ids and chunks:
            chunk_ids = [chunks[0]["id"]]
        first_chunk = chunk_by_id.get(chunk_ids[0]) if chunk_ids else None
        media_id = concept.get("media_id") or (first_chunk or {}).get("media_id")
        start_time = concept.get("start_time") if concept.get("start_time") is not None else (first_chunk or {}).get("start_time")
        end_time = concept.get("end_time") if concept.get("end_time") is not None else (first_chunk or {}).get("end_time")

        def provenance() -> dict:
            return {
                "concept": name,
                "source_chunk_ids": chunk_ids,
                "media_id": media_id,
                "start_time": start_time,
                "end_time": end_time,
            }

        if len(cards) < max_cards:
            snippet, s_start, s_end = _snippet_for_concept(name, chunks)
            back = description or snippet or f"Key concept: {name}."
            cards.append(ExtractedFlashcard(card_type="definition", front=name, back=back, **provenance()))
        if len(cards) < max_cards and (description or snippet):
            body = description or snippet
            cards.append(
                ExtractedFlashcard(
                    card_type="basic",
                    front=f"What is {name}?",
                    back=body,
                    **provenance(),
                )
            )
        if len(cards) < max_cards:
            cards.append(
                ExtractedFlashcard(
                    card_type="true_false",
                    front=f"{name} is a key concept discussed in this material.",
                    back="True",
                    options=["True", "False"],
                    **provenance(),
                )
            )
    return cards


def build_concept_payloads(concepts: List[dict], media_ids: List[str]) -> Tuple[List[dict], List[dict]]:
    """Split a list of ConceptNode-ish dicts into concept payloads and their referenced chunks."""
    chunk_ids: set = set()
    for c in concepts:
        for cid in (c.get("source_chunk_ids") or []):
            chunk_ids.add(cid)
    return concepts, []
