import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '@/services/apiClient';
import { useAppStore } from '@/store/useAppStore';

export interface QuizItemDTO {
  id: string;
  quiz_id: string;
  concept_id: string | null;
  concept_name: string | null;
  question_text: string;
  options: string[];
  correct_index: number;
  explanation: string;
  media_id: string | null;
  source_chunk_ids: string[];
  start_time: number | null;
  end_time: number | null;
}

export interface QuizContainerDTO {
  id: string;
  workspace_id: string;
  title: string;
  version: number;
  status: string;
  concept_ids: string[];
  question_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface QuizAttemptDTO {
  id: string;
  quiz_id: string;
  workspace_id: string;
  version: number;
  score: number;
  total_questions: number;
  correct_count: number;
  answers: Record<string, { user_answer: number; correct_index: number; is_correct: boolean }> | null;
  time_taken: number;
  created_at: string | null;
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: { id: string; text: string; isCorrect: boolean }[];
  explanation: string;
  conceptName: string | null;
  startTime: number | null;
  mediaId: string | null;
}

interface UseQuizOptions {
  autoGenerate?: boolean;
}

export interface WorkspaceLearningSettingsDTO {
  auto_evolve_flashcards: boolean;
  flashcard_target_budget_per_media: number;
  auto_evolve_quizzes: boolean;
  quiz_target_budget_per_media: number;
}

export function useQuiz(options: UseQuizOptions = {}) {
  const { autoGenerate = true } = options;
  const activeWorkspaceId = useAppStore((state) => state.activeWorkspaceId);
  const setActiveView = useAppStore((state) => state.setActiveView);

  const [quizzes, setQuizzes] = useState<QuizContainerDTO[]>([]);
  const [activeQuiz, setActiveQuiz] = useState<QuizContainerDTO | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [settings, setSettings] = useState<WorkspaceLearningSettingsDTO>({
    auto_evolve_flashcards: true,
    flashcard_target_budget_per_media: 20,
    auto_evolve_quizzes: true,
    quiz_target_budget_per_media: 15,
  });
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [selectedOptId, setSelectedOptId] = useState<string | null>(null);
  const [showExplanation, setShowExplanation] = useState<boolean>(false);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
  const [attempt, setAttempt] = useState<QuizAttemptDTO | null>(null);
  const [elapsed, setElapsed] = useState<number>(0);
  const [error, setError] = useState<string | null>(null);

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

  const generateQuiz = useCallback(async () => {
    const ws = wsRef.current;
    if (!ws) return null;
    setGenerating(true);
    setError(null);
    try {
      const quiz = await apiClient<QuizContainerDTO>(
        `/api/v1/learning/quizzes/${encodeURIComponent(ws)}/generate?force_new_version=true`,
        { method: 'POST' }
      );
      await refreshQuizzes();
      return quiz;
    } catch (_err) {
      setError('Failed to generate quiz. Ensure concepts have been extracted.');
      return null;
    } finally {
      setGenerating(false);
    }
  }, [refreshQuizzes]);

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

  useEffect(() => {
    let cancelled = false;
    async function init() {
      if (!wsRef.current) return;
      setLoading(true);
      fetchSettings();
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

  const selectVersion = useCallback(
    async (version: number) => {
      const ws = wsRef.current;
      try {
        const quiz = await apiClient<QuizContainerDTO>(
          `/api/v1/learning/quizzes/workspace/${encodeURIComponent(ws)}/version/${version}`
        );
        await loadQuiz(quiz);
      } catch (_err) {
        setError('Failed to load quiz version.');
      }
    },
    [loadQuiz]
  );

  // Timer for attempt
  useEffect(() => {
    if (!activeQuiz || attempt || questions.length === 0) return;
    const timer = setInterval(() => setElapsed((prev) => prev + 1), 1000);
    return () => clearInterval(timer);
  }, [activeQuiz, attempt, questions.length]);

  const handleSelectOption = (opt: { id: string; text: string; isCorrect: boolean }) => {
    if (showExplanation) return;
    setSelectedOptId(opt.id);
    setShowExplanation(true);
    const q = questions[currentIndex];
    if (q) {
      const optIdx = q.options.findIndex((o) => o.id === opt.id);
      setAnswers((prev) => ({ ...prev, [q.id]: optIdx }));
    }
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      const nextQ = questions[currentIndex + 1];
      const nextAnswer = nextQ ? answers[nextQ.id] : undefined;
      setSelectedOptId(nextAnswer != null ? nextQ.options[nextAnswer]?.id : null);
      setShowExplanation(nextAnswer != null);
    }
  };

  const submitQuiz = useCallback(async () => {
    if (!activeQuiz) return;
    try {
      const result = await apiClient<QuizAttemptDTO>(
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
      setAttempt(result);
    } catch (_err) {
      setError('Failed to submit quiz.');
    }
  }, [activeQuiz, answers, elapsed]);

  const correctCount = useMemo(() => {
    let count = 0;
    for (const q of questions) {
      const answered = q.options.findIndex((o) => o.isCorrect);
      if (answers[q.id] === answered) count++;
    }
    return count;
  }, [questions, answers]);

  const jumpToSource = useCallback((mediaId: string | null, seconds: number | null) => {
    if (!mediaId || seconds == null) return;
    useAppStore.setState({
      activeMediaId: mediaId,
      targetSeekSeconds: seconds,
      activeView: 'view-video',
    });
  }, []);

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
    settings,
    loading,
    generating,
    error,
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
  };
}
