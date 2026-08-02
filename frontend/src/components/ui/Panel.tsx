import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
}

export const Panel: React.FC<PanelProps> = ({ title, subtitle, action, children, className, ...props }) => {
  return (
    <div className={twMerge(clsx('flex flex-col bg-background border-r border-outline-variant', className))} {...props}>
      {title && (
        <div className="p-4 border-b border-outline-variant bg-surface-container-low flex justify-between items-center shrink-0">
          <div>
            <h2 className="font-bold text-sm text-on-surface">{title}</h2>
            {subtitle && <p className="text-xs text-on-surface-variant/70 mt-0.5">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      <div className="flex-1 overflow-y-auto custom-scrollbar">{children}</div>
    </div>
  );
};
