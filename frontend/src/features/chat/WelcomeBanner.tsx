'use client';

import React from 'react';

interface WelcomeBannerProps {
  iconSrc?: string;
  title?: string;
  subtitle?: string;
  children?: React.ReactNode;
}

export const WelcomeBanner: React.FC<WelcomeBannerProps> = ({
  iconSrc = '/icon.png',
  title = 'Athenus',
  subtitle = 'In Pursuit of Wisdom.',
  children,
}) => {
  return (
    <div className="relative flex flex-col items-center justify-center text-center select-none px-6">
      {/* Soft radial glow behind the icon */}
      <div
        aria-hidden
        className="absolute w-56 h-56 sm:w-64 sm:h-64 rounded-full bg-secondary/15 blur-3xl pointer-events-none"
      />
      <img
        src={iconSrc}
        alt="Athenus"
        className="relative w-32 h-32 sm:w-36 sm:h-36 md:w-40 md:h-40 drop-shadow-lg"
      />
      <h1 className="relative mt-1 sm:mt-2 font-carvist font-bold leading-tight text-[clamp(2.5rem,6vw,4.5rem)] bg-gradient-to-br from-amber-200 via-secondary to-secondary-container bg-clip-text text-transparent">
        {title}
      </h1>
      <p className="relative italic text-sm md:text-base text-on-surface-variant/80 tracking-wide">
        {subtitle}
      </p>

      {children && <div className="relative mt-8">{children}</div>}
    </div>
  );
};
