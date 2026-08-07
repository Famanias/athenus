import { useAppStore } from '@/store/useAppStore';
import { JobLifecycle } from './jobLifecycle';

export function useJob(mediaId: string | null) {
  const { jobs } = useAppStore();
  const job = mediaId ? Object.values(jobs).find((j) => j.media_id === mediaId) : undefined;
  const isComplete = job ? JobLifecycle.isComplete(job.status, job.stage) : false;
  const isActive = job ? JobLifecycle.isActive(job.status) : false;
  return { job, isComplete, isActive };
}
