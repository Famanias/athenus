import React from 'react';

export const StatusBar: React.FC = () => {
  return (
    <footer className="fixed bottom-0 left-0 w-full flex justify-between items-center px-4 py-1.5 z-50 bg-surface-container-lowest border-t border-outline-variant text-[11px] font-mono text-on-surface-variant">
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
