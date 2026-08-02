from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

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
