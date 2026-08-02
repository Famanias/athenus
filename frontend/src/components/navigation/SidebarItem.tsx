import React from 'react';
import { NavItem } from '@/config/navigation';
import { Badge } from '@/components/ui/Badge';
import { useAppStore } from '@/store/useAppStore';

interface SidebarItemProps {
  item: NavItem;
}

export const SidebarItem: React.FC<SidebarItemProps> = ({ item }) => {
  const { activeView, setActiveView } = useAppStore();
  const isActive = activeView === item.id;

  return (
    <button
      onClick={() => setActiveView(item.id)}
      className={`flex items-center gap-3 w-full px-4 py-2.5 text-xs transition-all duration-150 ${
        isActive
          ? 'text-secondary border-l-2 border-secondary bg-surface-container-high font-semibold'
          : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
      }`}
    >
      <span className="material-symbols-outlined text-[18px]">{item.icon}</span>
      <span className="truncate">{item.label}</span>
      {item.badge && (
        <Badge variant={item.badgeType} className="ml-auto shrink-0">
          {item.badge}
        </Badge>
      )}
    </button>
  );
};
