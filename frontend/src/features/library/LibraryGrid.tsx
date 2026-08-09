'use client';

import React from 'react';
import { useLibrary } from './useLibrary';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { useAppStore } from '@/store/useAppStore';

export const LibraryGrid: React.FC = () => {
  const { assets, loading, isOffline } = useLibrary();
  const { setActiveView, setActiveMediaId, setActiveDocumentId, setActiveSourceType } = useAppStore();

  const handleSelectAsset = (id: string, isDoc: boolean) => {
    if (isDoc) {
      setActiveDocumentId(id);
      setActiveSourceType('pdf');
    } else {
      setActiveMediaId(id);
      setActiveSourceType('video');
    }
    setActiveView('view-video');
  };

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar space-y-6">
      {/* Offline Notice */}
      {isOffline && (
        <div className="p-3 bg-amber-950/60 border border-amber-500/40 rounded text-amber-300 text-xs flex justify-between items-center">
          <span>⚠️ Backend service unavailable. Displaying local offline sample workspace.</span>
        </div>
      )}

      {/* Header */}
      <div className="flex justify-between items-end">
        <div>
          <h2 className="font-type-light text-2xl font-bold text-on-surface">
            Knowledge Library & Workspaces
          </h2>
          <p className="text-xs text-on-surface-variant mt-1">
            Manage active workspace media and document assets, transcripts, and vector indexes.
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

      {/* Loading & Empty States */}
      {loading && (
        <div className="p-12 text-center text-xs text-on-surface-variant font-mono">
          Loading workspace assets...
        </div>
      )}

      {!loading && assets.length === 0 && (
        <div className="p-12 border border-dashed border-outline-variant rounded-lg bg-surface-container-low text-center space-y-3">
          <span className="text-4xl block">📚</span>
          <h4 className="font-bold text-sm text-on-surface">No Lecture Videos in Workspace Yet</h4>
          <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
            Upload your first video or audio lecture file to extract transcripts and index vector embeddings.
          </p>
          <Button variant="primary" icon="upload_file" onClick={() => setActiveView('view-ingestion')}>
            Upload First Lecture
          </Button>
        </div>
      )}

      {/* Asset Grid */}
      {!loading && assets.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {assets.map((asset) => {
            // Determine asset modality — document assets use the 📄 icon,
            // video/audio assets use the 🎬 icon.
            const isDocument =
              asset.thumbnailEmoji === '📄' ||
              asset.id.toLowerCase().startsWith('doc_') ||
              asset.id.toLowerCase().includes('pdf') ||
              asset.id.toLowerCase().includes('doc');

            return (
              <Card
                key={asset.id}
                hoverable
                onClick={() => handleSelectAsset(asset.id, isDocument)}
                className="flex flex-col justify-between"
              >
                <div>
                  <div className="flex justify-between items-start mb-3">
                    <span className="text-3xl">{isDocument ? '📄' : '🎬'}</span>
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
                  <span>{isDocument ? '📄 Document' : '🎬 Video'}</span>
                  <span>{asset.wordCount > 0 ? `${asset.wordCount} words` : 'No transcript'}</span>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};
