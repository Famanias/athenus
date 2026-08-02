import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'active' | 'soon' | 'secondary' | 'neutral';
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({ children, variant = 'neutral', className }) => {
  const base = 'px-2 py-0.5 rounded text-[10px] font-mono border font-semibold';
  
  const variants = {
    active: 'bg-emerald-950/60 text-emerald-400 border-emerald-500/40',
    soon: 'bg-surface-container-highest text-on-surface-variant/60 border-outline-variant',
    secondary: 'bg-secondary/15 text-secondary border-secondary/40',
    neutral: 'bg-surface-container-high text-on-surface-variant border-outline-variant',
  };

  return (
    <span className={twMerge(clsx(base, variants[variant], className))}>
      {children}
    </span>
  );
};
