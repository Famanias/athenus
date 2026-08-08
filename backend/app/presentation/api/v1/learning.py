import io
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.domain.learning.entities import FlashcardCard, FlashcardDeck, QuizContainer, QuizQuestionItem
from app.domain.learning.flashcard_service import FlashcardService
from app.domain.learning.quiz_service import QuizService
from app.infrastructure.exporters.anki_exporter import (
    export_deck_apkg,
    export_deck_csv,
)
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.events.event_bus import event_bus as global_event_bus
from app.domain.analytics.analytics_service import AnalyticsService

router = APIRouter()

# ai_service_bus is the process-wide singleton built in main.py.
# Import it here so both FlashcardService and QuizService can reach the LLM
# provider — without this injection their _generate_with_llm methods return []
# immediately (self.ai_service_bus is None) and always fall back to the
# heuristic engine, regardless of which provider is configured.
from app.main import ai_service_bus  # noqa: E402

graph_service = KnowledgeGraphService()
flashcard_service = FlashcardService(graph_service=graph_service, ai_service_bus=ai_service_bus, event_bus=global_event_bus)
quiz_service = QuizService(graph_service=graph_service, ai_service_bus=ai_service_bus, event_bus=global_event_bus)
# Precomputed analytics subscribe to domain events once at import time.
_analytics = AnalyticsService(event_bus=global_event_bus, graph_service=graph_service, flashcard_service=flashcard_service)


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


# ---------------------------------------------------------------------------
# Adaptive Comprehension Quiz Studio
# ---------------------------------------------------------------------------
class QuizItemResponse(BaseModel):
    id: str
    quiz_id: str
    concept_id: Optional[str] = None
    concept_name: Optional[str] = None
    question_text: str
    options: List[str] = []
    correct_index: int = 0
    explanation: str = ""
    media_id: Optional[str] = None
    source_chunk_ids: List[str] = []
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class QuizContainerResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    version: int
    status: str
    concept_ids: List[str] = []
    question_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class QuizAttemptResponse(BaseModel):
    id: str
    quiz_id: str
    workspace_id: str
    version: int
    score: float
    total_questions: int
    correct_count: int
    answers: Optional[dict] = None
    time_taken: float = 0.0
    created_at: Optional[str] = None


class GradeAttemptRequest(BaseModel):
    workspace_id: str
    answers: dict
    time_taken: float = 0.0


class ArtifactJobStatusResponse(BaseModel):
    artifact_type: str
    target_key: str
    status: str
    stage: Optional[str] = None
    progress: int = 0
    message: Optional[str] = None
    error_message: Optional[str] = None
    updated_at: Optional[str] = None


def _artifact_job_to_response(job) -> Optional[ArtifactJobStatusResponse]:
    if not job:
        return None
    return ArtifactJobStatusResponse(
        artifact_type=job.artifact_type,
        target_key=job.target_key,
        status=job.status,
        stage=getattr(job, "stage", None),
        progress=job.progress or 0,
        message=job.message,
        error_message=job.error_message,
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
    )


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


@router.get("/learning/decks/{workspace_id}/status", response_model=Optional[ArtifactJobStatusResponse])
def get_flashcard_artifact_status(workspace_id: str):
    job = graph_service.get_artifact_job(workspace_id, "flashcards", target_key=workspace_id)
    if not job:
        return None
    return _artifact_job_to_response(job)


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
# Adaptive Comprehension Quiz Studio endpoints
# ---------------------------------------------------------------------------
def _quiz_to_response(quiz: QuizContainer) -> QuizContainerResponse:
    return QuizContainerResponse(
        id=quiz.id,
        workspace_id=quiz.workspace_id,
        title=quiz.title,
        version=quiz.version,
        status=quiz.status,
        concept_ids=quiz.concept_ids,
        question_count=quiz.question_count,
        created_at=quiz.created_at.isoformat() if quiz.created_at else None,
        updated_at=quiz.updated_at.isoformat() if quiz.updated_at else None,
    )


def _question_to_response(q: QuizQuestionItem) -> QuizItemResponse:
    return QuizItemResponse(
        id=q.id,
        quiz_id=q.quiz_id,
        concept_id=q.concept_id,
        concept_name=q.concept_name,
        question_text=q.question_text,
        options=q.options,
        correct_index=q.correct_index,
        explanation=q.explanation,
        media_id=q.media_id,
        source_chunk_ids=q.source_chunk_ids,
        start_time=q.start_time,
        end_time=q.end_time,
    )


@router.post("/learning/quizzes/{workspace_id}/generate", response_model=QuizContainerResponse)
async def generate_quiz(
    workspace_id: str,
    max_questions: int = 10,
    force_new_version: bool = False,
):
    try:
        quiz = await quiz_service.generate_quiz(
            workspace_id=workspace_id,
            max_questions=max_questions,
            force_new_version=force_new_version,
        )
        return _quiz_to_response(quiz)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/learning/quizzes/workspace/{workspace_id}", response_model=List[QuizContainerResponse])
