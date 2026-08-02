import React from 'react';

interface MainPanelProps {
  children: React.ReactNode;
}

export const MainPanel: React.FC<MainPanelProps> = ({ children }) => {
  return (
    <div className="flex-1 min-h-0 flex overflow-auto relative bg-background">
      {children}
    </div>
  );
};
