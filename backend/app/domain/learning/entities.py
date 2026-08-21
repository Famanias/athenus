from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


# ---------------------------------------------------------------------------
# Legacy dataclasses (kept for backward compatibility with prior workers)
# ---------------------------------------------------------------------------
@dataclass
class QuizQuestion:
    id: str
    question_text: str
    options: List[str]
    correct_option_index: int
    explanation: str
    concept_id: Optional[str] = None
    source_chunk_id: Optional[str] = None


@dataclass
class Quiz:
    id: str
    workspace_id: str
    title: str
    questions: List[QuizQuestion] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Flashcard:
    id: str
    workspace_id: str
    front_prompt: str
    back_answer: str
    concept_id: Optional[str] = None
    ease_factor: float = 2.5  # SM-2 / FSRS algorithm factor
    interval_days: int = 1
    repetitions: int = 0
    next_review_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Flashcard studio entities (concept-grounded, provenance-aware)
# ---------------------------------------------------------------------------
@dataclass
class FlashcardCard:
    id: str
    deck_id: str
    workspace_id: str
    card_type: str  # basic | cloze | definition | true_false
    front: str
    back: Optional[str] = None
    cloze_text: Optional[str] = None
    options: Optional[List[str]] = None
    concept_id: Optional[str] = None
    concept_name: Optional[str] = None
    # Grounding & provenance contract
    media_id: Optional[str] = None
    source_chunk_ids: List[str] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    # SM-2 scheduling
    ease_factor: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    next_review_at: Optional[datetime] = None


@dataclass
class FlashcardDeck:
    id: str
    workspace_id: str
    name: str
    version: int = 1
    status: str = "ready"  # pending | generating | ready | failed
    media_ids: List[str] = field(default_factory=list)
    concept_ids: List[str] = field(default_factory=list)
    card_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FlashcardReview:
    id: str
    flashcard_id: str
    workspace_id: str
    rating: int  # SM-2 quality 1-4
    ease_factor: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    reviewed_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Quiz studio entities
# ---------------------------------------------------------------------------
@dataclass
class QuizQuestionItem:
    id: str
    quiz_id: str
    workspace_id: str
    concept_id: Optional[str] = None
    concept_name: Optional[str] = None
    question_text: str = ""
    options: List[str] = field(default_factory=list)
    correct_index: int = 0
    explanation: str = ""
    # Grounding & provenance contract
    media_id: Optional[str] = None
    source_chunk_ids: List[str] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None


@dataclass
class QuizContainer:
    id: str
    workspace_id: str
    title: str
    version: int = 1
    status: str = "ready"
    concept_ids: List[str] = field(default_factory=list)
    question_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QuizAttempt:
    id: str
    quiz_id: str
    workspace_id: str
    version: int = 1
    score: float = 0.0
    total_questions: int = 0
    correct_count: int = 0
    answers: Optional[dict] = None
    time_taken: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Note studio entities (concept-grounded, timestamp/page provenance-aware)
# ---------------------------------------------------------------------------
@dataclass
class NoteFolder:
    id: str
    workspace_id: str
    name: str
    note_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class NoteSection:
    id: str
    note_id: str
    workspace_id: str
    heading: str
    body: str
    key_takeaways: List[str] = field(default_factory=list)
    # Grounding & provenance contract
    media_id: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    source_chunk_ids: List[str] = field(default_factory=list)
    order_index: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Note:
    id: str
    workspace_id: str
    title: str
    folder_id: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    media_id: Optional[str] = None
    version: int = 1
    status: str = "ready"  # pending | generating | ready | failed
    action_items: List[str] = field(default_factory=list)
    sections: List[NoteSection] = field(default_factory=list)
    generation_method: str = "llm"  # llm | heuristic | manual
    fallback_reason: Optional[str] = None
    provider_id: Optional[str] = None
    model_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
