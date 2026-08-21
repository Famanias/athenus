'use client';

import React from 'react';
import { NoteSectionDTO } from './useNotes';
import { formatSecondsToTimestamp } from '@/services/chatService';

interface NoteSectionCardProps {
  section: NoteSectionDTO;
  index: number;
}

export const NoteSectionCard: React.FC<NoteSectionCardProps> = ({
  section,
  index,
}) => {
  const hasTime = section.start_time !== null && section.start_time !== undefined;
  const isPageCitation = hasTime && section.start_time! < 100 && section.start_time! === section.end_time;
  const timestampLabel = isPageCitation
    ? `Page ${Math.floor(section.start_time!)}`
    : hasTime
    ? formatSecondsToTimestamp(section.start_time!)
    : null;

  return (
    <div className="bg-surface-container-low border border-outline-variant/50 rounded-xl p-5 space-y-3.5 hover:border-outline transition-colors shadow-sm">
      {/* Section Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="w-6 h-6 rounded-md bg-surface-container-highest flex items-center justify-center text-xs font-mono font-bold text-on-surface-variant">
            {index + 1}
          </span>
          <h4 className="font-semibold text-base text-on-surface">
            {section.heading || `Section ${index + 1}`}
          </h4>
        </div>

        {/* Static Non-Clickable Timestamp Label */}
        {hasTime && (
          <div
            className="flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-surface-container-high text-on-surface-variant border border-outline-variant/40 text-xs font-mono select-none"
          >
            <span className="material-symbols-outlined text-[13px] opacity-70">
              schedule
            </span>
            <span>{timestampLabel}</span>
          </div>
        )}
      </div>

      {/* Section Body */}
      <div className="text-xs text-on-surface/90 leading-relaxed space-y-1.5 pl-8.5">
        {section.body.split('\n').map((line, idx) => {
          const trimmed = line.trim();
          if (!trimmed) return null;
          if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
            return (
              <div key={idx} className="flex items-start gap-2 text-on-surface/90">
                <span className="text-primary font-bold">·</span>
                <span>{trimmed.replace(/^[-*]\s+/, '')}</span>
              </div>
            );
          }
          return (
            <p key={idx} className="text-on-surface/85">
              {trimmed}
            </p>
          );
        })}
      </div>

      {/* Key Takeaways Pills */}
      {section.key_takeaways && section.key_takeaways.length > 0 && (
        <div className="pt-2 pl-8.5 border-t border-outline-variant/30 flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] font-mono uppercase tracking-wider text-on-surface-variant font-semibold mr-1">
            Key Insights:
          </span>
          {section.key_takeaways.map((takeaway, tIdx) => (
            <span
              key={tIdx}
              className="text-[11px] bg-surface-container-high text-on-surface-variant px-2.5 py-0.5 rounded-full border border-outline-variant/40"
            >
              {takeaway}
            </span>
          ))}
        </div>
      )}
    </div>
  );
};
