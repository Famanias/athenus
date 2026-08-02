'use client';

import React, { useRef, useEffect } from 'react';
import { useChat } from './useChat';
import { ChatMessageItem } from './ChatMessageItem';
import { RetrievedEvidencePanel } from './RetrievedEvidencePanel';
import { Button } from '@/components/ui/Button';

export const ChatWorkspace: React.FC = () => {
  const { messages, evidence, agentLogs, inputQuery, setInputQuery, sendMessage, isGenerating } =
    useChat();
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex-1 flex w-full h-full overflow-hidden">
      {/* Main Chat Thread Area */}
      <div className="flex-1 flex flex-col border-r border-outline-variant">
        {/* Chat Workspace Header */}
        <div className="p-4 border-b border-outline-variant bg-surface-container-low flex justify-between items-center shrink-0">
          <div>
            <h2 className="font-bold text-sm text-on-surface flex items-center gap-2">
              <span>🦉</span> AI Research Assistant Chat
            </h2>
            <p className="text-xs text-on-surface-variant/70">
              8-Stage Hybrid Retrieval grounded in active workspace context.
            </p>
          </div>
          <span className="bg-surface-container-high px-2.5 py-1 rounded border border-outline-variant text-[10px] font-mono text-secondary">
            Local LLM: llama3:8b
          </span>
        </div>

        {/* Message Thread List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          {messages.map((msg) => (
            <ChatMessageItem key={msg.id} message={msg} />
          ))}
          <div ref={threadEndRef} />
        </div>

        {/* Query Input Box */}
        <div className="p-4 bg-surface-container-low border-t border-outline-variant flex gap-3 shrink-0">
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isGenerating}
            className="flex-1 bg-surface-container border border-outline-variant rounded px-4 py-2.5 text-xs text-on-surface placeholder:text-on-surface-variant/50 focus:border-secondary focus:outline-none disabled:opacity-50"
            placeholder="Ask Athenus a question or request a concept breakdown..."
          />
          <Button
            variant="primary"
            onClick={() => sendMessage()}
            disabled={isGenerating || !inputQuery.trim()}
          >
            {isGenerating ? 'Thinking...' : 'Ask Athenus'}
          </Button>
        </div>
      </div>

      {/* Right Context Evidence Panel */}
      <RetrievedEvidencePanel evidence={evidence} agentLogs={agentLogs} />
    </div>
  );
};
