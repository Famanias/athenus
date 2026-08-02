import React from 'react';

interface MainPanelProps {
  children: React.ReactNode;
}

export const MainPanel: React.FC<MainPanelProps> = ({ children }) => {
  return (
    <div className="flex-1 flex overflow-hidden relative bg-background">
      {children}
    </div>
  );
};
