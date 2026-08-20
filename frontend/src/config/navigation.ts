export interface NavItem {
  id: string;
  label: string;
  icon: string;
  badge?: string;
  badgeType?: 'active' | 'soon';
}

export interface NavCategory {
  id: string;
  title: string;
  icon?: string;
  items: NavItem[];
}

export const NAVIGATION_CONFIG: NavCategory[] = [
  {
    id: 'wisdom',
    title: 'Wisdom',
    items: [
      { id: 'view-chat', label: 'Chat', icon: 'forum', badge: 'Active', badgeType: 'active' },
    ],
  },
  {
    id: 'knowledge',
    title: 'Knowledge',
    items: [
      { id: 'view-dashboard', label: 'Library', icon: 'library_books' },
      { id: 'view-video', label: 'Learning', icon: 'school', badge: 'Active', badgeType: 'active' },
      { id: 'view-notes', label: 'Notes', icon: 'auto_stories', badge: 'Active', badgeType: 'active' },
      { id: 'view-graph', label: 'Blueprint', icon: 'hub', badge: 'Active', badgeType: 'active' },
    ],
  },
  {
    id: 'strategy',
    title: 'Strategy',
    items: [
      { id: 'view-flashcards', label: 'Flashcards', icon: 'layers', badge: 'Active', badgeType: 'active' },
      { id: 'view-quiz', label: 'Quizzes', icon: 'quiz', badge: 'Active', badgeType: 'active' },
      { id: 'view-analytics', label: 'Analytics', icon: 'analytics', badge: 'Active', badgeType: 'active' },
    ],
  },
  {
    id: 'infrastructure',
    title: 'Infrastructure',
    items: [
      { id: 'view-ingestion', label: 'Uploads', icon: 'upload', badge: 'Active', badgeType: 'active' },
      { id: 'view-settings', label: 'Settings', icon: 'settings' },
    ],
  },
];
