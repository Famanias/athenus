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

const MOCK_QUIZ_QUESTIONS: QuizQuestion[] = [
  {
    id: 'q_1',
    question: 'Why is the scaling factor sqrt(d_k) applied in Scaled Dot-Product Attention?',
    options: [
      { id: 'opt_a', text: 'A) To decrease linear matrix computation latency', isCorrect: false },
      { id: 'opt_b', text: 'B) To prevent Softmax gradients from vanishing for large vector dimensions', isCorrect: true },
      { id: 'opt_c', text: 'C) To eliminate positional encoding vectors', isCorrect: false },
    ],
    explanation: 'Correct! Large dot product values push the Softmax function into regions with extremely small gradient magnitudes, causing gradient vanishing during backpropagation.',
  },
  {
    id: 'q_2',
    question: 'What is the role of Positional Encodings in Transformer architectures?',
    options: [
      { id: 'opt_a', text: 'A) Injecting sequence order information using sinusoidal functions', isCorrect: true },
      { id: 'opt_b', text: 'B) Normalizing Query and Key vector dimensions', isCorrect: false },
      { id: 'opt_c', text: 'C) Reducing feed-forward layer parameter counts', isCorrect: false },
    ],
    explanation: 'Correct! Because Transformers evaluate tokens in parallel without recurrence, positional encodings provide required sequential ordering information.',
  },
];

export function useQuiz() {
  const [questions] = useState<QuizQuestion[]>(MOCK_QUIZ_QUESTIONS);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [selectedOptId, setSelectedOptId] = useState<string | null>(null);
  const [showExplanation, setShowExplanation] = useState<boolean>(false);

  const currentQuestion = questions[currentIndex];

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
  };
}
