import React from 'react';
import { NAVIGATION_CONFIG } from '@/config/navigation';
import { SidebarItem } from './SidebarItem';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';
import { SessionList } from './SessionList';

export const Sidebar: React.FC = () => {
  const { initLazyNewChat, setWorkspaceModalOpen, isSidebarCollapsed, toggleSidebar } = useAppStore();

  return (
    <aside
      className={`fixed left-0 top-0 h-screen flex flex-col z-40 bg-surface-container-low border-r border-outline-variant transition-all duration-200 ${
        isSidebarCollapsed ? 'w-16' : 'w-sidebar-width'
      }`}
    >
      {/* Brand Header */}
      <div
        className={`p-4 flex border-b border-outline-variant/50 ${
          isSidebarCollapsed ? 'flex-col items-center gap-3' : 'items-center justify-between'
        }`}
      >
        <div className={`min-w-0 ${isSidebarCollapsed ? '' : 'flex items-center gap-3'}`}>
          <div className="w-8 h-8 rounded flex items-center justify-center overflow-hidden shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/icon.png" alt="Athenus" className="w-full h-full object-contain" />
          </div>
          {!isSidebarCollapsed && (
            <h1 className="font-bold text-4xl font-carvist tracking-tight leading-none bg-gradient-to-br from-amber-200 via-secondary to-secondary-container bg-clip-text text-transparent">
              Athenus
            </h1>
          )}
        </div>
        <button
          type="button"
          onClick={toggleSidebar}
          aria-label={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!isSidebarCollapsed}
          title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="w-8 h-8 rounded flex items-center justify-center text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary/70"
        >
          <span className="material-symbols-outlined text-[20px]" aria-hidden="true">
            {isSidebarCollapsed ? 'chevron_right' : 'chevron_left'}
          </span>
        </button>
      </div>

      {/* Quick "+ New Chat" Action */}
      <div
        className={`p-3 border-b border-outline-variant/50 ${
          isSidebarCollapsed ? 'flex flex-col items-center gap-2' : 'flex gap-2'
        }`}
      >
        {isSidebarCollapsed ? (
          <>
            <button
              type="button"
              onClick={initLazyNewChat}
              aria-label="New Chat"
              title="New Chat"
              className="w-9 h-9 rounded flex items-center justify-center bg-secondary text-on-secondary hover:brightness-110 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary/70"
            >
              <span className="material-symbols-outlined text-[18px]" aria-hidden="true">add</span>
            </button>
            <button
              type="button"
              onClick={() => setWorkspaceModalOpen(true)}
              aria-label="Create New Workspace"
              title="Create New Workspace"
              className="w-9 h-9 rounded flex items-center justify-center bg-surface-container hover:bg-surface-container-high border border-outline-variant text-on-surface-variant hover:text-on-surface transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary/70"
            >
              <span className="material-symbols-outlined text-sm" aria-hidden="true">add_box</span>
            </button>
          </>
        ) : (
          <>
            <Button
              variant="primary"
              size="md"
              icon="add"
              className="flex-1"
              onClick={initLazyNewChat}
            >
              New Chat
            </Button>
            <button
              type="button"
              onClick={() => setWorkspaceModalOpen(true)}
              className="px-2 py-1 bg-surface-container hover:bg-surface-container-high border border-outline-variant rounded text-on-surface-variant hover:text-on-surface transition-colors shrink-0"
              title="Create New Workspace"
            >
              <span className="material-symbols-outlined text-sm">add_box</span>
            </button>
          </>
        )}
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 overflow-y-auto custom-scrollbar py-3 space-y-4">
        {NAVIGATION_CONFIG.map((category) => (
          <div key={category.id}>
            {!isSidebarCollapsed && (
              <div className="px-4 py-1 flex items-center justify-between text-[11px] font-mono text-secondary font-semibold uppercase tracking-wider opacity-90">
                <span>{category.title}</span>
              </div>
            )}
            <ul className={`space-y-0.5 ${isSidebarCollapsed ? '' : 'mt-1'}`}>
              {category.items.map((item) => (
                <li key={item.id}>
                  <SidebarItem item={item} collapsed={isSidebarCollapsed} />
                </li>
              ))}
            </ul>
          </div>
        ))}

        {/* Sessions List within active workspace */}
        {!isSidebarCollapsed && <SessionList />}
      </nav>
    </aside>
  );
};
