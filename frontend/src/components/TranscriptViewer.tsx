"use client";

import React from "react";

export interface Segment {
  start_time: number;
  end_time: number;
  text: string;
}

interface TranscriptViewerProps {
  segments: Segment[];
  currentTime: number;
  onSeek: (time: number) => void;
}

export const TranscriptViewer: React.FC<TranscriptViewerProps> = ({ segments, currentTime, onSeek }) => {
  const formatTime = (seconds: number) => {
    const min = Math.floor(seconds / 60);
    const sec = Math.floor(seconds % 60);
    return `${min.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
  };

  return (
    <div className="h-full flex flex-col bg-slate-900/80 rounded-xl border border-slate-800 p-4 shadow-xl backdrop-blur-md">
      <h3 className="text-lg font-bold text-slate-100 mb-3 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
        Interactive Transcript
      </h3>
      <div className="flex-1 overflow-y-auto space-y-2 pr-2 custom-scrollbar">
        {segments.length === 0 ? (
          <p className="text-slate-500 text-sm italic">No transcript segments available.</p>
        ) : (
          segments.map((seg, idx) => {
            const isActive = currentTime >= seg.start_time && currentTime <= seg.end_time;
            return (
              <div
                key={idx}
                onClick={() => onSeek(seg.start_time)}
                className={`p-2.5 rounded-lg transition-all cursor-pointer text-sm flex gap-3 ${
                  isActive
                    ? "bg-indigo-600/30 border border-indigo-500/50 text-indigo-100 font-medium"
                    : "hover:bg-slate-800/60 text-slate-300"
                }`}
              >
                <span className="text-xs font-mono text-indigo-400 shrink-0 pt-0.5">
                  [{formatTime(seg.start_time)}]
                </span>
                <p className="leading-relaxed">{seg.text}</p>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
