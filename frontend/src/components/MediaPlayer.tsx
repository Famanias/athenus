"use client";

import React, { useRef, useEffect } from "react";

interface MediaPlayerProps {
  src: string;
  currentTime: number;
  onTimeUpdate?: (time: number) => void;
}

export const MediaPlayer: React.FC<MediaPlayerProps> = ({ src, currentTime, onTimeUpdate }) => {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (videoRef.current && Math.abs(videoRef.current.currentTime - currentTime) > 1.0) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime]);

  return (
    <div className="relative w-full aspect-video bg-black rounded-xl overflow-hidden shadow-2xl border border-slate-800">
      <video
        ref={videoRef}
        src={src}
        controls
        className="w-full h-full object-contain"
        onTimeUpdate={(e) => onTimeUpdate && onTimeUpdate(e.currentTarget.currentTime)}
      />
    </div>
  );
};
