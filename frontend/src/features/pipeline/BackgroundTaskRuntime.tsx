'use client';

import React, { useEffect, useRef } from 'react';
import { useAppStore, BackgroundJob } from '@/store/useAppStore';
import { createMediaProcessingStream } from '@/services/mediaService';
import { apiClient } from '@/services/apiClient';

// Valid pipeline stage transitions
const VALID_STAGES = [
  'uploaded',
  'audio_extraction',
  'transcription',
  'chunking',
  'vector_indexing',
  'graph_extraction',
  'completed',
  'failed',
] as const;

import { JobLifecycle } from './jobLifecycle';

export const BackgroundTaskRuntime: React.FC = () => {
  const { jobs, upsertJob, setJobHistory } = useAppStore();

  // Stream ref registry tracking active EventSource streams by media_id
  const activeStreamsRef = useRef<Record<string, EventSource>>({});
  // Polling interval registry
  const activePollersRef = useRef<Record<string, NodeJS.Timeout>>({});
  // Retry counters for exponential backoff
  const retryCountsRef = useRef<Record<string, number>>({});

  const activeJobEntries = Object.values(jobs).filter(
    (j) => JobLifecycle.isActive(j.status)
  );

  useEffect(() => {
    activeJobEntries.forEach((job) => {
      const mediaId = job.media_id;

      // 1. Initial history rehydration if history is not yet loaded
      if (!job.history || job.history.length === 0) {
        apiClient<Array<any>>(`/api/v1/media/${encodeURIComponent(mediaId)}/history`)
          .then((logs) => {
            if (Array.isArray(logs) && logs.length > 0) {
              const mapped = logs.map((l) => ({
                stage: l.stage,
                progress: l.progress,
                status: l.status,
                timestamp: l.timestamp,
              }));
              setJobHistory(job.job_id, mapped);
            }
          })
          .catch(() => {});
      }

      // 2. Open SSE Stream if not already listening
      if (!activeStreamsRef.current[mediaId]) {
        try {
          const stream = createMediaProcessingStream(mediaId);
          activeStreamsRef.current[mediaId] = stream;

          stream.onmessage = (event) => {
            try {
              const payload = JSON.parse(event.data);
              const { current_stage, overall_progress, status, message, error } = payload;

              // Validate stage
              const validStage = VALID_STAGES.includes(current_stage) ? current_stage : job.stage;

              if (status === 'failed') {
                upsertJob({
                  ...job,
                  status: 'failed',
                  stage: 'failed',
                  error: error || message || 'Processing failed.',
                  updatedAt: new Date().toISOString(),
                });
                cleanupJobResources(mediaId);
                return;
              }

              if (status === 'completed' || current_stage === 'completed') {
                upsertJob({
                  ...job,
                  status: 'completed',
                  stage: 'completed',
                  progress: 100,
                  message: 'Ingestion completed successfully.',
                  updatedAt: new Date().toISOString(),
                });
                cleanupJobResources(mediaId);

                if (typeof window !== 'undefined') {
                  window.dispatchEvent(
                    new CustomEvent('athenus:transcript-ready', { detail: { mediaId } })
                  );
                }
                return;
              }

              // In-flight progress update
              upsertJob({
                ...job,
                status: 'processing',
                stage: validStage,
                progress: typeof overall_progress === 'number' ? overall_progress : job.progress,
                message: message || job.message,
                updatedAt: new Date().toISOString(),
              });

              // Reset backoff on successful message
              retryCountsRef.current[mediaId] = 0;
            } catch (_e) {
              // Ignore heartbeat parse frames
            }
          };

          stream.onerror = () => {
            console.warn(`[BackgroundTaskRuntime] SSE stream interrupted for media: ${mediaId}. Initiating recovery.`);
            stream.close();
            delete activeStreamsRef.current[mediaId];

            // Exponential backoff reconnect logic (2s -> 5s -> 10s)
            const currentRetries = (retryCountsRef.current[mediaId] || 0) + 1;
            retryCountsRef.current[mediaId] = currentRetries;
            const backoffMs = Math.min(2000 * Math.pow(2, currentRetries - 1), 10000);

            // Start HTTP fallback polling while waiting for reconnection
            startFallbackPolling(job);

            setTimeout(() => {
              // Trigger state refresh to attempt reconnect
              upsertJob({ ...job, updatedAt: new Date().toISOString() });
            }, backoffMs);
          };
        } catch (_err) {
          startFallbackPolling(job);
        }
      }
    });
  }, [activeJobEntries.map((j) => `${j.job_id}:${j.updatedAt}`).join(',')]);

  const startFallbackPolling = (job: BackgroundJob) => {
    const mediaId = job.media_id;
    if (activePollersRef.current[mediaId]) return;

    activePollersRef.current[mediaId] = setInterval(async () => {
      try {
        const statusRes = await apiClient<{
          media_id: string;
          status: string;
          overall_progress: number;
          message: string;
          error_message?: string;
        }>(`/api/v1/media/${encodeURIComponent(mediaId)}/status`);

        if (statusRes) {
          if (statusRes.status === 'completed') {
            upsertJob({
              ...job,
              status: 'completed',
              stage: 'completed',
              progress: 100,
              message: 'Processing completed via polling recovery.',
              updatedAt: new Date().toISOString(),
            });
            cleanupJobResources(mediaId);

            if (typeof window !== 'undefined') {
              window.dispatchEvent(
                new CustomEvent('athenus:transcript-ready', { detail: { mediaId } })
              );
            }
          } else if (statusRes.status === 'failed') {
            upsertJob({
              ...job,
              status: 'failed',
              stage: 'failed',
              error: statusRes.error_message || 'Processing failed.',
              updatedAt: new Date().toISOString(),
            });
            cleanupJobResources(mediaId);
          } else {
            upsertJob({
              ...job,
              status: 'processing',
              progress: statusRes.overall_progress || job.progress,
              message: statusRes.message || job.message,
              updatedAt: new Date().toISOString(),
            });
          }
        }
      } catch (_err) {
        // Polling silent retry
      }
    }, 5000);
  };

  const cleanupJobResources = (mediaId: string) => {
    if (activeStreamsRef.current[mediaId]) {
      activeStreamsRef.current[mediaId].close();
      delete activeStreamsRef.current[mediaId];
    }
    if (activePollersRef.current[mediaId]) {
      clearInterval(activePollersRef.current[mediaId]);
      delete activePollersRef.current[mediaId];
    }
    delete retryCountsRef.current[mediaId];
  };

  // Pure background worker runtime — renders no UI nodes
  return null;
};
