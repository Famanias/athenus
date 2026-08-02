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

export function useFlashcards() {
  const [cards, setCards] = useState<Flashcard[]>([]);
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
          } else {
            setCards([]);
          }
        } else {
          setCards([]);
        }
      } catch (_err) {
        setCards([]);
      } finally {
        setLoading(false);
      }
    }
    fetchCards();
  }, []);

  return { cards, loading };
}
