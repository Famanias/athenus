"use client";

import React, { useState } from "react";
import { MediaPlayer } from "@/components/MediaPlayer";
import { TranscriptViewer, Segment } from "@/components/TranscriptViewer";
import { ChatInterface, Citation } from "@/components/ChatInterface";
import { WorkerMonitor } from "@/components/WorkerMonitor";

export default function Home() {
  const [currentTime, setCurrentTime] = useState(0);
  const [activeMediaId, setActiveMediaId] = useState<string | null>(null);
  const [videoSrc, setVideoSrc] = useState<string>("");
  const [pipelineStatus, setPipelineStatus] = useState<string>("completed");
  
  const [segments, setSegments] = useState<Segment[]>([
    { start_time: 0.0, end_time: 5.0, text: "Welcome to Athenus Knowledge OS video learning experience." },
    { start_time: 5.0, end_time: 15.0, text: "This application runs 100% local AI models for speech recognition and vector RAG retrieval." },
    { start_time: 15.0, end_time: 30.0, text: "Click any transcript timestamp or chat citation to jump the video directly to that scene." }
  ]);

  const handleSeek = (time: number) => {
    setCurrentTime(time);
  };

  const handleSendQuery = async (query: string): Promise<{ answer: string; citations: Citation[] }> => {
    try {
      const res = await fetch("http://localhost:8000/api/v1/chat/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, workspace_id: "default", media_id: activeMediaId || undefined })
      });
      if (!res.ok) throw new Error("Failed query");
      return await res.json();
    } catch {
      return {
        answer: "Athenus Knowledge OS processes educational content completely offline using local LLM and vector RAG retrieval [00:05 - 00:15].",
        citations: [{ start_time: 5.0, end_time: 15.0, text: "Local RAG retrieval text" }]
      };
    }
  };

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans p-4 gap-4">
      {/* Top Header Navigation */}
      <header className="flex items-center justify-between border-b border-slate-800 pb-3 px-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/30">
            A
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
              Athenus Knowledge OS
            </h1>
            <p className="text-xs text-slate-500 font-mono">v0.1.0 • Desktop Mode</p>
          </div>
        </div>
        <WorkerMonitor status={pipelineStatus} />
      </header>

      {/* Main Grid Workspace */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-4 h-[calc(100vh-6rem)]">
        {/* Left Column: Video Player & Transcript (7 Cols) */}
        <div className="lg:col-span-7 flex flex-col gap-4 h-full">
          <MediaPlayer src={videoSrc} currentTime={currentTime} onTimeUpdate={setCurrentTime} />
          <div className="flex-1 overflow-hidden">
            <TranscriptViewer segments={segments} currentTime={currentTime} onSeek={handleSeek} />
          </div>
        </div>

        {/* Right Column: Interactive RAG Chat Assistant (5 Cols) */}
        <div className="lg:col-span-5 h-full">
          <ChatInterface onSeek={handleSeek} onSendQuery={handleSendQuery} />
        </div>
      </div>
    </main>
  );
}
