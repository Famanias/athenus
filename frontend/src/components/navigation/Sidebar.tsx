import React from 'react';
import { NAVIGATION_CONFIG } from '@/config/navigation';
import { SidebarItem } from './SidebarItem';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';

export const Sidebar: React.FC = () => {
  const { setActiveView } = useAppStore();

  return (
    <aside className="fixed left-0 top-0 h-screen flex flex-col z-40 bg-surface-container-low border-r border-outline-variant w-sidebar-width transition-all">
      {/* Brand Header */}
      <div className="p-4 flex items-center justify-between border-b border-outline-variant/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded flex items-center justify-center overflow-hidden shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/icon.png" alt="Athenus" className="w-full h-full object-contain" />
          </div>
          <div>
            <h1 className="font-bold text-lg font-carvist text-on-surface tracking-tight leading-none">
              Athenus
            </h1>
            <span className="text-[10px] font-mono text-secondary uppercase tracking-widest">
              Knowledge OS
            </span>
          </div>
        </div>
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 overflow-y-auto custom-scrollbar py-3 space-y-4">
        {NAVIGATION_CONFIG.map((category) => (
          <div key={category.id}>
            <div className="px-4 py-1 flex items-center justify-between text-[11px] font-mono text-secondary font-semibold uppercase tracking-wider opacity-90">
              <span>{category.title}</span>
            </div>
            <ul className="mt-1 space-y-0.5">
              {category.items.map((item) => (
                <li key={item.id}>
                  <SidebarItem item={item} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {/* Upload Media Quick Trigger */}
      <div className="p-3 border-t border-outline-variant">
        <Button
          variant="secondary"
          size="md"
          icon="upload_file"
          className="w-full"
          onClick={() => setActiveView('view-ingestion')}
        >
          Upload Media File
        </Button>
      </div>
    </aside>
  );
};
