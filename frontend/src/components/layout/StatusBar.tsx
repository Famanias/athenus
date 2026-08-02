import React from 'react';

export const StatusBar: React.FC = () => {
  return (
    <footer className="shrink-0 flex justify-between items-center px-4 py-1.5 bg-surface-container-lowest border-t border-outline-variant text-[11px] font-mono text-on-surface-variant w-full">
      <div className="flex items-center gap-3">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        <span className="text-secondary font-semibold">Athenus Local Engine: Active</span>
      </div>
      <div className="flex gap-4">
        <span>Vector Storage: 142 Chunks</span>
        <span>SQLite Metadata: Connected</span>
        <span>Latency: 14ms</span>
      </div>
    </footer>
  );
};
