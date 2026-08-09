export interface WorkspaceContext {
  workspaceId: string;
  sessionId: string | null;
  mediaId: string | null;
  documentId?: string | null;
  sourceType?: 'video' | 'pdf';
  currentPage?: number | null;
}
