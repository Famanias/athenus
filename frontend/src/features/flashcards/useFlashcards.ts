import { useState, useEffect } from 'react';

export interface Flashcard {
  id: string;
  category: string;
  question: string;
  answer: string;
  easeFactor: number;
  intervalDays: number;
  dueDate: string;
}

const MOCK_FLASHCARDS: Flashcard[] = [
  {
    id: 'fc_1',
    category: 'ATTENTION MATH',
    question: 'What is the exact formula for Scaled Dot-Product Attention in Transformers?',
    answer: 'Attention(Q, K, V) = Softmax( (Q * K^T) / sqrt(d_k) ) * V',
    easeFactor: 2.5,
    intervalDays: 6,
    dueDate: 'Today',
  },
  {
    id: 'fc_2',
    category: 'OPTIMIZATION RATIONALE',
    question: 'Why do Transformers divide Query-Key dot products by sqrt(d_k)?',
    answer: 'To prevent large dot product magnitudes from pushing the Softmax function into vanishing gradient regions.',
    easeFactor: 2.36,
    intervalDays: 3,
    dueDate: 'Tomorrow',
  },
  {
    id: 'fc_3',
    category: 'POSITIONAL ENCODING',
    question: 'How do Transformers encode sequence order without recurrent loops?',
    answer: 'By adding sinusoidal functions of varying frequencies to initial input embeddings.',
    easeFactor: 2.5,
    intervalDays: 10,
    dueDate: 'In 3 days',
  },
];

export function useFlashcards() {
  const [cards, setCards] = useState<Flashcard[]>(MOCK_FLASHCARDS);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    async function fetchCards() {
      try {
        setLoading(true);
        const res = await fetch('http://localhost:8000/api/v1/learning/flashcards');
        if (res.ok) {
          const data = await res.json();
          if (data.flashcards && data.flashcards.length > 0) {
            setCards(data.flashcards);
          }
        }
      } catch (_err) {
        // Silent fallback
      } finally {
        setLoading(false);
      }
    }
    fetchCards();
  }, []);

  return { cards, loading };
}
