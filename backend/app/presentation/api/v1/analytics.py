from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.analytics.analytics_service import AnalyticsService

router = APIRouter()

analytics_service = AnalyticsService()


class WorkspaceAnalyticsResponse(BaseModel):
    workspace_id: str
    total_media: int = 0
    total_concepts: int = 0
    total_flashcards: int = 0
    total_quiz_attempts: int = 0
    total_reviews: int = 0
    avg_quiz_score: float = 0.0
    total_study_seconds: float = 0.0
    review_streak_days: int = 0
    last_activity_at: Optional[str] = None


class ConceptMasteryResponse(BaseModel):
    concept_id: str
    concept_name: str
    mastery_level: float
    review_count: int
    quiz_correct: int
    quiz_attempts: int
    last_reviewed_at: Optional[str] = None


class ActivityResponse(BaseModel):
    id: str
    activity_type: str
    duration_seconds: float
    created_at: Optional[str] = None


class RevisionRecommendation(BaseModel):
    type: str  # flashcard | concept
    card_id: Optional[str] = None
    title: str
    concept_id: Optional[str] = None
    concept_name: Optional[str] = None
    due_in_days: int = 0
    mastery_level: float = 0.0
    priority: str = "medium"


class AnalyticsSummaryResponse(BaseModel):
    workspace: WorkspaceAnalyticsResponse
    concept_mastery: List[ConceptMasteryResponse]
    recent_activity: List[ActivityResponse]
    revision_recommendations: List[RevisionRecommendation]


@router.get("/analytics/workspace/{workspace_id}", response_model=WorkspaceAnalyticsResponse)
def get_workspace_analytics(workspace_id: str):
    data = analytics_service.get_workspace_analytics(workspace_id) or {}
    return WorkspaceAnalyticsResponse(**data)


@router.get("/analytics/workspace/{workspace_id}/concepts", response_model=List[ConceptMasteryResponse])
def get_concept_mastery(workspace_id: str):
    records = analytics_service.get_concept_mastery(workspace_id)
    return [ConceptMasteryResponse(**r) for r in records]


@router.get("/analytics/workspace/{workspace_id}/activity", response_model=List[ActivityResponse])
def get_recent_activity(workspace_id: str, limit: int = 10):
    records = analytics_service.get_recent_activity(workspace_id, limit=limit)
    return [ActivityResponse(**r) for r in records]


@router.get("/analytics/workspace/{workspace_id}/revisions", response_model=List[RevisionRecommendation])
def get_revision_recommendations(workspace_id: str, limit: int = 8):
    records = analytics_service.recommend_revisions(workspace_id, limit=limit)
    return [RevisionRecommendation(**r) for r in records]


@router.get("/analytics/workspace/{workspace_id}/summary", response_model=AnalyticsSummaryResponse)
def get_analytics_summary(workspace_id: str):
    workspace = analytics_service.get_workspace_analytics(workspace_id) or {}
    concepts = analytics_service.get_concept_mastery(workspace_id)
    activity = analytics_service.get_recent_activity(workspace_id, limit=10)
    revisions = analytics_service.recommend_revisions(workspace_id, limit=8)
    return AnalyticsSummaryResponse(
        workspace=WorkspaceAnalyticsResponse(**workspace),
        concept_mastery=[ConceptMasteryResponse(**r) for r in concepts],
        recent_activity=[ActivityResponse(**r) for r in activity],
        revision_recommendations=[RevisionRecommendation(**r) for r in revisions],
    )
