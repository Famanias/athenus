"use client";

import React, { useState } from "react";

export interface Citation {
  chunk_id?: string;
  start_time: number;
  end_time: number;
  text: string;
}

export interface ChatMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  citations?: Citation[];
}

interface ChatInterfaceProps {
  onSeek: (time: number) => void;
  onSendQuery: (query: string) => Promise<{ answer: string; citations: Citation[] }>;
}

export const ChatInterface: React.FC<ChatInterfaceProps> = ({ onSeek, onSendQuery }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "1",
      sender: "assistant",
      text: "Hello! I am your Athenus Learning Assistant. Ask me anything about your uploaded video context.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg: ChatMessage = { id: Date.now().toString(), sender: "user", text: input };
    setMessages((prev) => [...prev, userMsg]);
    const currentQuery = input;
    setInput("");
    setLoading(true);

    try {
      const res = await onSendQuery(currentQuery);
      const assistantMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        sender: "assistant",
        text: res.answer,
        citations: res.citations,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: Date.now().toString(), sender: "assistant", text: "Error executing query. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (sec: number) => {
    const min = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${min.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="h-full flex flex-col bg-slate-900/80 rounded-xl border border-slate-800 shadow-xl backdrop-blur-md overflow-hidden">
      <div className="p-4 border-b border-slate-800 bg-slate-950/40 flex justify-between items-center">
        <h3 className="font-bold text-slate-100 flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-indigo-500"></span>
          Learning Assistant Chat
        </h3>
        <span className="text-xs bg-slate-800 text-slate-400 px-2.5 py-1 rounded-full border border-slate-700">
          Local RAG Engine
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`max-w-[85%] p-3.5 rounded-2xl text-sm leading-relaxed ${
                msg.sender === "user"
                  ? "bg-indigo-600 text-white rounded-br-none shadow-lg shadow-indigo-600/20"
                  : "bg-slate-800/90 text-slate-100 rounded-bl-none border border-slate-700/60"
              }`}
            >
              <p>{msg.text}</p>
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-3 pt-2.5 border-t border-slate-700/50 flex flex-wrap gap-1.5">
                  <span className="text-xs text-slate-400 font-medium block w-full mb-1">Citations:</span>
                  {msg.citations.map((c, i) => (
                    <button
                      key={i}
                      onClick={() => onSeek(c.start_time)}
                      className="text-xs bg-indigo-950/80 hover:bg-indigo-900 border border-indigo-500/40 text-indigo-300 px-2 py-0.5 rounded transition-all font-mono"
                    >
                      ⏱ [{formatTime(c.start_time)} - {formatTime(c.end_time)}]
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-slate-400 text-sm italic">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping"></span>
            Synthesizing response...
          </div>
        )}
      </div>

      <form onSubmit={handleSend} className="p-3 border-t border-slate-800 bg-slate-950/40 flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about this video..."
          className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-100 focus:outline-none focus:border-indigo-500 transition-colors placeholder:text-slate-500"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg font-medium transition-colors"
        >
          Send
        </button>
      </form>
    </div>
  );
};
