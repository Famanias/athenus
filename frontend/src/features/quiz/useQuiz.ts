import { useState } from 'react';

export interface QuizOption {
  id: string;
  text: string;
  isCorrect: boolean;
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: QuizOption[];
  explanation: string;
}

export function useQuiz() {
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [selectedOptId, setSelectedOptId] = useState<string | null>(null);
  const [showExplanation, setShowExplanation] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);

  const currentQuestion = questions[currentIndex] || null;

  const handleSelectOption = (opt: QuizOption) => {
    setSelectedOptId(opt.id);
    setShowExplanation(true);
  };

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex((prev) => prev + 1);
      setSelectedOptId(null);
      setShowExplanation(false);
    }
  };

  return {
    currentQuestion,
    currentIndex,
    totalQuestions: questions.length,
    selectedOptId,
    showExplanation,
    handleSelectOption,
    handleNext,
    loading,
  };
}
