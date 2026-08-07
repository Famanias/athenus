'use client';

import React from 'react';
import { useAnalytics, ConceptMasteryDTO, RevisionRecommendationDTO } from './useAnalytics';
import { Button } from '@/components/ui/Button';

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const hrs = Math.floor(mins / 60);
  if (hrs > 0) return `${hrs}h ${mins % 60}m`;
  if (mins > 0) return `${mins}m ${Math.floor(seconds % 60)}s`;
  return `${Math.floor(seconds)}s`;
}

function masteryColor(level: number): string {
  if (level >= 0.7) return 'text-emerald-400';
  if (level >= 0.4) return 'text-amber-400';
  return 'text-rose-400';
}

function masteryBar(level: number): string {
  if (level >= 0.7) return 'bg-emerald-400';
  if (level >= 0.4) return 'bg-amber-400';
  return 'bg-rose-400';
}

function StatCard({ icon, label, value, sub }: { icon: string; label: string; value: string; sub?: string }) {
  return (
    <div className="p-4 bg-surface-container-low border border-outline-variant rounded space-y-1">
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-secondary text-base">{icon}</span>
        <span className="font-mono text-[10px] text-on-surface-variant uppercase tracking-wider">{label}</span>
      </div>
      <p className="font-type-light text-2xl font-bold text-on-surface">{value}</p>
      {sub && <p className="font-mono text-[10px] text-on-surface-variant">{sub}</p>}
    </div>
  );
}

function MasteryRow({ m }: { m: ConceptMasteryDTO }) {
  const level = Math.round((m.mastery_level || 0) * 100);
  return (
    <div className="flex items-center gap-3 py-2 border-b border-outline-variant/50 last:border-0">
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-on-surface truncate">{m.concept_name || m.concept_id}</p>
        <p className="font-mono text-[10px] text-on-surface-variant">
          {m.review_count} reviews · {m.quiz_correct}/{m.quiz_attempts} quiz correct
        </p>
      </div>
      <div className="w-28">
        <div className="h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
          <div className={`h-full rounded-full ${masteryBar(m.mastery_level)}`} style={{ width: `${level}%` }} />
        </div>
      </div>
      <span className={`font-mono text-xs font-bold w-10 text-right ${masteryColor(m.mastery_level)}`}>
        {level}%
      </span>
    </div>
  );
}

function RecommendationRow({ r }: { r: RevisionRecommendationDTO }) {
  const priorityStyles =
    r.priority === 'high'
      ? 'border-rose-400/50 bg-rose-950/20 text-rose-300'
      : 'border-amber-400/40 bg-amber-950/20 text-amber-300';
  return (
    <div className="flex items-center justify-between gap-3 py-2.5 border-b border-outline-variant/50 last:border-0">
      <div className="flex items-center gap-2.5 min-w-0">
        <span className="material-symbols-outlined text-secondary text-base">
          {r.type === 'flashcard' ? 'layers' : 'hub'}
        </span>
        <div className="min-w-0">
          <p className="text-xs font-semibold text-on-surface truncate">{r.title}</p>
          <p className="font-mono text-[10px] text-on-surface-variant">
            {r.concept_name || '—'} · mastery {Math.round((r.mastery_level || 0) * 100)}%
          </p>
        </div>
      </div>
      <span className={`font-mono text-[10px] px-2 py-0.5 rounded border uppercase ${priorityStyles}`}>
        {r.priority}
      </span>
    </div>
  );
}

