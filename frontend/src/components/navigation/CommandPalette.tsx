import React, { useEffect } from 'react';
import { useAppStore } from '@/store/useAppStore';

export const CommandPalette: React.FC = () => {
  const { isCmdPaletteOpen, setCmdPaletteOpen, setActiveView } = useAppStore();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCmdPaletteOpen(!isCmdPaletteOpen);
      }
      if (e.key === 'Escape') {
        setCmdPaletteOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isCmdPaletteOpen, setCmdPaletteOpen]);

  if (!isCmdPaletteOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-start justify-center pt-24"
      onClick={() => setCmdPaletteOpen(false)}
    >
      <div
        className="w-[540px] bg-surface-container-low border border-outline-variant rounded-lg shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-4 border-b border-outline-variant flex items-center gap-3">
          <span className="material-symbols-outlined text-on-surface-variant">search</span>
          <input
            type="text"
            autoFocus
            className="flex-1 bg-transparent text-xs text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none"
            placeholder="Search knowledge base or jump to tab..."
          />
          <span className="text-[10px] font-mono text-on-surface-variant/50">ESC</span>
        </div>
        <div className="p-2 space-y-1 text-xs">
          <div
            className="p-2.5 rounded hover:bg-surface-container-high cursor-pointer flex justify-between items-center"
            onClick={() => {
              setActiveView('view-chat');
              setCmdPaletteOpen(false);
            }}
          >
            <span>💬 AI Research Assistant</span>
            <span className="font-mono text-[10px] text-secondary">Wisdom</span>
          </div>
          <div
            className="p-2.5 rounded hover:bg-surface-container-high cursor-pointer flex justify-between items-center"
            onClick={() => {
              setActiveView('view-video');
              setCmdPaletteOpen(false);
            }}
          >
            <span>📹 Video Learning Workspace</span>
            <span className="font-mono text-[10px] text-secondary">Knowledge</span>
          </div>
          <div
            className="p-2.5 rounded hover:bg-surface-container-high cursor-pointer flex justify-between items-center"
            onClick={() => {
              setActiveView('view-flashcards');
              setCmdPaletteOpen(false);
            }}
          >
            <span>🎴 Active Recall Flashcards</span>
            <span className="font-mono text-[10px] text-secondary">Strategy</span>
          </div>
        </div>
      </div>
    </div>
  );
};
