import json
import re
from dataclasses import dataclass, field
from typing import List, Optional

QUESTION_TYPES = {"mcq", "true_false"}


@dataclass
class ExtractedQuestion:
    question_text: str
    options: List[str]
    correct_index: int
    explanation: str
    concept: Optional[str] = None
    source_chunk_ids: List[str] = field(default_factory=list)
    media_id: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


# ---------------------------------------------------------------------------
# LLM prompt assembly & response parsing
# ---------------------------------------------------------------------------
def build_quiz_prompt(concepts: List[dict], chunks: List[dict], max_questions: int = 10) -> str:
    concept_blob = "\n".join(
        f"- {c['name']}: {c.get('description', '')}  [chunks: {', '.join(c.get('source_chunk_ids', []))}]"
        for c in concepts
    )
    chunk_blob = "\n".join(
        f"[chunk:{c['id']}] ({c.get('start_time', 0.0):.1f}s - {c.get('end_time', 0.0):.1f}s) {c['text']}"
        for c in chunks
    )
    return f"""You are a comprehension-quiz author for an educational video transcript.

Create {max_questions} multiple-choice comprehension questions that are:
- Grounded in the provided concepts and transcript chunks (distractors must be plausible but incorrect).
- Concept-balanced: cover a spread of the extracted concepts rather than one topic.
- Answerable ONLY from the transcript material.

Respond with ONLY a JSON object in exactly this shape:
{{
  "questions": [
    {{
      "question_text": "...",
      "options": ["A", "B", "C", "D"],
      "correct_index": 1,
      "explanation": "Why this answer is correct (grounded in the transcript).",
      "concept": "Concept Name",
      "source_chunk_ids": ["chunk_0"]
    }}
  ]
}}

Extracted concepts:
{concept_blob}

Transcript chunks:
{chunk_blob}
"""


def parse_llm_quiz(text: str) -> Optional[List[ExtractedQuestion]]:
    if not text:
        return None
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(0))
    except Exception:
        return None

    raw_questions = data.get("questions") or []
    if not raw_questions:
        return None

    questions: List[ExtractedQuestion] = []
    for q in raw_questions:
        text_q = str(q.get("question_text", "")).strip()
        options = [str(x) for x in (q.get("options") or [])]
        if not text_q or len(options) < 2:
            continue
        try:
            correct_index = int(q.get("correct_index", 0))
        except (ValueError, TypeError):
            correct_index = 0
        correct_index = max(0, min(correct_index, len(options) - 1))
        questions.append(
            ExtractedQuestion(
                question_text=text_q,
                options=options,
                correct_index=correct_index,
                explanation=str(q.get("explanation", "") or ""),
                concept=str(q.get("concept", "") or "") or None,
                source_chunk_ids=[str(x) for x in (q.get("source_chunk_ids") or [])],
            )
        )
    return questions or None


# ---------------------------------------------------------------------------
# Deterministic heuristic quiz fallback (no LLM required)
# ---------------------------------------------------------------------------
def _distractors_for(concept: dict, concepts: List[dict]) -> List[str]:
    """Pick up to 3 plausible-but-incorrect concept names as distractors."""
    others = [c for c in concepts if c["id"] != concept["id"]]
    names = [c["name"] for c in others]
    return names[:3]


def generate_quiz_heuristic(
    concepts: List[dict], chunks: List[dict], max_questions: int = 10
) -> List[ExtractedQuestion]:
    """Deterministic concept-balanced multiple-choice generation for offline environments."""
    if not concepts:
        return []

    chunk_by_id = {c["id"]: c for c in chunks}
    questions: List[ExtractedQuestion] = []
    for concept in concepts:
        if len(questions) >= max_questions:
            break
        name = str(concept.get("name", "")).strip()
        description = str(concept.get("description", "") or "").strip()
        if not name:
            continue
        chunk_ids = concept.get("source_chunk_ids") or []
        if not chunk_ids and chunks:
            chunk_ids = [chunks[0]["id"]]
        first_chunk = chunk_by_id.get(chunk_ids[0]) if chunk_ids else None
        media_id = concept.get("media_id") or (first_chunk or {}).get("media_id")
        start_time = concept.get("start_time") if concept.get("start_time") is not None else (first_chunk or {}).get("start_time")
        end_time = concept.get("end_time") if concept.get("end_time") is not None else (first_chunk or {}).get("end_time")

        distractors = _distractors_for(concept, concepts)
        if distractors:
            options = [name, *distractors]
            import random
            indices = list(range(len(options)))
            random.Random(f"{name}-{len(questions)}").shuffle(indices)
            shuffled = [options[i] for i in indices]
            correct_index = indices.index(0)
            question_text = f"Which of the following is best described as: {description}" if description else f"Which concept is described by '{name}'?"
            questions.append(
                ExtractedQuestion(
                    question_text=question_text,
                    options=shuffled,
                    correct_index=correct_index,
                    explanation=description or f"The correct answer is {name}.",
                    concept=name,
                    source_chunk_ids=chunk_ids,
                    media_id=media_id,
                    start_time=start_time,
                    end_time=end_time,
                )
            )
        else:
            questions.append(
                ExtractedQuestion(
                    question_text=f"Is '{name}' a key concept covered in this material?",
                    options=["True", "False"],
                    correct_index=0,
                    explanation=f"'{name}' is identified as a key concept in the transcript.",
                    concept=name,
                    source_chunk_ids=chunk_ids,
                    media_id=media_id,
                    start_time=start_time,
                    end_time=end_time,
                )
            )
    return questions


def build_concept_payloads_for_quiz(concepts: List[dict], count: Optional[int] = None) -> List[dict]:
    """Concept-balanced subsampling when the corpus exceeds the question budget."""
    if count is None or len(concepts) <= count:
        return concepts
    step = len(concepts) / count
    sampled = [concepts[int(i * step)] for i in range(count)]
    return sampled
