'use client';

import React from 'react';
import { ChatMessage } from './useChat';
import { useAppStore } from '@/store/useAppStore';

interface ChatMessageItemProps {
  message: ChatMessage;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({ message }) => {
  const { setCurrentTime, setActiveView, setActiveMediaId, setTargetSeekSeconds } = useAppStore();
  const isUser = message.sender === 'user';

  const handleCitationClick = (startTime?: string, mediaId?: string) => {
    if (mediaId) {
      setActiveMediaId(mediaId);
    }
    if (startTime) {
      setCurrentTime(startTime);
      const parts = startTime.split(':');
      if (parts.length === 2) {
        const secs = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
        setTargetSeekSeconds(secs);
      }
    }
    setActiveView('view-video');
  };

  return (
    <div className={`flex gap-4 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : ''}`}>
      {/* Avatar */}
      {isUser ? (
        <div className="w-8 h-8 rounded flex items-center justify-center font-bold text-xs shrink-0 bg-surface-container-highest text-on-surface">
          DEV
        </div>
      ) : (
        <img
          src="/icon-black-hat.png"
          alt="Athenus"
          className="w-8 h-8 shrink-0"
        />
      )}

      {/* Message Content Bubble */}
      <div
        className={`p-4 rounded border text-xs leading-relaxed ${
          isUser
            ? 'bg-surface-container-high border-outline-variant text-on-surface'
            : 'bg-surface-container border-outline-variant text-on-surface space-y-3'
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>

        {/* Citations Badges */}
        {message.citations && message.citations.length > 0 && (
          <div className="pt-2 flex flex-wrap gap-2 border-t border-outline-variant/40">
            <span className="text-[10px] text-on-surface-variant font-mono flex items-center gap-1">
              <span>🎯</span> Grounded Citations:
            </span>
            {message.citations.map((cit, idx) => {
              const startStr = cit.startTime || '00:00';
              const endStr = cit.endTime ? ` - ${cit.endTime}` : '';
              const titleStr = cit.mediaTitle ? ` (${cit.mediaTitle})` : '';
              const tooltipText = cit.textSnippet ? `"${cit.textSnippet.substring(0, 100)}..."` : 'Jump to video citation';

              return (
                <button
                  key={idx}
                  title={tooltipText}
                  onClick={() => handleCitationClick(cit.startTime, cit.mediaId)}
                  className="px-2.5 py-1 rounded bg-secondary/15 border border-secondary/40 text-secondary text-[11px] font-mono hover:bg-secondary/30 transition-all cursor-pointer flex items-center gap-1 shadow-sm hover:scale-[1.02]"
                >
                  ⏱ {startStr}{endStr}{titleStr}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
