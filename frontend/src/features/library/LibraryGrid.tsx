'use client';

import React from 'react';
import { useLibrary } from './useLibrary';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { useAppStore } from '@/store/useAppStore';

export const LibraryGrid: React.FC = () => {
  const { assets } = useLibrary();
  const { setActiveView, setActiveMediaId } = useAppStore();

  const handleSelectAsset = (id: string) => {
    setActiveMediaId(id);
    setActiveView('view-video');
  };

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar space-y-6">
      {/* Header */}
      <div className="flex justify-between items-end">
        <div>
          <h2 className="font-carvist text-2xl font-bold text-on-surface">
            Knowledge Library & Workspaces
          </h2>
          <p className="text-xs text-on-surface-variant mt-1">
            Manage active workspace video assets, transcripts, and vector indexes.
          </p>
        </div>
        <Button
          variant="primary"
          icon="upload_file"
          onClick={() => setActiveView('view-ingestion')}
        >
          Upload Asset
        </Button>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {assets.map((asset) => (
          <Card
            key={asset.id}
            hoverable
            onClick={() => handleSelectAsset(asset.id)}
            className="flex flex-col justify-between"
          >
            <div>
              <div className="flex justify-between items-start mb-3">
                <span className="text-3xl">{asset.thumbnailEmoji}</span>
                <Badge variant="active">{asset.masteryScore}% Mastered</Badge>
              </div>
              <h4 className="font-bold text-sm text-on-surface mb-1 line-clamp-2">
                {asset.title}
              </h4>
              <p className="text-xs text-on-surface-variant line-clamp-2 leading-relaxed">
                {asset.description}
              </p>
            </div>

            <div className="mt-6 pt-3 border-t border-outline-variant/40 text-[11px] font-mono text-on-surface-variant/60 flex justify-between items-center">
              <span>⏱ {asset.duration}</span>
              <span>📄 {asset.wordCount} words</span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};
