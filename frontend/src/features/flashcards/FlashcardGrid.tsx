'use client';

import React, { useState } from 'react';
import { useFlashcards } from './useFlashcards';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';

export const FlashcardGrid: React.FC = () => {
  const { cards, loading } = useFlashcards();
  const { setActiveView } = useAppStore();
  const [flippedMap, setFlippedMap] = useState<Record<string, boolean>>({});

  const toggleFlip = (id: string) => {
    setFlippedMap((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-5xl mx-auto space-y-6 w-full">
      {/* Header */}
      <div className="flex justify-between items-center pb-4 border-b border-outline-variant">
        <div>
          <h2 className="font-carvist text-2xl font-bold text-on-surface">
            Active Recall Flashcards (Anki SM-2)
          </h2>
          <p className="text-xs text-on-surface-variant mt-1">
            Click any flashcard to flip between Question and Answer.
          </p>
        </div>
        <span className="font-mono text-xs text-secondary bg-secondary/10 px-3 py-1 rounded border border-secondary/30">
          {cards.length} Active Deck Cards
        </span>
      </div>

      {loading && (
        <div className="p-12 text-center text-xs text-on-surface-variant font-mono">
          Loading flashcard deck...
        </div>
      )}

      {!loading && cards.length === 0 && (
        <div className="p-12 border border-dashed border-outline-variant rounded-lg bg-surface-container-low text-center space-y-3">
          <span className="text-4xl block">🎴</span>
          <h4 className="font-bold text-sm text-on-surface">No Flashcards in Active Deck</h4>
          <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
            Upload and process a lecture video to generate active recall flashcards with Anki SM-2 spaced repetition schedules.
          </p>
          <Button variant="primary" icon="upload_file" onClick={() => setActiveView('view-ingestion')}>
            Upload Lecture
          </Button>
        </div>
      )}

      {/* Card Grid */}
      {!loading && cards.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cards.map((card) => {
            const isFlipped = !!flippedMap[card.id];
            return (
              <div
                key={card.id}
                onClick={() => toggleFlip(card.id)}
                className={`flashcard-box ${isFlipped ? 'flipped' : ''}`}
              >
                <div className="flashcard-inner">
                  {/* Question Front */}
                  <div className="flashcard-front">
                    <span className="font-mono text-[10px] text-secondary uppercase tracking-wider font-semibold">
                      {card.category}
                    </span>
                    <p className="text-xs font-semibold text-center my-auto text-on-surface leading-relaxed">
                      {card.question}
                    </p>
                    <span className="text-[10px] text-on-surface-variant/50 font-mono text-center">
                      Click to flip 🔄
                    </span>
                  </div>

                  {/* Answer Back */}
                  <div className="flashcard-back">
                    <span className="font-mono text-[10px] text-secondary uppercase tracking-wider font-semibold">
                      ANSWER & RECALL
                    </span>
                    <p className="text-xs font-mono font-semibold text-center my-auto leading-relaxed">
                      {card.answer}
                    </p>
                    <div className="text-[10px] font-mono text-secondary text-center flex justify-between pt-2 border-t border-secondary/30">
                      <span>Ease: {card.easeFactor}</span>
                      <span>Due: {card.dueDate}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
