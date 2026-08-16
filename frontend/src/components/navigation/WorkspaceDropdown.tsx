import React, { useState, useEffect, useRef } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { getWorkspaces, getActiveWorkspace, activateWorkspace } from '@/services/libraryService';

export const WorkspaceDropdown: React.FC = () => {
  const {
    workspaces,
    setWorkspaces,
    activeWorkspaceId,
    switchWorkspace,
    setWorkspaceModalOpen,
  } = useAppStore();

  const [isOpen, setIsOpen] = useState(false);
  const [filterQuery, setFilterQuery] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Load workspaces and active workspace context on mount
  useEffect(() => {
    async function loadWorkspaces() {
      try {
        const [wsList, actCtx] = await Promise.all([getWorkspaces(), getActiveWorkspace()]);
        if (wsList && wsList.length > 0) {
          setWorkspaces(wsList);
          const targetId = actCtx?.active_workspace_id || wsList[0].id;
          switchWorkspace(targetId);
        }
      } catch {
        // Handle error gracefully
      }
    }
    loadWorkspaces();
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const activeWs = workspaces.find((w) => w.id === activeWorkspaceId) || workspaces[0];

  const handleSelectWorkspace = async (id: string) => {
    setIsOpen(false);
    setFilterQuery('');
    if (id !== activeWorkspaceId) {
      switchWorkspace(id);
      try {
        await activateWorkspace(id);
      } catch {
        // Activate error
      }
    }
  };

  const filteredWorkspaces = workspaces.filter((w) =>
    w.name.toLowerCase().includes(filterQuery.toLowerCase())
  );

  const pinnedWorkspaces = filteredWorkspaces.filter((w) => w.is_pinned);
  const unpinnedWorkspaces = filteredWorkspaces.filter((w) => !w.is_pinned);

  return (
    <div className="relative inline-block max-w-sm sm:max-w-md md:max-w-lg" ref={dropdownRef}>
      {/* Active Workspace Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        title={activeWs ? activeWs.name : 'Select Workspace'}
        className="flex items-center gap-2.5 bg-surface-container/70 hover:bg-surface-container border border-outline-variant hover:border-secondary/40 px-3 py-1.5 rounded-lg transition-all cursor-pointer text-left group max-w-full"
      >
        <div className="w-6 h-6 rounded-md bg-secondary/15 flex items-center justify-center shrink-0 border border-secondary/30">
          <span className="material-symbols-outlined text-secondary text-sm">
            {activeWs?.icon || 'psychology'}
          </span>
        </div>
        <span className="font-semibold text-xs sm:text-sm text-on-surface truncate min-w-0 pr-1">
          {activeWs ? activeWs.name : 'Select Workspace'}
        </span>
        <span className="material-symbols-outlined text-on-surface-variant text-sm transition-transform duration-200 shrink-0 group-hover:text-on-surface ml-0.5">
          {isOpen ? 'expand_less' : 'expand_more'}
        </span>
      </button>

      {/* Dropdown Menu Overlay */}
      {isOpen && (
        <div className="absolute left-0 top-full mt-2 w-80 max-w-[calc(100vw-2rem)] bg-surface-container-high border border-outline-variant rounded-xl shadow-2xl z-50 overflow-hidden flex flex-col backdrop-blur-md">
          {/* Search Filter */}
          <div className="p-2.5 border-b border-outline-variant bg-surface-container-low">
            <div className="relative">
              <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant text-xs">
                search
              </span>
              <input
                type="text"
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                placeholder="Search workspaces..."
                className="w-full bg-surface-container border border-outline-variant rounded-lg pl-8 pr-3 py-1.5 text-xs text-on-surface placeholder:text-on-surface-variant/50 focus:outline-none focus:border-secondary"
              />
            </div>
          </div>

          {/* Workspaces List */}
          <div className="max-h-64 overflow-y-auto custom-scrollbar p-1.5 space-y-1">
            {pinnedWorkspaces.length > 0 && (
              <div>
                <div className="px-2 py-1 text-[10px] font-mono text-secondary uppercase font-semibold">
                  Pinned Workspaces
                </div>
                {pinnedWorkspaces.map((ws) => (
                  <button
                    key={ws.id}
                    type="button"
                    title={ws.name}
                    onClick={() => handleSelectWorkspace(ws.id)}
                    className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition-colors text-left ${
                      ws.id === activeWorkspaceId
                        ? 'bg-secondary/15 text-secondary font-semibold border border-secondary/30'
                        : 'text-on-surface hover:bg-surface-container'
                    }`}
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className="material-symbols-outlined text-xs shrink-0 text-secondary">
                        {ws.icon || 'psychology'}
                      </span>
                      <span className="truncate">{ws.name}</span>
                    </div>
                    {ws.id === activeWorkspaceId && (
                      <span className="material-symbols-outlined text-xs text-secondary shrink-0">
                        check
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}

            {unpinnedWorkspaces.length > 0 && (
              <div>
                {pinnedWorkspaces.length > 0 && (
                  <div className="px-2 py-1 text-[10px] font-mono text-secondary uppercase font-semibold">
                    All Workspaces
                  </div>
                )}
                {unpinnedWorkspaces.map((ws) => (
                  <button
                    key={ws.id}
                    type="button"
                    title={ws.name}
                    onClick={() => handleSelectWorkspace(ws.id)}
                    className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs transition-colors text-left ${
                      ws.id === activeWorkspaceId
                        ? 'bg-secondary/15 text-secondary font-semibold border border-secondary/30'
                        : 'text-on-surface hover:bg-surface-container'
                    }`}
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className="material-symbols-outlined text-xs shrink-0 text-on-surface-variant">
                        {ws.icon || 'psychology'}
                      </span>
                      <span className="truncate">{ws.name}</span>
                    </div>
                    {ws.id === activeWorkspaceId && (
                      <span className="material-symbols-outlined text-xs text-secondary shrink-0">
                        check
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}

            {filteredWorkspaces.length === 0 && (
              <div className="p-3 text-center text-xs text-on-surface-variant">
                No workspaces match &quot;{filterQuery}&quot;
              </div>
            )}
          </div>

          {/* Quick Create Action Footer */}
          <div className="p-2 border-t border-outline-variant bg-surface-container-low flex justify-between items-center">
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                setWorkspaceModalOpen(true);
              }}
              className="w-full flex items-center justify-center gap-1.5 text-xs text-secondary hover:text-on-surface font-mono py-1.5 rounded-lg hover:bg-surface-container transition-colors"
            >
              <span className="material-symbols-outlined text-xs">add_box</span>
              <span>Create / Manage Workspaces</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
