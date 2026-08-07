'use client';

import React, { useState } from 'react';
import { useFlashcards, FlashcardCardDTO } from './useFlashcards';
import { Button } from '@/components/ui/Button';

function cardFrontText(card: FlashcardCardDTO): string {
  if (card.card_type === 'cloze' && card.cloze_text) return card.cloze_text;
  return card.front || card.concept_name || '';
}

function cardBackText(card: FlashcardCardDTO): string {
  if (card.card_type === 'cloze') return card.back || card.front || '';
  return card.back || card.options?.join('  ·  ') || '';
}

export const FlashcardGrid: React.FC = () => {
  const {
    decks,
    activeDeck,
    selectedVersion,
    cards,
    artifact,
    settings,
    loading,
    generating,
    error,
    toastMessage,
    generateDeck,
    selectVersion,
    updateSettings,
    setActiveView,
  } = useFlashcards();

  const [flippedMap, setFlippedMap] = useState<Record<string, boolean>>({});

  const toggleFlip = (id: string) => {
    setFlippedMap((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-5xl mx-auto space-y-6 w-full">
      {/* Completion Toast Banner */}
      {toastMessage && (
        <div className="px-4 py-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 font-mono text-xs font-semibold animate-pulse flex items-center justify-between">
          <span>{toastMessage}</span>
          <span className="text-[10px] text-emerald-400/60 uppercase tracking-wider">Active version synced</span>
        </div>
      )}
      {/* Header */}
      <div className="flex justify-between items-center pb-4 border-b border-outline-variant">
        <div>
          <h2 className="font-carvist text-2xl font-bold text-on-surface">
            Active Recall Flashcards (Anki SM-2)
          </h2>
          <p className="text-xs text-on-surface-variant mt-1">
            Click any flashcard to flip between Question and Answer, then rate your recall.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Auto-Evolve Control */}
          <div className="flex items-center gap-2 bg-surface-container-high px-3 py-1.5 rounded-lg border border-outline-variant/50">
            <label className="flex items-center gap-1.5 text-xs text-on-surface cursor-pointer select-none">
              <input
                type="checkbox"
                checked={settings.auto_evolve_flashcards}
                onChange={(e) => updateSettings({ auto_evolve_flashcards: e.target.checked })}
                className="accent-primary rounded"
              />
              <span className="font-medium text-xs">⚡ Auto-Evolve</span>
            </label>
            <span className="text-outline-variant">|</span>
            <select
              value={settings.flashcard_target_budget_per_media}
              onChange={(e) => updateSettings({ flashcard_target_budget_per_media: Number(e.target.value) })}
              className="bg-transparent text-xs font-mono text-primary outline-none cursor-pointer"
            >
              <option value={10} className="bg-surface text-on-surface">Compact (~10/video)</option>
              <option value={20} className="bg-surface text-on-surface">Standard (~20/video)</option>
              <option value={40} className="bg-surface text-on-surface">Deep (~40/video)</option>
            </select>
          </div>

          {activeDeck && (
            <span className="font-mono text-xs text-secondary bg-secondary/10 px-3 py-1 rounded border border-secondary/30">
              Deck v{activeDeck.version} · {activeDeck.card_count} cards
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            icon="add_card"
            disabled={generating}
            onClick={() => generateDeck()}
          >
            {generating ? 'Generating...' : activeDeck ? 'Regenerate' : 'Generate Deck'}
          </Button>
        </div>
      </div>

      {/* Independent Flashcard Artifact Lifecycle Status Bar */}
      <div className="px-4 py-2 border border-outline-variant bg-surface-container-low rounded flex items-center gap-3 text-[11px] font-mono">
        <span className="text-on-surface-variant">Artifact:</span>
        <span className={`font-bold uppercase ${artifact?.status === 'failed' ? 'text-rose-400' : artifact?.status === 'ready' ? 'text-emerald-400' : 'text-secondary'}`}>
          {artifact?.status || 'idle'}
        </span>
        {artifact?.stage && artifact.stage !== 'ready' && (
          <span className="text-on-surface-variant/70">{artifact.stage.replace(/_/g, ' ')}</span>
        )}
        <span className="text-on-surface-variant/60">progress {artifact?.progress ?? 0}%</span>
        {artifact?.message && (
          <span className="text-on-surface-variant truncate">{artifact.message}</span>
        )}
        <div className="flex-1 h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
          <div
            className="h-full rounded-full bg-secondary transition-all"
            style={{ width: `${artifact?.progress ?? 0}%` }}
          />
        </div>
      </div>

      {/* Version selector */}
      {decks.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[10px] text-on-surface-variant uppercase tracking-wider">
            Deck versions:
          </span>
          {decks.map((deck) => (
            <button
              key={deck.id}
              onClick={() => selectVersion(deck.version)}
              className={`font-mono text-xs px-3 py-1 rounded border transition-colors ${
                selectedVersion === deck.version
                  ? 'bg-secondary text-on-secondary border-secondary'
                  : 'bg-surface-container-low text-on-surface-variant border-outline-variant hover:bg-surface-container-high'
              }`}
            >
              v{deck.version}
              {deck.status !== 'ready' && <span className="ml-1">({deck.status})</span>}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="p-3 rounded border border-error/40 bg-error/10 text-xs text-error font-mono">
          {error}
        </div>
      )}

      {loading && (
        <div className="p-12 text-center text-xs text-on-surface-variant font-mono">
          Loading flashcard deck...
        </div>
      )}

      {!loading && !error && cards.length === 0 && (
        <div className="p-12 border border-dashed border-outline-variant rounded-lg bg-surface-container-low text-center space-y-3">
          <span className="text-4xl block">🎴</span>
          <h4 className="font-bold text-sm text-on-surface">No Flashcards in Active Deck</h4>
          <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
            Process a lecture video to extract concepts, then generate an SM-2 spaced
            repetition flashcard deck grounded in your knowledge graph.
          </p>
          <div className="flex justify-center gap-3">
            <Button variant="primary" icon="upload_file" onClick={() => setActiveView('view-ingestion')}>
              Upload Lecture
            </Button>
            <Button variant="outline" icon="auto_awesome" disabled={generating} onClick={() => generateDeck()}>
              Generate Deck
            </Button>
          </div>
        </div>
      )}

      {/* Card Grid */}
      {!loading && cards.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {cards.map((card) => {
            const isFlipped = !!flippedMap[card.id];
            return (
              <div key={card.id} className="flex flex-col gap-2">
                <div
                  onClick={() => toggleFlip(card.id)}
                  className={`flashcard-box ${isFlipped ? 'flipped' : ''}`}
                >
                  <div className="flashcard-inner">
                    {/* Question Front */}
                    <div className="flashcard-front">
                      <span className="font-mono text-[10px] text-secondary uppercase tracking-wider font-semibold">
                        {card.card_type}
                      </span>
                      <p className="text-xs font-semibold text-center my-auto text-on-surface leading-relaxed">
                        {cardFrontText(card)}
                      </p>
                      <span className="text-[10px] text-on-surface-variant/50 font-mono text-center">
                        Click to flip 🔄
                      </span>
                    </div>

                    {/* Answer Back (Physical Card UX - Answer ONLY) */}
                    <div className="flashcard-back">
                      <span className="font-mono text-[10px] text-secondary uppercase tracking-wider font-semibold">
                        ANSWER
                      </span>
                      <p className="text-xs font-mono font-semibold text-center my-auto leading-relaxed">
                        {cardBackText(card)}
                      </p>
                      <span className="text-[10px] text-on-surface-variant/50 font-mono text-center">
                        Click to flip 🔄
                      </span>
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
