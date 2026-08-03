'use client';

import React, { useState } from 'react';
import { useChat } from '@/features/chat/useChat';
import { useAppStore } from '@/store/useAppStore';
import { formatSecondsToTimestamp } from '@/services/chatService';

interface EmbeddedChatWidgetProps {
  currentTimestampSeconds: number;
  selectedTranscriptText?: string;
  onClearSelectedText?: () => void;
}

export const EmbeddedChatWidget: React.FC<EmbeddedChatWidgetProps> = ({
  currentTimestampSeconds,
  selectedTranscriptText,
  onClearSelectedText,
}) => {
  const { messages, sendMessage, isGenerating, clearConversation } = useChat();
  const { setActiveView, setCurrentTime, setTargetSeekSeconds } = useAppStore();
  const [localInput, setLocalInput] = useState<string>('');

  const currentFormattedTime = formatSecondsToTimestamp(currentTimestampSeconds);

  const handleSend = async (queryText?: string) => {
    const textToSend = queryText || localInput;
    if (!textToSend.trim() || isGenerating) return;

    await sendMessage(textToSend, currentTimestampSeconds, selectedTranscriptText);
    setLocalInput('');
    if (onClearSelectedText) onClearSelectedText();
  };

  const handleCitationClick = (startTime?: string) => {
    if (startTime) {
      setCurrentTime(startTime);
      const parts = startTime.split(':');
      if (parts.length === 2) {
        const secs = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
        setTargetSeekSeconds(secs);
      }
    }
  };

  return (
    <div className="flex flex-col h-full bg-surface-container-lowest overflow-hidden text-xs">
      {/* Widget Header Bar */}
      <div className="p-3 bg-surface-container-low border-b border-outline-variant flex justify-between items-center shrink-0">
        <div className="flex items-center gap-2">
          <span className="font-bold text-on-surface font-mono text-xs flex items-center gap-1">
            <span>💬</span> AI Assistant
          </span>
          <span className="bg-secondary/15 border border-secondary/40 text-secondary text-[10px] font-mono px-2 py-0.5 rounded-full">
            📍 {currentFormattedTime}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveView('view-chat')}
            title="Expand to Full Chat View"
            className="px-2 py-1 bg-surface-container hover:bg-surface-container-high border border-outline-variant rounded text-[10px] font-mono text-on-surface-variant hover:text-on-surface transition-colors flex items-center gap-1"
          >
            Full Chat ↗
          </button>
          <button
            onClick={clearConversation}
            title="Clear Chat"
            className="text-[10px] text-on-surface-variant hover:text-rose-400 font-mono"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Selected Text Context Banner */}
      {selectedTranscriptText && (
        <div className="p-2 bg-secondary/10 border-b border-secondary/30 flex justify-between items-center text-[11px] text-secondary font-mono shrink-0">
          <span className="truncate max-w-[85%]">
            📝 Selected: "{selectedTranscriptText}"
          </span>
          <button onClick={onClearSelectedText} className="text-on-surface-variant hover:text-on-surface font-bold">
            ✕
          </button>
        </div>
      )}

      {/* Quick Prompt Chips */}
      <div className="p-2.5 border-b border-outline-variant/40 bg-surface-container-lowest flex flex-wrap gap-1.5 shrink-0">
        <button
          onClick={() => handleSend("Can you explain what was just discussed around this timestamp?")}
          disabled={isGenerating}
          className="px-2 py-1 rounded-full bg-surface-container border border-outline-variant text-[10px] text-on-surface-variant hover:text-secondary hover:border-secondary transition-all"
        >
          💡 Explain this
        </button>
        <button
          onClick={() => handleSend("Summarize the key points from the last 2 minutes.")}
          disabled={isGenerating}
          className="px-2 py-1 rounded-full bg-surface-container border border-outline-variant text-[10px] text-on-surface-variant hover:text-secondary hover:border-secondary transition-all"
        >
          📝 Summarize last 2m
        </button>
        <button
          onClick={() => handleSend("Generate a quick quiz question based on this section.")}
          disabled={isGenerating}
          className="px-2 py-1 rounded-full bg-surface-container border border-outline-variant text-[10px] text-on-surface-variant hover:text-secondary hover:border-secondary transition-all"
        >
          ❓ Quiz me
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {messages.length === 0 && (
          <div className="p-6 text-center text-on-surface-variant space-y-2 border border-dashed border-outline-variant rounded bg-surface-container-low/50 mt-4">
            <span className="text-2xl block">🦉</span>
            <p className="font-bold text-xs">Context-Aware Video Assistant</p>
            <p className="text-[11px] leading-relaxed">
              Ask questions about what's being discussed at <span className="text-secondary font-mono font-bold">{currentFormattedTime}</span> without leaving the video.
            </p>
          </div>
        )}

        {messages.map((msg) => {
          const isUser = msg.sender === 'user';
          return (
            <div key={msg.id} className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} space-y-1`}>
              <div
                className={`p-3 rounded-lg border max-w-[90%] text-xs leading-relaxed ${
                  isUser
                    ? 'bg-surface-container-high border-outline-variant text-on-surface'
                    : 'bg-surface-container border-outline-variant text-on-surface space-y-2'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>

                {/* Grounded Citation Badges */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="pt-1.5 flex flex-wrap gap-1 border-t border-outline-variant/30">
                    {msg.citations.map((cit, idx) => (
                      <button
                        key={idx}
                        onClick={() => handleCitationClick(cit.startTime)}
                        className="px-2 py-0.5 rounded bg-secondary/15 border border-secondary/40 text-secondary text-[10px] font-mono hover:bg-secondary/30 transition-all"
                      >
                        ⏱ {cit.startTime}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <span className="text-[9px] text-on-surface-variant/60 font-mono px-1">
                {msg.timestamp}
              </span>
            </div>
          );
        })}

        {isGenerating && (
          <div className="flex items-center gap-2 p-3 bg-surface-container rounded border border-outline-variant text-xs text-secondary font-mono animate-pulse">
            <span>🦉</span> Processing contextual inquiry...
          </div>
        )}
      </div>

      {/* Input Bar */}
      <div className="p-3 bg-surface-container-low border-t border-outline-variant shrink-0">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex gap-2"
        >
          <input
            type="text"
            placeholder={`Ask about lecture @ ${currentFormattedTime}...`}
            value={localInput}
            onChange={(e) => setLocalInput(e.target.value)}
            className="flex-1 bg-surface-container border border-outline-variant rounded p-2 text-xs text-on-surface focus:border-secondary focus:outline-none"
          />
          <button
            type="submit"
            disabled={!localInput.trim() || isGenerating}
            className="px-3 py-2 bg-secondary disabled:opacity-40 text-on-secondary font-bold text-xs rounded hover:brightness-110 transition-all font-mono"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
};
