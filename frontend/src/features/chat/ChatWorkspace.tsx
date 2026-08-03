'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useChat } from './useChat';
import { ChatMessageItem } from './ChatMessageItem';
import { RetrievedEvidencePanel } from './RetrievedEvidencePanel';
import { Button } from '@/components/ui/Button';

export const ChatWorkspace: React.FC = () => {
  const { messages, evidence, agentLogs, inputQuery, setInputQuery, sendMessage, isGenerating, clearConversation } =
    useChat();
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  // Active focused assistant message for inspection in RetrievedEvidencePanel
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);

  // Auto-scroll to bottom on new message and update selectedMessageId to latest assistant response
  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    const lastAsst = messages.filter((m) => m.sender === 'assistant').pop();
    if (lastAsst) {
      setSelectedMessageId(lastAsst.id);
    }
  }, [messages]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Determine active evidence to display in RetrievedEvidencePanel:
  // 1. If a message is selected, use its citations (if any).
  // 2. Otherwise, fall back to global state evidence or empty array.
  const selectedMessage = messages.find((m) => m.id === selectedMessageId && m.sender === 'assistant');
  const activeEvidence = selectedMessage
    ? (selectedMessage.citations || [])
    : evidence;

  return (
    <div className="flex-1 flex w-full h-full overflow-hidden">
      {/* Main Chat Thread Area */}
      <div className="flex-1 flex flex-col border-r border-outline-variant">
        {/* Chat Workspace Header */}
        <div className="p-4 border-b border-outline-variant bg-surface-container-low flex justify-between items-center shrink-0">
          <div>
            <h1 className="font-bold text-md text-on-surface flex items-center gap-2">
              Athenus Chat
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <span className="bg-surface-container-high px-2.5 py-1 rounded border border-outline-variant text-[10px] font-mono text-secondary">
              Local LLM: llama3:8b
            </span>
            <Button
              variant="secondary"
              size="sm"
              icon="delete"
              onClick={() => {
                clearConversation();
                setSelectedMessageId(null);
              }}
              disabled={isGenerating}
            >
              Clear Chat
            </Button>
          </div>
        </div>

        {/* Message Thread List */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          {messages.map((msg) => (
            <ChatMessageItem
              key={msg.id}
              message={msg}
              isSelected={msg.id === selectedMessageId}
              onSelectMessage={(id) => setSelectedMessageId(id)}
            />
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

      {/* Right Context Evidence Panel (binds to active assistant message evidence) */}
      <RetrievedEvidencePanel evidence={activeEvidence} agentLogs={agentLogs} />
    </div>
  );
};
