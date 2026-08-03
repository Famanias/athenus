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
        className="relative w-20 h-20 sm:w-24 sm:h-24 md:w-28 md:h-28 drop-shadow-lg"
      />

      <h1 className="relative mt-6 sm:mt-8 font-carvist font-bold leading-tight text-[clamp(2.5rem,6vw,4.5rem)] bg-gradient-to-br from-amber-200 via-secondary to-secondary-container bg-clip-text text-transparent">
        {title}
      </h1>

      <p className="relative mt-3 sm:mt-4 text-sm md:text-base text-on-surface-variant/80 tracking-wide">
        {subtitle}
      </p>

      {children && <div className="relative mt-8">{children}</div>}
    </div>
  );
};
