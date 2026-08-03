import React, { useEffect } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { getWorkspaceSessions, deleteSession } from '@/services/chatService';

export const SessionList: React.FC = () => {
  const activeWorkspaceId = useAppStore((s) => s.activeWorkspaceId);
  const activeSessionId = useAppStore((s) => s.chat.activeSessionId);
  const sessions = useAppStore((s) => s.sessions);
  const setSessions = useAppStore((s) => s.setSessions);
  const switchSession = useAppStore((s) => s.switchSession);
  const initLazyNewChat = useAppStore((s) => s.initLazyNewChat);

  useEffect(() => {
    let isCancelled = false;
    async function loadSessions() {
      if (!activeWorkspaceId) return;
      try {
        const sessionList = await getWorkspaceSessions(activeWorkspaceId);
        if (!isCancelled) {
          setSessions(sessionList);
        }
      } catch {
        // Handle error
      }
    }
    loadSessions();
    return () => {
      isCancelled = true;
    };
  }, [activeWorkspaceId, activeSessionId, setSessions]);

  const [deletingSessionId, setDeletingSessionId] = React.useState<string | null>(null);

  const handleConfirmDeleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation();
    try {
      await deleteSession(sid);
      const updated = sessions.filter((s) => s.id !== sid);
      setSessions(updated);
      if (sid === activeSessionId) {
        if (updated.length > 0) {
          switchSession(updated[0].id);
        } else {
          initLazyNewChat();
        }
      }
    } catch {
      // Delete error
    } finally {
      setDeletingSessionId(null);
    }
  };

  if (sessions.length === 0) {
    return (
      <div className="px-4 py-2 text-[11px] font-mono text-on-surface-variant/60 italic">
        No active chat sessions.
      </div>
    );
  }

  return (
    <div className="px-2 py-1 space-y-0.5">
      <div className="px-2 py-1 flex items-center justify-between text-[10px] font-mono text-secondary font-semibold uppercase tracking-wider">
        <span>Recent Chats ({sessions.length})</span>
      </div>
      <div className="space-y-0.5 max-h-48 overflow-y-auto custom-scrollbar">
        {sessions.map((sess) => {
          const isActive = sess.id === activeSessionId;
          if (deletingSessionId === sess.id) {
            return (
              <div
                key={sess.id}
                className="flex items-center justify-between px-2 py-1 rounded text-xs border border-error/50 bg-error/10 text-on-surface"
              >
                <span className="text-[11px] font-semibold text-error truncate">
                  Delete chat?
                </span>
                <div className="flex items-center gap-1 shrink-0">
                  <button
                    type="button"
                    onClick={(e) => handleConfirmDeleteSession(e, sess.id)}
                    className="px-1.5 py-0.5 bg-error text-on-error font-bold text-[10px] rounded hover:bg-error/80 transition-colors"
                  >
                    Confirm
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeletingSessionId(null);
                    }}
                    className="px-1.5 py-0.5 bg-surface-container text-on-surface-variant font-medium text-[10px] rounded hover:bg-surface-container-high transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            );
          }

          return (
            <div
              key={sess.id}
              onClick={() => switchSession(sess.id)}
              className={`group flex items-center justify-between px-2.5 py-1.5 rounded text-xs cursor-pointer transition-colors ${
                isActive
                  ? 'bg-secondary/15 text-secondary font-semibold border border-secondary/30'
                  : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
              }`}
            >
              <div className="flex items-center gap-2 truncate pr-1">
                <span className="material-symbols-outlined text-xs shrink-0 opacity-75">
                  chat_bubble_outline
                </span>
                <div className="truncate">
                  <div className="truncate text-xs font-medium leading-tight">
                    {sess.title || 'Learning Session'}
                  </div>
                  {sess.preview_text && (
                    <div className="truncate text-[10px] text-on-surface-variant/60 font-normal">
                      {sess.preview_text}
                    </div>
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setDeletingSessionId(sess.id);
                }}
                className="opacity-0 group-hover:opacity-100 p-0.5 text-on-surface-variant hover:text-error rounded hover:bg-surface-container-high transition-opacity"
                title="Delete Chat"
              >
                <span className="material-symbols-outlined text-xs">close</span>
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};
