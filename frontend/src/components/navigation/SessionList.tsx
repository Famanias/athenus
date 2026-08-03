import React, { useEffect } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { getWorkspaceSessions, deleteSession } from '@/services/chatService';

export const SessionList: React.FC = () => {
  const {
    activeWorkspaceId,
    sessions,
    setSessions,
    context,
    switchSession,
    initLazyNewChat,
  } = useAppStore();

  const activeSessionId = context.sessionId;

  useEffect(() => {
    async function loadSessions() {
      if (!activeWorkspaceId) return;
      try {
        const sessionList = await getWorkspaceSessions(activeWorkspaceId);
        setSessions(sessionList);
      } catch {
        // Handle error
      }
    }
    loadSessions();
  }, [activeWorkspaceId, setSessions]);

  const handleDeleteSession = async (e: React.MouseEvent, sid: string) => {
    e.stopPropagation();
    let confirmed = true;
    try {
      if (typeof window !== 'undefined' && window.confirm) {
        confirmed = window.confirm('Delete this chat session history?');
      }
    } catch {
      confirmed = true;
    }

    if (confirmed) {
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
      }
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
                onClick={(e) => handleDeleteSession(e, sess.id)}
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
