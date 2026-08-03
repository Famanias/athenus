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
      { id: 'view-ask', label: 'Ask & Explain Concepts', icon: 'psychology' },
      { id: 'view-insights', label: 'AI Synthesis Insights', icon: 'auto_awesome' },
    ],
  },
  {
    id: 'knowledge',
    title: 'Knowledge',
    items: [
      { id: 'view-dashboard', label: 'Workspace Library', icon: 'grid_view' },
      { id: 'view-video', label: 'Video', icon: 'smart_display', badge: 'Active', badgeType: 'active' },
      { id: 'view-graph', label: 'Blueprint', icon: 'hub', badge: 'v0.3', badgeType: 'soon' },
    ],
  },
  {
    id: 'strategy',
    title: 'Strategy',
    items: [
      { id: 'view-flashcards', label: 'Flashcards', icon: 'layers', badge: 'v0.4', badgeType: 'soon' },
      { id: 'view-quiz', label: 'Quizzes', icon: 'quiz', badge: 'v0.4', badgeType: 'soon' },
      { id: 'view-analytics', label: 'Analytics', icon: 'analytics' },
    ],
  },
  {
    id: 'infrastructure',
    title: 'Infrastructure',
    items: [
      { id: 'view-ingestion', label: 'Pipelines', icon: 'database', badge: 'Active', badgeType: 'active' },
      { id: 'view-settings', label: 'Settings', icon: 'settings' },
    ],
  },
];
