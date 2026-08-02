'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';

export const TranscriptReader: React.FC = () => {
  const { setCurrentTime, setActiveView } = useAppStore();
  const [autoScroll, setAutoScroll] = useState<boolean>(true);

  const handleTimestampClick = (timeStr: string) => {
    setCurrentTime(timeStr);
    setActiveView('view-video');
  };

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-4xl mx-auto space-y-6 w-full">
      {/* Header Toolbar */}
      <div className="flex justify-between items-center pb-4 border-b border-outline-variant">
        <div>
          <h2 className="font-carvist text-2xl font-bold text-on-surface">
            Full Document Transcript Reader
          </h2>
          <p className="text-xs text-on-surface-variant mt-1">
            Lecture 14 • Advanced AI Foundations • 1,420 Words
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-mono text-on-surface-variant cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded accent-secondary"
            />
            Auto-Scroll
          </label>
          <Button variant="secondary" size="sm" icon="chat" onClick={() => setActiveView('view-chat')}>
            Ask AI Assistant
          </Button>
        </div>
      </div>

      {/* Paragraph Document Body */}
      <div className="p-8 bg-surface-container-low border border-outline-variant rounded space-y-6 text-xs leading-relaxed text-on-surface-variant">
        <div className="space-y-2">
          <span
            onClick={() => handleTimestampClick('00:15')}
            className="text-secondary font-mono font-semibold cursor-pointer hover:underline"
          >
            ⏱ 00:15
          </span>
          <p>
            In today&apos;s session, we are diving deep into{' '}
            <span className="gold-highlight">Transformers</span> and why their attention mechanism redefined how we think about{' '}
            <span className="gold-highlight">Contextual Embeddings</span>. The primary innovation was not just parallelization, but dynamic query-key matrix dot products.
          </p>
        </div>

        <div className="space-y-2">
          <span
            onClick={() => handleTimestampClick('05:15')}
            className="text-secondary font-mono font-semibold cursor-pointer hover:underline"
          >
            ⏱ 05:15
          </span>
          <p>
            Consider the <span className="gold-highlight">Attention Is All You Need</span> paper. Before this, we relied heavily on Recurrent Neural Networks which suffered from vanishing gradient degradation in long sequences. Self-attention allows every token to attend to every other token.
          </p>
        </div>

        <div className="space-y-2">
          <span
            onClick={() => handleTimestampClick('12:40')}
            className="text-secondary font-mono font-semibold cursor-pointer hover:underline"
          >
            ⏱ 12:40
          </span>
          <p>
            By using <span className="gold-highlight">sqrt(d_k)</span> as a scaling factor, we prevent the dot products from growing excessively large for high dimensions. This keeps the <span className="gold-highlight">Softmax gradients</span> stable during backpropagation.
          </p>
        </div>

        <div className="space-y-2">
          <span
            onClick={() => handleTimestampClick('18:20')}
            className="text-secondary font-mono font-semibold cursor-pointer hover:underline"
          >
            ⏱ 18:20
          </span>
          <p>
            Positional encodings inject positional ordering into token embeddings via sinusoidal functions of varying frequencies, preserving sequential relationships without recurrent loops.
          </p>
        </div>
      </div>
    </div>
  );
};
