"use client";

import React from "react";

interface WorkerMonitorProps {
  status: string;
  progressPercent?: number;
}

export const WorkerMonitor: React.FC<WorkerMonitorProps> = ({ status, progressPercent = 100 }) => {
  const getStatusBadge = () => {
    switch (status.toLowerCase()) {
      case "completed":
        return <span className="text-emerald-400 font-semibold">● Ready</span>;
      case "transcribing":
      case "extracting_audio":
      case "indexing":
        return <span className="text-amber-400 font-semibold animate-pulse">⚙ Processing ({status})</span>;
      case "failed":
        return <span className="text-rose-400 font-semibold">✖ Failed</span>;
      default:
        return <span className="text-slate-400">⏳ Idle</span>;
    }
  };

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-lg p-3 flex items-center justify-between text-xs text-slate-300 shadow-md">
      <div className="flex items-center gap-2">
        <span className="font-mono text-slate-400">Pipeline Status:</span>
        {getStatusBadge()}
      </div>
      <div className="flex items-center gap-2">
        <span className="font-mono text-slate-500">Resource Profile:</span>
        <span className="bg-indigo-950 text-indigo-300 border border-indigo-500/30 px-2 py-0.5 rounded font-mono">
          Local CPU/GPU
        </span>
      </div>
    </div>
  );
};
