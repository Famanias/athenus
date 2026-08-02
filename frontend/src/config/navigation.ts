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
    title: '🦉 Wisdom (Νοῦς)',
    items: [
      { id: 'view-chat', label: 'AI Research Assistant', icon: 'forum', badge: 'Active', badgeType: 'active' },
      { id: 'view-ask', label: 'Ask & Explain Concepts', icon: 'psychology' },
      { id: 'view-insights', label: 'AI Synthesis Insights', icon: 'auto_awesome' },
    ],
  },
  {
    id: 'knowledge',
    title: '📚 Knowledge (Episteme)',
    items: [
      { id: 'view-dashboard', label: 'Workspace Library', icon: 'grid_view' },
      { id: 'view-video', label: 'Video Learning Workspace', icon: 'smart_display', badge: 'Active', badgeType: 'active' },
      { id: 'view-transcript', label: 'Transcript Reader', icon: 'description', badge: 'Active', badgeType: 'active' },
      { id: 'view-graph', label: 'Concept Knowledge Graph', icon: 'hub', badge: 'v0.3', badgeType: 'soon' },
    ],
  },
  {
    id: 'strategy',
    title: '⚔️ Strategy (Metis)',
    items: [
      { id: 'view-flashcards', label: 'Active Recall Flashcards', icon: 'layers', badge: 'v0.4', badgeType: 'soon' },
      { id: 'view-quiz', label: 'Adaptive Quizzes', icon: 'quiz', badge: 'v0.4', badgeType: 'soon' },
      { id: 'view-analytics', label: 'Memory & Progress Analytics', icon: 'analytics' },
    ],
  },
  {
    id: 'infrastructure',
    title: 'Infrastructure',
    items: [
      { id: 'view-ingestion', label: 'Ingestion Pipeline', icon: 'database', badge: 'Active', badgeType: 'active' },
      { id: 'view-settings', label: 'AI Models & Providers', icon: 'settings' },
    ],
  },
];