def list_quizzes(workspace_id: str):
    quizzes = quiz_service.list_quizzes(workspace_id)
    return [_quiz_to_response(q) for q in quizzes]


@router.get("/learning/quizzes/workspace/{workspace_id}/status", response_model=Optional[ArtifactJobStatusResponse])
def get_quiz_artifact_status(workspace_id: str):
    job = graph_service.get_artifact_job(workspace_id, "quiz", target_key=workspace_id)
    if not job:
        return None
    return _artifact_job_to_response(job)


@router.get("/learning/quizzes/workspace/{workspace_id}/version/{version}", response_model=QuizContainerResponse)
def get_quiz_version(workspace_id: str, version: int):
    quiz = quiz_service.get_workspace_quiz(workspace_id, version=version)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz version not found")
    return _quiz_to_response(quiz)


@router.get("/learning/quizzes/container/{quiz_id}/questions", response_model=List[QuizItemResponse])
def get_quiz_questions(quiz_id: str):
    questions = quiz_service.get_quiz_questions(quiz_id)
    return [_question_to_response(q) for q in questions]


@router.post("/learning/quizzes/{quiz_id}/grade", response_model=QuizAttemptResponse)
def grade_quiz(quiz_id: str, request: GradeAttemptRequest):
    try:
        attempt = quiz_service.grade_attempt(
            quiz_id=quiz_id,
            workspace_id=request.workspace_id,
            answers=request.answers,
            time_taken=request.time_taken,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return QuizAttemptResponse(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        workspace_id=attempt.workspace_id,
        version=attempt.version,
        score=attempt.score,
        total_questions=attempt.total_questions,
        correct_count=attempt.correct_count,
        answers=attempt.answers,
        time_taken=attempt.time_taken,
        created_at=attempt.created_at.isoformat() if attempt.created_at else None,
    )


@router.get("/learning/quizzes/workspace/{workspace_id}/attempts", response_model=List[QuizAttemptResponse])
def list_quiz_attempts(workspace_id: str, limit: int = 20):
    attempts = quiz_service.get_attempts(workspace_id, limit=limit)
    return [
        QuizAttemptResponse(
            id=a.id,
            quiz_id=a.quiz_id,
            workspace_id=a.workspace_id,
            version=a.version,
            score=a.score,
            total_questions=a.total_questions,
            correct_count=a.correct_count,
            answers=a.answers,
            time_taken=a.time_taken,
            created_at=a.created_at.isoformat() if a.created_at else None,
        )
        for a in attempts
    ]


# ---------------------------------------------------------------------------
# Workspace Learning Settings & Auto-Evolution Configuration
# ---------------------------------------------------------------------------
class WorkspaceLearningSettingsDTO(BaseModel):
    auto_evolve_flashcards: bool = False
    flashcard_target_budget_per_media: int = 20
    auto_evolve_quizzes: bool = False
    quiz_target_budget_per_media: int = 15


@router.get("/learning/workspaces/{workspace_id}/settings", response_model=WorkspaceLearningSettingsDTO)
def get_workspace_learning_settings(workspace_id: str):
    from app.infrastructure.db.models import WorkspaceTable
    from app.infrastructure.db.session import engine
    try:
        from sqlmodel import Session
    except ImportError:
        from sqlalchemy.orm import Session

    if not engine or not Session:
        return WorkspaceLearningSettingsDTO()

    try:
        with Session(engine) as session:
            ws = session.get(WorkspaceTable, workspace_id)
            if ws and ws.settings_json:
                import json
                data = json.loads(ws.settings_json)
                return WorkspaceLearningSettingsDTO(
                    auto_evolve_flashcards=data.get("auto_evolve_flashcards", False),
                    flashcard_target_budget_per_media=data.get("flashcard_target_budget_per_media", 20),
                    auto_evolve_quizzes=data.get("auto_evolve_quizzes", False),
                    quiz_target_budget_per_media=data.get("quiz_target_budget_per_media", 15),
                )
    except Exception:
        pass
    return WorkspaceLearningSettingsDTO()


@router.patch("/learning/workspaces/{workspace_id}/settings", response_model=WorkspaceLearningSettingsDTO)
def patch_workspace_learning_settings(workspace_id: str, payload: WorkspaceLearningSettingsDTO):
    from app.infrastructure.db.models import WorkspaceTable
    from app.infrastructure.db.session import engine
    try:
        from sqlmodel import Session
    except ImportError:
        from sqlalchemy.orm import Session

    if not engine or not Session:
        return payload

    try:
        with Session(engine) as session:
            ws = session.get(WorkspaceTable, workspace_id)
            if ws:
                import json
                current_settings = json.loads(ws.settings_json) if ws.settings_json else {}
                current_settings.update({
                    "auto_evolve_flashcards": payload.auto_evolve_flashcards,
                    "flashcard_target_budget_per_media": payload.flashcard_target_budget_per_media,
                    "auto_evolve_quizzes": payload.auto_evolve_quizzes,
                    "quiz_target_budget_per_media": payload.quiz_target_budget_per_media,
                })
                ws.settings_json = json.dumps(current_settings)
                session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return payload


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
