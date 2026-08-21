import React from 'react';
import { NavItem } from '@/config/navigation';
import { Badge } from '@/components/ui/Badge';
import { useAppStore } from '@/store/useAppStore';

interface SidebarItemProps {
  item: NavItem;
  collapsed?: boolean;
}

export const SidebarItem: React.FC<SidebarItemProps> = ({ item, collapsed = false }) => {
  const { activeView, setActiveView } = useAppStore();
  const isActive = activeView === item.id;

  return (
    <button
      onClick={() => setActiveView(item.id)}
      title={collapsed ? item.label : undefined}
      aria-label={collapsed ? item.label : undefined}
      className={`flex items-center w-full py-2.5 text-xs transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary/70 ${
        collapsed ? 'justify-center' : 'gap-3 px-4'
      } ${
        isActive
          ? 'text-secondary border-l-2 border-secondary bg-surface-container-high font-semibold'
          : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
      }`}
    >
      <span className="material-symbols-outlined text-[18px]">{item.icon}</span>
      {!collapsed && <span className="truncate">{item.label}</span>}
      {!collapsed && item.badge && (
        <Badge variant={item.badgeType} className="ml-auto shrink-0">
          {item.badge}
        </Badge>
      )}
    </button>
  );
};
