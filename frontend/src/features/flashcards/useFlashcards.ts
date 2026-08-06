import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '@/services/apiClient';
import { useAppStore } from '@/store/useAppStore';

export interface FlashcardCardDTO {
  id: string;
  deck_id: string;
  card_type: string;
  front: string;
  back: string | null;
  cloze_text: string | null;
  options: string[] | null;
  concept_id: string | null;
  concept_name: string | null;
  media_id: string | null;
  source_chunk_ids: string[];
  start_time: number | null;
  end_time: number | null;
  ease_factor: number;
  interval_days: number;
  repetitions: number;
}

export interface FlashcardDeckDTO {
  id: string;
  workspace_id: string;
  name: string;
  version: number;
  status: string;
  media_ids: string[];
  concept_ids: string[];
  card_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface ReviewResultDTO {
  id: string;
  flashcard_id: string;
  rating: number;
  ease_factor: number;
  interval_days: number;
  repetitions: number;
}

interface UseFlashcardsOptions {
  autoGenerate?: boolean;
}

export interface WorkspaceLearningSettingsDTO {
  auto_evolve_flashcards: boolean;
  flashcard_target_budget_per_media: number;
  auto_evolve_quizzes: boolean;
  quiz_target_budget_per_media: number;
}

export function useFlashcards(options: UseFlashcardsOptions = {}) {
  const { autoGenerate = true } = options;
  const activeWorkspaceId = useAppStore((state) => state.activeWorkspaceId);
  const setActiveView = useAppStore((state) => state.setActiveView);

  const [decks, setDecks] = useState<FlashcardDeckDTO[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [activeDeck, setActiveDeck] = useState<FlashcardDeckDTO | null>(null);
  const [cards, setCards] = useState<FlashcardCardDTO[]>([]);
  const [settings, setSettings] = useState<WorkspaceLearningSettingsDTO>({
    auto_evolve_flashcards: true,
    flashcard_target_budget_per_media: 20,
    auto_evolve_quizzes: true,
    quiz_target_budget_per_media: 15,
  });
  const [loading, setLoading] = useState<boolean>(false);
  const [generating, setGenerating] = useState<boolean>(false);
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

  const refreshDecks = useCallback(async () => {
    const ws = wsRef.current;
    try {
      const data = await apiClient<FlashcardDeckDTO[]>(
        `/api/v1/learning/decks/${encodeURIComponent(ws)}`
      );
      setDecks(data || []);
      return data || [];
    } catch (_err) {
      setDecks([]);
      return [];
    }
  }, []);

  const generateDeck = useCallback(async () => {
    const ws = wsRef.current;
    if (!ws) return null;
    setGenerating(true);
    setError(null);
    try {
      const deck = await apiClient<FlashcardDeckDTO>(
        `/api/v1/learning/decks/${encodeURIComponent(ws)}?force_new_version=true`,
        { method: 'POST' }
      );
      await refreshDecks();
      return deck;
    } catch (_err) {
      setError('Failed to generate flashcard deck. Ensure concepts have been extracted.');
      return null;
    } finally {
      setGenerating(false);
    }
  }, [refreshDecks]);

  const selectVersion = useCallback(async (version: number) => {
    const ws = wsRef.current;
    setSelectedVersion(version);
    setLoading(true);
    setError(null);
    try {
      const deck = await apiClient<FlashcardDeckDTO>(
        `/api/v1/learning/decks/${encodeURIComponent(ws)}/version/${version}`
      );
      setActiveDeck(deck);
      const cardData = await apiClient<FlashcardCardDTO[]>(
        `/api/v1/learning/decks/${encodeURIComponent(deck.id)}/cards`
      );
      setCards(cardData || []);
    } catch (_err) {
      setActiveDeck(null);
      setCards([]);
      setError('Failed to load deck cards.');
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
        let existing = await refreshDecks();
        if (!existing || existing.length === 0) {
          if (!autoGenerate) {
            setLoading(false);
            return;
          }
          const created = await apiClient<FlashcardDeckDTO>(
            `/api/v1/learning/decks/${encodeURIComponent(wsRef.current)}`,
            { method: 'POST' }
          ).catch(() => null);
          existing = created ? await refreshDecks() : existing;
        }
        if (cancelled) return;
        if (existing && existing.length > 0) {
          const latest = existing[0];
          setActiveDeck(latest);
          setSelectedVersion(latest.version);
          const cardData = await apiClient<FlashcardCardDTO[]>(
            `/api/v1/learning/decks/${encodeURIComponent(latest.id)}/cards`
          ).catch(() => []);
          if (!cancelled) setCards(cardData || []);
        }
      } catch (_err) {
        if (!cancelled) setError('Failed to initialize flashcard studio.');
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

  const recordReview = useCallback(
    async (flashcardId: string, rating: number): Promise<ReviewResultDTO | null> => {
      try {
        const review = await apiClient<ReviewResultDTO>(`/api/v1/learning/reviews`, {
          method: 'POST',
          body: JSON.stringify({
            flashcard_id: flashcardId,
            workspace_id: wsRef.current,
            rating,
          }),
        });
        setCards((prev) =>
          prev.map((c) =>
            c.id === flashcardId
              ? {
                  ...c,
                  ease_factor: review.ease_factor,
                  interval_days: review.interval_days,
                  repetitions: review.repetitions,
                }
              : c
          )
        );
        return review;
      } catch (_err) {
        return null;
      }
    },
    []
  );

  const jumpToSource = useCallback(
    (mediaId: string | null, seconds: number | null) => {
      if (!mediaId || seconds == null) return;
      useAppStore.setState({
        activeMediaId: mediaId,
        targetSeekSeconds: seconds,
        activeView: 'view-video',
      });
    },
    []
  );

  return {
    decks,
    activeDeck,
    selectedVersion,
    cards,
    settings,
    loading,
    generating,
    error,
    refreshDecks,
    generateDeck,
    selectVersion,
    recordReview,
    updateSettings,
    jumpToSource,
    setActiveView,
    activeWorkspaceId,
  };
}
