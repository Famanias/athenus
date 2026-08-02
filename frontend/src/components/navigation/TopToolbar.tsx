import React from 'react';
import { useAppStore } from '@/store/useAppStore';

export const TopToolbar: React.FC = () => {
  const { setCmdPaletteOpen } = useAppStore();

  return (
    <header className="shrink-0 flex justify-between items-center w-full px-6 h-14 z-50 bg-background border-b border-outline-variant">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 bg-surface-container-high px-3 py-1 rounded border border-outline-variant cursor-pointer">
          <span className="material-symbols-outlined text-secondary text-sm">psychology</span>
          <span className="font-mono text-xs text-on-surface font-semibold">
            Workspace: Machine Learning & Deep Learning
          </span>
          <span className="material-symbols-outlined text-on-surface-variant text-xs">
            expand_more
          </span>
        </div>
      </div>

      {/* Global Search & Command Palette Trigger */}
      <div className="flex-1 max-w-md mx-6">
        <div
          className="relative cursor-pointer"
          onClick={() => setCmdPaletteOpen(true)}
        >
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm">
            search
          </span>
          <input
            type="text"
            readOnly
            className="w-full bg-surface-container-low border border-outline-variant rounded pl-9 pr-12 py-1.5 text-xs text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none pointer-events-none"
            placeholder="Global search across transcripts, concepts, notes..."
          />
          <div className="absolute right-2 top-1/2 -translate-y-1/2 flex gap-1">
            <span className="bg-surface-container-high px-1 py-0.5 rounded border border-outline-variant text-[9px] font-mono text-on-surface-variant">
              CTRL K
            </span>
          </div>
        </div>
      </div>


    </header>
  );
};
