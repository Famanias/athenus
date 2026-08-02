import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({ children, hoverable = false, className, ...props }) => {
  return (
    <div
      className={twMerge(
        clsx(
          'p-4 bg-surface-container-low border border-outline-variant rounded-md transition-all duration-200',
          hoverable && 'hover:border-secondary hover:shadow-lg cursor-pointer',
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  );
};
