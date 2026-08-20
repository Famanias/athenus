'use client';

import React, { useState } from 'react';
import { NoteDTO } from './useNotes';

interface NoteSummaryHeaderProps {
  note: NoteDTO;
}

export const NoteSummaryHeader: React.FC<NoteSummaryHeaderProps> = ({ note }) => {
  const [checkedItems, setCheckedItems] = useState<Record<number, boolean>>({});

  const toggleItem = (idx: number) => {
    setCheckedItems((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <div className="bg-surface-container-low border border-outline-variant/60 rounded-xl p-6 space-y-4 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 border-b border-outline-variant/30 pb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary font-bold">
            <span className="material-symbols-outlined text-xl">auto_stories</span>
          </div>
          <div>
            <h3 className="font-type-light text-xl font-bold text-on-surface">
              {note.title || 'Structured Study Notes'}
            </h3>
            <p className="text-xs text-on-surface-variant flex items-center gap-2 mt-0.5">
              <span>Version {note.version}</span>
              <span>·</span>
              <span>{note.sections?.length || 0} Core Sections</span>
              {note.created_at && (
                <>
                  <span>·</span>
                  <span>{new Date(note.created_at).toLocaleDateString()}</span>
                </>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono font-medium px-2.5 py-1 rounded bg-secondary/10 text-secondary border border-secondary/20 uppercase tracking-wider">
            AI Synthesized
          </span>
        </div>
      </div>

      {note.summary && (
        <div className="space-y-1.5">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-on-surface-variant font-mono">
            Executive Summary
          </h4>
          <p className="text-sm text-on-surface leading-relaxed bg-surface/40 p-3 rounded-lg border border-outline-variant/30">
            {note.summary}
          </p>
        </div>
      )}

      {note.action_items && note.action_items.length > 0 && (
        <div className="space-y-2 pt-1">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-primary font-mono flex items-center gap-1.5">
            <span className="material-symbols-outlined text-sm">checklist</span>
            Action Items & Key Tasks
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {note.action_items.map((item, idx) => {
              const isChecked = !!checkedItems[idx];
              return (
                <div
                  key={idx}
                  onClick={() => toggleItem(idx)}
                  className={`flex items-start gap-2.5 p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                    isChecked
                      ? 'bg-primary/5 border-primary/30 text-on-surface/50 line-through'
                      : 'bg-surface-container-high/40 border-outline-variant/40 text-on-surface hover:border-primary/40'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => {}}
                    className="mt-0.5 rounded border-outline cursor-pointer accent-primary"
                  />
                  <span className="leading-snug">{item}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
