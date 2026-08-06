import io
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.domain.learning.entities import FlashcardCard, FlashcardDeck
from app.domain.learning.flashcard_service import FlashcardService
from app.infrastructure.exporters.anki_exporter import (
    export_deck_apkg,
    export_deck_csv,
)
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService

router = APIRouter()

flashcard_service = FlashcardService(graph_service=KnowledgeGraphService())


class CardResponse(BaseModel):
    id: str
    deck_id: str
    card_type: str
    front: str
    back: Optional[str] = None
    cloze_text: Optional[str] = None
    options: Optional[List[str]] = None
    concept_id: Optional[str] = None
    concept_name: Optional[str] = None
    media_id: Optional[str] = None
    source_chunk_ids: List[str] = []
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    ease_factor: float = 2.5
    interval_days: int = 0
    repetitions: int = 0


class DeckResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    version: int
    status: str
    media_ids: List[str] = []
    concept_ids: List[str] = []
    card_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ReviewRequest(BaseModel):
    flashcard_id: str
    workspace_id: str
    rating: int  # SM-2 quality 1-4


class ReviewResponse(BaseModel):
    id: str
    flashcard_id: str
    rating: int
    ease_factor: float
    interval_days: int
    repetitions: int


def _deck_to_response(deck: FlashcardDeck) -> DeckResponse:
    return DeckResponse(
        id=deck.id,
        workspace_id=deck.workspace_id,
        name=deck.name,
        version=deck.version,
        status=deck.status,
        media_ids=deck.media_ids,
        concept_ids=deck.concept_ids,
        card_count=deck.card_count,
        created_at=deck.created_at.isoformat() if deck.created_at else None,
        updated_at=deck.updated_at.isoformat() if deck.updated_at else None,
    )


def _card_to_response(card: FlashcardCard) -> CardResponse:
    return CardResponse(
        id=card.id,
        deck_id=card.deck_id,
        card_type=card.card_type,
        front=card.front,
        back=card.back,
        cloze_text=card.cloze_text,
        options=card.options,
        concept_id=card.concept_id,
        concept_name=card.concept_name,
        media_id=card.media_id,
        source_chunk_ids=card.source_chunk_ids,
        start_time=card.start_time,
        end_time=card.end_time,
        ease_factor=card.ease_factor,
        interval_days=card.interval_days,
        repetitions=card.repetitions,
    )


@router.post("/learning/decks/{workspace_id}", response_model=DeckResponse)
async def create_deck(
    workspace_id: str,
    force_new_version: bool = False,
    max_cards: int = 40,
):
    try:
        deck = await flashcard_service.generate_deck(
            workspace_id=workspace_id,
            max_cards=max_cards,
            force_new_version=force_new_version,
        )
        return _deck_to_response(deck)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/learning/decks/{workspace_id}", response_model=List[DeckResponse])
def list_decks(workspace_id: str):
    decks = flashcard_service.list_decks(workspace_id)
    return [_deck_to_response(d) for d in decks]


@router.get("/learning/decks/{workspace_id}/version/{version}", response_model=DeckResponse)
def get_deck_version(workspace_id: str, version: int):
    deck = flashcard_service.get_workspace_deck(workspace_id, version=version)
    if not deck:
        raise HTTPException(status_code=404, detail="Deck version not found")
    return _deck_to_response(deck)


@router.get("/learning/decks/{deck_id}/cards", response_model=List[CardResponse])
def get_deck_cards(deck_id: str):
    cards = flashcard_service.get_deck_cards(deck_id)
    return [_card_to_response(c) for c in cards]


@router.post("/learning/reviews", response_model=ReviewResponse)
def record_review(request: ReviewRequest):
    review = flashcard_service.record_review(
        flashcard_id=request.flashcard_id,
        workspace_id=request.workspace_id,
        rating=request.rating,
    )
    return ReviewResponse(
        id=review.id,
        flashcard_id=review.flashcard_id,
        rating=review.rating,
        ease_factor=review.ease_factor,
        interval_days=review.interval_days,
        repetitions=review.repetitions,
    )


@router.get("/learning/decks/{deck_id}/due", response_model=List[CardResponse])
def get_due_cards(deck_id: str, workspace_id: str, limit: int = 30):
    cards = flashcard_service.due_cards(workspace_id, limit=limit)
    return [_card_to_response(c) for c in cards]


@router.get("/learning/decks/{deck_id}/export")
def export_deck(deck_id: str, format: str = "csv"):
    cards = flashcard_service.get_deck_cards(deck_id)
    if not cards:
        raise HTTPException(status_code=404, detail="No cards found in deck")
    if format == "csv":
        content = export_deck_csv(cards)
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{deck_id}.csv"'},
        )
    if format == "apkg":
        buffer = io.BytesIO()
        export_deck_apkg(cards, buffer)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/apkg",
            headers={"Content-Disposition": f'attachment; filename="{deck_id}.apkg"'},
        )
    raise HTTPException(status_code=400, detail="format must be csv or apkg")


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for backward compatibility with existing tests/UIs)
# ---------------------------------------------------------------------------
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


class LegacyFlashcardResponse(BaseModel):
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


@router.get("/learning/flashcards/{media_id}", response_model=List[LegacyFlashcardResponse])
def get_flashcards(media_id: str):
    return [
        LegacyFlashcardResponse(
            id=f"card_{media_id}_1",
            front_prompt="What distance metric is used in Embedded Qdrant vector retrieval?",
            back_answer="Cosine Distance metric over 384-dimensional BGE embeddings.",
            ease_factor=2.5
        )
    ]
