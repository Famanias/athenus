import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.domain.knowledge.entities import RelationType

STOPWORDS = set(
    """
    a an and are as at be by for from has have in is it its of on or that the
    this to was were will with about into over after between during through
    before under again further then once here there when where why how all any
    both each few more most other some such no nor not only own same so than
    too very can did do does done down just what which who whom
    """.split()
)


@dataclass
class ExtractedConcept:
    name: str
    description: str
    source_chunk_ids: List[str] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0


@dataclass
class ExtractedRelation:
    source: str
    target: str
    relation_type: str = "related_to"
    weight: float = 1.0


# ---------------------------------------------------------------------------
# Heuristic term-frequency concept extractor (deterministic fallback)
# ---------------------------------------------------------------------------
def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z\-']{1,}", text.lower())


def extract_concepts_heuristic(
    chunks: List[Dict[str, object]], max_concepts: int = 8
) -> Tuple[List[ExtractedConcept], List[ExtractedRelation]]:
    """Deterministic concept extraction from transcript chunk dicts.

    Each chunk dict must expose: id, text, start_time, end_time.
    Uses word/bigram frequency with stopword filtering; co-occurring concepts
    within the same chunk produce `related_to` relations.
    """
    if not chunks:
        return [], []

    term_freq: Counter = Counter()
    bigram_freq: Counter = Counter()
    chunk_of_term: Dict[str, str] = {}
    chunk_text_by_id: Dict[str, Dict[str, object]] = {c["id"]: c for c in chunks}

    for chunk in chunks:
        tokens = _tokenize(str(chunk.get("text", "")))
        tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
        for token in tokens:
            term_freq[token] += 1
            chunk_of_term[token] = chunk["id"]
        for i in range(len(tokens) - 1):
            bigram = f"{tokens[i]} {tokens[i + 1]}"
            bigram_freq[bigram] += 1
            chunk_of_term[bigram] = chunk["id"]

    candidates = list(term_freq.keys()) + list(bigram_freq.keys())
    candidate_scores = {
        term: bigram_freq.get(term, 0) * 2 + term_freq.get(term, 0)
        for term in candidates
    }
    ranked = sorted(candidate_scores, key=lambda t: candidate_scores[t], reverse=True)

    concepts: List[ExtractedConcept] = []
    for term in ranked:
        if len(concepts) >= max_concepts:
            break
        if term in [c.name.lower() for c in concepts]:
            continue
        chunk_id = chunk_of_term.get(term)
        chunk = chunk_text_by_id.get(chunk_id, {})
        concepts.append(
            ExtractedConcept(
                name=term.title(),
                description=f"Key concept extracted from lecture content.",
                source_chunk_ids=[chunk_id] if chunk_id else [],
                start_time=float(chunk.get("start_time", 0.0) or 0.0),
                end_time=float(chunk.get("end_time", 0.0) or 0.0),
            )
        )

    # Co-occurrence relations within the same chunk
    concepts_by_name = {c.name: c for c in concepts}
    co_occurrences: Dict[Tuple[str, str], int] = defaultdict(int)
    for chunk in chunks:
        chunk_tokens = set(
            t for t in _tokenize(str(chunk.get("text", ""))) if t not in STOPWORDS and len(t) > 2
        )
        present = [c.name for c in concepts if c.name.lower() in chunk_tokens]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                key = (present[i], present[j])
                co_occurrences[key] += 1

    relations: List[ExtractedRelation] = []
    for (a, b), count in co_occurrences.items():
        if count >= 2:
            relations.append(ExtractedRelation(source=a, target=b, relation_type="related_to", weight=min(float(count), 3.0)))

    if not relations and len(concepts) >= 2:
        relations.append(
            ExtractedRelation(
                source=concepts[0].name,
                target=concepts[1].name,
                relation_type="related_to",
                weight=1.0,
            )
        )

    return concepts, relations


# ---------------------------------------------------------------------------
# LLM extraction prompt assembly & response parsing
# ---------------------------------------------------------------------------
def build_extraction_prompt(chunks: List[Dict[str, object]]) -> str:
    chunk_blob = "\n".join(
        f"[chunk:{c['id']}] ({c['start_time']:.1f}s - {c['end_time']:.1f}s) {c['text']}"
        for c in chunks
    )
    return f"""You are a knowledge-graph extraction engine for an educational video transcript.

Extract the domain concepts (entities, terms, algorithms, definitions) and their directional relationships from the transcript chunks below.

Rules:
- Every concept MUST reference at least one source chunk id exactly as given.
- Only use relation types: prerequisite_for, related_to, expands_on, contradicts, example_of.
- Keep concept names concise (2-5 words).

Respond with ONLY a JSON object in exactly this shape:
{{
  "concepts": [
    {{"name": "Concept Name", "description": "Short definition grounded in the transcript.", "source_chunk_ids": ["chunk_0"]}}
  ],
  "relations": [
    {{"source": "Concept Name", "target": "Other Concept", "relation_type": "prerequisite_for"}}
  ]
}}

Transcript chunks:
{chunk_blob}
"""


def parse_llm_extraction(text: str) -> Optional[Tuple[List[ExtractedConcept], List[ExtractedRelation]]]:
    if not text:
        return None
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(0))
    except Exception:
        return None

    raw_concepts = data.get("concepts") or []
    raw_relations = data.get("relations") or []
    if not raw_concepts:
        return None

    valid_types = {r.value for r in RelationType}
    concepts: List[ExtractedConcept] = []
    for c in raw_concepts:
        name = str(c.get("name", "")).strip()
        if not name:
            continue
        concepts.append(
            ExtractedConcept(
                name=name,
                description=str(c.get("description", "") or ""),
                source_chunk_ids=[str(x) for x in (c.get("source_chunk_ids") or [])],
            )
        )
    if not concepts:
        return None

    relations: List[ExtractedRelation] = []
    for r in raw_relations:
        source = str(r.get("source", "")).strip()
        target = str(r.get("target", "")).strip()
        rel_type = str(r.get("relation_type", "related_to")).strip()
        if not source or not target:
            continue
        if rel_type not in valid_types:
            rel_type = "related_to"
        relations.append(
            ExtractedRelation(source=source, target=target, relation_type=rel_type)
        )
    return concepts, relations
