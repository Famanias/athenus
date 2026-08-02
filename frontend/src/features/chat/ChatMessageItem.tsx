'use client';

import React from 'react';
import { ChatMessage } from './useChat';
import { useAppStore } from '@/store/useAppStore';

interface ChatMessageItemProps {
  message: ChatMessage;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({ message }) => {
  const { setCurrentTime, setActiveView } = useAppStore();
  const isUser = message.sender === 'user';

  const handleCitationClick = (startTime: string) => {
    setCurrentTime(startTime);
    setActiveView('view-video');
  };

  return (
    <div
      className={`flex gap-4 max-w-3xl ${
        isUser ? 'ml-auto flex-row-reverse' : ''
      }`}
    >
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded flex items-center justify-center font-bold text-xs shrink-0 ${
          isUser
            ? 'bg-surface-container-highest text-on-surface'
            : 'bg-secondary text-on-secondary font-carvist text-sm'
        }`}
      >
        {isUser ? 'DEV' : '🦉'}
      </div>

      {/* Message Content Bubble */}
      <div
        className={`p-4 rounded border text-xs leading-relaxed ${
          isUser
            ? 'bg-surface-container-high border-outline-variant text-on-surface'
            : 'bg-surface-container border-outline-variant text-on-surface space-y-3'
        }`}
      >
        <p>{message.content}</p>

        {/* Citations Badges */}
        {message.citations && message.citations.length > 0 && (
          <div className="pt-2 flex flex-wrap gap-2 border-t border-outline-variant/40">
            <span className="text-[10px] text-on-surface-variant font-mono">
              Grounded Citations:
            </span>
            {message.citations.map((cit, idx) => (
              <button
                key={idx}
                onClick={() => handleCitationClick(cit.startTime)}
                className="px-2 py-0.5 rounded bg-secondary/15 border border-secondary/40 text-secondary text-[11px] font-mono hover:bg-secondary/30 transition-all cursor-pointer"
              >
                ⏱ {cit.startTime} - {cit.endTime} ({cit.mediaTitle})
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
