import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '@/services/apiClient';
import { useAppStore } from '@/store/useAppStore';

export interface QuizOption {
  id: string;
  text: string;
  isCorrect?: boolean;
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: QuizOption[];
  explanation: string;
  conceptName: string;
  startTime?: number;
  mediaId?: string;
}

export interface QuizContainerDTO {
  id: string;
  workspace_id: string;
  title: string;
  version: number;
  status: string;
  question_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface QuizItemDTO {
  id: string;
  container_id: string;
  question_text: string;
  options: string[];
  correct_index: number;
  explanation: string;
  concept_id: string | null;
  concept_name: string;
  media_id: string | null;
  start_time: number | null;
  end_time: number | null;
}

export interface QuizAttemptDTO {
  id: string;
  quiz_id: string;
  workspace_id: string;
  version: number;
  score: number;
  total_questions: number;
  correct_count: number;
  answers: Record<
    string,
    { user_answer: number | null; correct_index: number; is_correct: boolean; concept_id: string | null }
  > | null;
  time_taken: number;
  created_at: string | null;
}

export interface ArtifactJobStatusDTO {
  artifact_type: string;
  target_key: string;
  status: string;
  stage: string | null;
  progress: number;
  message: string | null;
  error_message: string | null;
  updated_at: string | null;
}

export interface WorkspaceLearningSettingsDTO {
  auto_evolve_flashcards: boolean;
  flashcard_target_budget_per_media: number;
  auto_evolve_quizzes: boolean;
  quiz_target_budget_per_media: number;
}

interface UseQuizOptions {
  autoGenerate?: boolean;
}

export function useQuiz(options: UseQuizOptions = {}) {
  const { autoGenerate = false } = options;
  const activeWorkspaceId = useAppStore((state) => state.activeWorkspaceId);
  const setActiveView = useAppStore((state) => state.setActiveView);

  const [quizzes, setQuizzes] = useState<QuizContainerDTO[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [activeQuiz, setActiveQuiz] = useState<QuizContainerDTO | null>(null);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [artifact, setArtifact] = useState<ArtifactJobStatusDTO | null>(null);
  const [settings, setSettings] = useState<WorkspaceLearningSettingsDTO>({
    auto_evolve_flashcards: true,
    flashcard_target_budget_per_media: 20,
    auto_evolve_quizzes: true,
    quiz_target_budget_per_media: 15,
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [selectedOptId, setSelectedOptId] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [showExplanation, setShowExplanation] = useState<boolean>(false);
  const [attempt, setAttempt] = useState<QuizAttemptDTO | null>(null);
  const [elapsed, setElapsed] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const wsRef = useRef(activeWorkspaceId);
  wsRef.current = activeWorkspaceId;

  const fetchSettings = useCallback(async () => {
    const ws = wsRef.current;
    if (!ws) return;
    try {
      const data = await apiClient<WorkspaceLearningSettingsDTO>(
        `/api/v1/learning/workspaces/${encodeURIComponent(ws)}/settings`
      );
      if (data) setSettings(data);
    } catch (_err) {
      // fallback
    }
  }, []);

  const updateSettings = useCallback(async (partial: Partial<WorkspaceLearningSettingsDTO>) => {
    const ws = wsRef.current;
    if (!ws) return;
    const next = { ...settings, ...partial };
    setSettings(next);
    try {
      await apiClient<WorkspaceLearningSettingsDTO>(
        `/api/v1/learning/workspaces/${encodeURIComponent(ws)}/settings`,
        {
          method: 'PATCH',
          body: JSON.stringify(next),
        }
      );
    } catch (_err) {
      // revert on failure
    }
  }, [settings]);

  const refreshQuizzes = useCallback(async () => {
    const ws = wsRef.current;
    try {
      const data = await apiClient<QuizContainerDTO[]>(
        `/api/v1/learning/quizzes/workspace/${encodeURIComponent(ws)}`
      );
      setQuizzes(data || []);
      return data || [];
    } catch (_err) {
      setQuizzes([]);
      return [];
    }
  }, []);

  const refreshArtifactStatus = useCallback(async () => {
    const ws = wsRef.current;
    if (!ws) {
      setArtifact(null);
      return;
    }
    try {
      const data = await apiClient<ArtifactJobStatusDTO | null>(
        `/api/v1/learning/quizzes/workspace/${encodeURIComponent(ws)}/status`
      );
      setArtifact(data || null);
    } catch (_err) {
      setArtifact(null);
    }
  }, []);

  const loadQuiz = useCallback(async (quiz: QuizContainerDTO) => {
    setActiveQuiz(quiz);
    setSelectedVersion(quiz.version);
    setLoading(true);
    setError(null);
    setAttempt(null);
    setCurrentIndex(0);
    setSelectedOptId(null);
    setShowExplanation(false);
    setElapsed(0);
    setAnswers({});
    try {
      const items = await apiClient<QuizItemDTO[]>(
        `/api/v1/learning/quizzes/container/${encodeURIComponent(quiz.id)}/questions`
      );
      const mapped: QuizQuestion[] = (items || []).map((q) => ({
        id: q.id,
        question: q.question_text,
        options: q.options.map((text, idx) => ({
          id: `${q.id}_opt_${idx}`,
          text,
          isCorrect: idx === q.correct_index,
        })),
        explanation: q.explanation,
        conceptName: q.concept_name,
        startTime: q.start_time,
        mediaId: q.media_id,
      }));
      setQuestions(mapped);
    } catch (_err) {
      setQuestions([]);
      setError('Failed to load quiz questions.');
    } finally {
      setLoading(false);
    }
  }, []);

  const selectVersion = useCallback(async (version: number) => {
    const ws = wsRef.current;
    const match = quizzes.find((q) => q.version === version);
    if (match) {
      await loadQuiz(match);
    } else {
      try {
        const fresh = await refreshQuizzes();
        const found = fresh.find((q) => q.version === version);
        if (found) await loadQuiz(found);
      } catch (_err) {}
    }
  }, [quizzes, loadQuiz, refreshQuizzes]);

  const generateQuiz = useCallback(async () => {
    const ws = wsRef.current;
    if (!ws) return null;
    setGenerating(true);
    setError(null);
    setToastMessage(null);
    try {
      const quiz = await apiClient<QuizContainerDTO>(
        `/api/v1/learning/quizzes/${encodeURIComponent(ws)}/generate?force_new_version=true`,
        { method: 'POST' }
      );
      await refreshQuizzes();
      await refreshArtifactStatus();
      if (quiz) {
        await loadQuiz(quiz);
        setToastMessage(`✅ Quiz regenerated (Version ${quiz.version})`);
        setTimeout(() => setToastMessage(null), 4000);
      }
      return quiz;
    } catch (_err) {
      setError('Failed to generate quiz. Ensure concepts have been extracted.');
      return null;
    } finally {
      setGenerating(false);
    }
  }, [refreshQuizzes, refreshArtifactStatus, loadQuiz]);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      if (!wsRef.current) return;
      setLoading(true);
      fetchSettings();
      refreshArtifactStatus();
      try {
        let existing = await refreshQuizzes();
        if (!existing || existing.length === 0) {
          if (!autoGenerate) {
            setLoading(false);
            return;
          }
          const created = await apiClient<QuizContainerDTO>(
            `/api/v1/learning/quizzes/${encodeURIComponent(wsRef.current)}/generate`,
            { method: 'POST' }
          ).catch(() => null);
          existing = created ? await refreshQuizzes() : existing;
        }
        if (cancelled) return;
        if (existing && existing.length > 0) {
          await loadQuiz(existing[0]);
        }
      } catch (_err) {
        if (!cancelled) setError('Failed to initialize quiz studio.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    init();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeWorkspaceId]);

  useEffect(() => {
    if (!activeWorkspaceId) return;
    const timer = setInterval(() => {
      refreshArtifactStatus();
    }, 5000);
    return () => clearInterval(timer);
  }, [activeWorkspaceId, refreshArtifactStatus]);

  useEffect(() => {
    if (attempt) return;
    const timer = setInterval(() => {
      setElapsed((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [attempt]);

  const handleSelectOption = useCallback((optionId: string) => {
    if (showExplanation) return;
    setSelectedOptId(optionId);
    const q = questions[currentIndex];
    if (!q) return;
    const selectedIdx = q.options.findIndex((o) => o.id === optionId);
    if (selectedIdx >= 0) {
      setAnswers((prev) => ({ ...prev, [q.id]: selectedIdx }));
    }
    setShowExplanation(true);
  }, [currentIndex, questions, showExplanation]);

  const handleNext = useCallback(() => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      setSelectedOptId(null);
      setShowExplanation(false);
    }
  }, [currentIndex, questions.length]);

  const submitQuiz = useCallback(async (): Promise<QuizAttemptDTO | null> => {
    if (!activeQuiz) return null;
    try {
      const res = await apiClient<QuizAttemptDTO>(
        `/api/v1/learning/quizzes/${encodeURIComponent(activeQuiz.id)}/grade`,
        {
          method: 'POST',
          body: JSON.stringify({
            workspace_id: wsRef.current,
            answers,
            time_taken: elapsed,
          }),
        }
      );
      setAttempt(res);
      return res;
    } catch (_err) {
      setError('Failed to submit quiz results.');
      return null;
    }
  }, [activeQuiz, answers, elapsed]);

  const jumpToSource = useCallback(
    (mediaId?: string, seconds?: number) => {
      if (!mediaId || seconds == null) return;
      useAppStore.setState({
        activeMediaId: mediaId,
        targetSeekSeconds: seconds,
        activeView: 'view-video',
      });
    },
    []
  );

  const currentQuestion = questions[currentIndex] || null;

  return {
    quizzes,
    activeQuiz,
    selectedVersion,
    currentQuestion,
    currentIndex,
    totalQuestions: questions.length,
    selectedOptId,
    showExplanation,
    artifact,
    settings,
    loading,
    generating,
    error,
    toastMessage,
    attempt,
    elapsed,
    generateQuiz,
    selectVersion,
    handleSelectOption,
    handleNext,
    submitQuiz,
    updateSettings,
    jumpToSource,
    setActiveView,
    activeWorkspaceId,
    refreshQuizzes,
    refreshArtifactStatus,
  };
}
