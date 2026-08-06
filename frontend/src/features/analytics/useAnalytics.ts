import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '@/services/apiClient';
import { useAppStore } from '@/store/useAppStore';

export interface WorkspaceAnalyticsDTO {
  workspace_id: string;
  total_media: number;
  total_concepts: number;
  total_flashcards: number;
  total_quiz_attempts: number;
  total_reviews: number;
  avg_quiz_score: number;
  total_study_seconds: number;
  review_streak_days: number;
  last_activity_at: string | null;
}

export interface ConceptMasteryDTO {
  concept_id: string;
  concept_name: string;
  mastery_level: number;
  review_count: number;
  quiz_correct: number;
  quiz_attempts: number;
  last_reviewed_at: string | null;
}

export interface ActivityDTO {
  id: string;
  activity_type: string;
  duration_seconds: number;
  created_at: string | null;
}

export interface RevisionRecommendationDTO {
  type: 'flashcard' | 'concept';
  card_id: string | null;
  title: string;
  concept_id: string | null;
  concept_name: string | null;
  due_in_days: number;
  mastery_level: number;
  priority: 'high' | 'medium' | 'low';
}

export interface AnalyticsSummaryDTO {
  workspace: WorkspaceAnalyticsDTO;
  concept_mastery: ConceptMasteryDTO[];
  recent_activity: ActivityDTO[];
  revision_recommendations: RevisionRecommendationDTO[];
}

const EMPTY_WORKSPACE: WorkspaceAnalyticsDTO = {
  workspace_id: '',
  total_media: 0,
  total_concepts: 0,
  total_flashcards: 0,
  total_quiz_attempts: 0,
  total_reviews: 0,
  avg_quiz_score: 0,
  total_study_seconds: 0,
  review_streak_days: 0,
  last_activity_at: null,
};

export function useAnalytics() {
  const activeWorkspaceId = useAppStore((state) => state.activeWorkspaceId);
  const setActiveView = useAppStore((state) => state.setActiveView);

  const [summary, setSummary] = useState<AnalyticsSummaryDTO | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef(activeWorkspaceId);
  wsRef.current = activeWorkspaceId;

  const fetchSummary = useCallback(async () => {
    const ws = wsRef.current;
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient<AnalyticsSummaryDTO>(
        `/api/v1/analytics/workspace/${encodeURIComponent(ws)}/summary`
      );
      setSummary(data);
    } catch (_err) {
      setSummary(null);
      setError('Failed to load workspace analytics.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary, activeWorkspaceId]);

  const jumpToRevision = useCallback((r: RevisionRecommendationDTO) => {
    if (r.type === 'flashcard') {
      setActiveView('view-flashcards');
    } else if (r.type === 'concept') {
      setActiveView('view-graph');
    }
  }, [setActiveView]);

  return {
    summary,
    workspace: summary?.workspace || EMPTY_WORKSPACE,
    conceptMastery: summary?.concept_mastery || [],
    recentActivity: summary?.recent_activity || [],
    recommendations: summary?.revision_recommendations || [],
    loading,
    error,
    fetchSummary,
    jumpToRevision,
    setActiveView,
    activeWorkspaceId,
  };
}
