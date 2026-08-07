export const JobLifecycle = {
  isActive: (status: string) => ['queued', 'pending', 'processing'].includes(status),
  isComplete: (status: string, stage?: string) =>
    status === 'completed' || stage === 'ready' || stage === 'completed',
  isFailed: (status: string, stage?: string) =>
    status === 'failed' || stage === 'failed',
};
