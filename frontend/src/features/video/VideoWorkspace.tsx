'use client';

import React from 'react';
import { useVideo } from './useVideo';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';

export const VideoWorkspace: React.FC = () => {
  const { currentTime, segments, videoRef, seekTo } = useVideo();
  const { setActiveView } = useAppStore();

  return (
    <div className="flex-1 flex overflow-hidden w-full h-full">
      {/* Video Player Side (60%) */}
      <div className="w-[60%] bg-black flex flex-col border-r border-outline-variant">
        <div className="flex-1 bg-surface-container-lowest flex flex-col items-center justify-center p-8 text-center space-y-4 relative">
          <video
            ref={videoRef}
            controls
            className="w-full h-full object-contain rounded border border-outline-variant"
            poster="https://lh3.googleusercontent.com/aida-public/AB6AXuCR7m0hlwOlm3ndopej37zycr0eQRjmRalljkWoJwvnL2AyO7AIpmqh_WaaGSkqt7Kiyyb5IwsU2dtwhp9BWyYvELU1BppcZSiKERNydycgaERF0CouYzW01MGC-0qgitxFaSMIBCdih54EqmaoORPLGz-vRGu8dLs-QuzDKseAtKeuvSmXSUDrOUjJJ27Ryd5I_TvuxzMe91RHTda5ndYSIFKudteCyrY9ptCDf435YqBxJSCV-ctd"
          />
        </div>
        <div className="p-4 bg-surface-container-low border-t border-outline-variant flex justify-between items-center text-xs">
          <div>
            <h3 className="font-bold text-on-surface text-sm">
              Lecture 14: Attention Mechanisms in Transformers
            </h3>
            <span className="font-mono text-secondary text-xs">
              Current Time: {currentTime} / 42:15
            </span>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" icon="bookmark">
              Bookmark [{currentTime}]
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon="layers"
              onClick={() => setActiveView('view-flashcards')}
            >
              Add Flashcard
            </Button>
          </div>
        </div>
      </div>

      {/* Synchronized Transcript Side (40%) */}
      <div className="w-[40%] flex flex-col bg-surface-container-lowest">
        <div className="p-4 border-b border-outline-variant font-mono text-xs font-semibold text-secondary uppercase tracking-wider flex justify-between items-center">
          <span>Synchronized Transcript</span>
          <span className="text-[10px] text-on-surface-variant font-normal">Click timestamp to seek</span>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4 custom-scrollbar text-xs leading-relaxed">
          {segments.map((seg) => (
            <div
              key={seg.id}
              onClick={() => seekTo(seg.timestamp)}
              className={`p-3 rounded transition-all cursor-pointer ${
                currentTime === seg.timestamp || seg.isHighlighted
                  ? 'bg-surface-container-high border-l-2 border-secondary text-on-surface shadow-md'
                  : 'hover:bg-surface-container text-on-surface-variant'
              }`}
            >
              <div className="flex justify-between items-center mb-1">
                <span className="text-secondary font-mono font-semibold">
                  ⏱ {seg.timestamp}
                </span>
                <span className="text-[10px] font-mono text-on-surface-variant/60">
                  {seg.speaker}
                </span>
              </div>
              <p className={seg.isHighlighted ? 'gold-highlight inline' : ''}>
                {seg.text}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
