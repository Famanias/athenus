from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class QuizQuestionResponse(BaseModel):
    id: str
    question_text: str
    options: List[str]
    correct_option_index: int
    explanation: str

class QuizResponse(BaseModel):
    id: str
    title: str
    questions: List[QuizQuestionResponse]

class FlashcardResponse(BaseModel):
    id: str
    front_prompt: str
    back_answer: str
    ease_factor: float

@router.get("/learning/quizzes/{media_id}", response_model=QuizResponse)
def get_quiz(media_id: str):
    return QuizResponse(
        id=f"quiz_{media_id}",
        title=f"Comprehension Quiz for {media_id}",
        questions=[
            QuizQuestionResponse(
                id="q1",
                question_text="What is the core principle of Local-First AI architectures?",
                options=["Cloud dependency", "Data privacy and offline execution", "High latency", "Centralized hosting"],
                correct_option_index=1,
                explanation="Local-first architectures prioritize running models and databases locally to preserve privacy and function offline."
            )
        ]
    )

@router.get("/learning/flashcards/{media_id}", response_model=List[FlashcardResponse])
def get_flashcards(media_id: str):
    return [
        FlashcardResponse(
            id=f"card_{media_id}_1",
            front_prompt="What distance metric is used in Embedded Qdrant vector retrieval?",
            back_answer="Cosine Distance metric over 384-dimensional BGE embeddings.",
            ease_factor=2.5
        )
    ]