export const AnalyticsDashboard: React.FC = () => {
  const {
    workspace,
    conceptMastery,
    recentActivity,
    recommendations,
    loading,
    error,
    fetchSummary,
    jumpToRevision,
    setActiveView,
  } = useAnalytics();

  const sortedMastery = [...conceptMastery].sort((a, b) => b.mastery_level - a.mastery_level);
  const highPriority = recommendations.filter((r) => r.priority === 'high');

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-5xl mx-auto space-y-6 w-full">
      <div className="flex justify-between items-center pb-4 border-b border-outline-variant">
        <div>
          <h2 className="font-type-light text-2xl font-bold text-on-surface">
            Learning Analytics
          </h2>
          <p className="text-xs text-on-surface-variant mt-1">
            Precomputed, event-driven mastery tracking across your workspace.
          </p>
        </div>
        <Button variant="outline" size="sm" icon="refresh" onClick={fetchSummary}>
          Refresh
        </Button>
      </div>

      {error && (
        <div className="p-3 rounded border border-error/40 bg-error/10 text-xs text-error font-mono">
          {error}
        </div>
      )}

      {loading && (
        <div className="p-12 text-center text-xs text-on-surface-variant font-mono">
          Loading analytics...
        </div>
      )}

      {!loading && workspace && (
        <>
          {/* Stat cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard icon="grid_view" label="Media" value={String(workspace.total_media || 0)} />
            <StatCard icon="hub" label="Concepts" value={String(workspace.total_concepts || 0)} />
            <StatCard icon="layers" label="Flashcards" value={String(workspace.total_flashcards || 0)} />
            <StatCard icon="quiz" label="Quiz attempts" value={String(workspace.total_quiz_attempts || 0)} />
            <StatCard icon="reviews" label="Reviews" value={String(workspace.total_reviews || 0)} />
            <StatCard
              icon="local_fire_department"
              label="Streak"
              value={`${workspace.review_streak_days || 0}d`}
              sub={`${formatDuration(workspace.total_study_seconds)} studied`}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Concept mastery */}
            <div className="p-5 bg-surface-container-low border border-outline-variant rounded space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-on-surface">Concept Mastery</h3>
                <span className="font-mono text-[10px] text-secondary bg-secondary/10 px-2 py-0.5 rounded border border-secondary/30">
                  avg {Math.round((workspace.avg_quiz_score || 0))}% quiz score
                </span>
              </div>
              {sortedMastery.length === 0 ? (
                <p className="text-xs text-on-surface-variant font-mono py-4 text-center">
                  No mastery data yet — take a quiz or review flashcards.
                </p>
              ) : (
                <div className="max-h-72 overflow-y-auto custom-scrollbar">
                  {sortedMastery.map((m) => (
                    <MasteryRow key={m.concept_id} m={m} />
                  ))}
                </div>
              )}
            </div>

            {/* Revision recommendations */}
            <div className="p-5 bg-surface-container-low border border-outline-variant rounded space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-on-surface">Revision Recommendations</h3>
                {highPriority.length > 0 && (
                  <span className="font-mono text-[10px] text-rose-300 bg-rose-950/20 px-2 py-0.5 rounded border border-rose-400/40">
                    {highPriority.length} high priority
                  </span>
                )}
              </div>
              {recommendations.length === 0 ? (
                <div className="text-center py-4 space-y-2">
                  <p className="text-xs text-on-surface-variant font-mono">
                    No revisions needed right now.
                  </p>
                  <Button variant="outline" size="sm" icon="auto_awesome" onClick={() => setActiveView('view-flashcards')}>
                    Practice Flashcards
                  </Button>
                </div>
              ) : (
                <div className="max-h-72 overflow-y-auto custom-scrollbar">
                  {recommendations.map((r, i) => (
                    <div
                      key={`${r.type}-${r.card_id || r.concept_id || i}`}
                      onClick={() => jumpToRevision(r)}
                      className="cursor-pointer hover:bg-surface-container-high/60 rounded"
                    >
                      <RecommendationRow r={r} />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Recent activity */}
          <div className="p-5 bg-surface-container-low border border-outline-variant rounded space-y-3">
            <h3 className="text-sm font-bold text-on-surface">Recent Activity</h3>
            {recentActivity.length === 0 ? (
              <p className="text-xs text-on-surface-variant font-mono py-3 text-center">
                No study activity recorded yet.
              </p>
            ) : (
              <div className="space-y-2">
                {recentActivity.map((a) => (
                  <div key={a.id} className="flex items-center justify-between py-1.5 border-b border-outline-variant/50 last:border-0">
                    <span className="font-mono text-[11px] text-on-surface">
                      {a.activity_type === 'quiz' ? '🧩 Quiz completed' : a.activity_type === 'review' ? '🎴 Flashcard review' : a.activity_type}
                    </span>
                    <span className="font-mono text-[10px] text-on-surface-variant">
                      {formatDuration(a.duration_seconds)} · {a.created_at ? new Date(a.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
