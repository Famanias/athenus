import React from 'react';

interface ContextPanelProps {
  title?: string;
  badge?: string;
  children: React.ReactNode;
}

export const ContextPanel: React.FC<ContextPanelProps> = ({ title = 'Context & Citations', badge, children }) => {
  return (
    <aside className="w-80 bg-surface-container-lowest border-l border-outline-variant flex flex-col shrink-0">
      <div className="p-4 border-b border-outline-variant font-bold text-xs text-on-surface flex justify-between items-center">
        <span>{title}</span>
        {badge && (
          <span className="text-[10px] font-mono text-secondary bg-secondary/10 px-1.5 py-0.5 rounded">
            {badge}
          </span>
        )}
      </div>
      <div className="p-4 overflow-y-auto space-y-4 custom-scrollbar flex-1">
        {children}
      </div>
    </aside>
  );
};
