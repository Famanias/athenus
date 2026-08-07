'use client';

import React from 'react';
import { useQuiz } from './useQuiz';
import { Button } from '@/components/ui/Button';

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export const QuizStudio: React.FC = () => {
  const {
    quizzes,
    activeQuiz,
    selectedVersion,
    currentQuestion,
    currentIndex,
    totalQuestions,
    selectedOptId,
    showExplanation,
    artifact,
    settings,
    loading,
    generating,
    error,
    toastMessage,
    attempt,
    elapsed,
    generateQuiz,
    selectVersion,
    handleSelectOption,
    handleNext,
    submitQuiz,
    updateSettings,
    jumpToSource,
    setActiveView,
  } = useQuiz();

  const isLastQuestion = currentIndex === totalQuestions - 1;

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-4xl mx-auto space-y-6 w-full">
      {/* Completion Toast Banner */}
      {toastMessage && (
        <div className="px-4 py-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 font-mono text-xs font-semibold animate-pulse flex items-center justify-between">
          <span>{toastMessage}</span>
          <span className="text-[10px] text-emerald-400/60 uppercase tracking-wider">Active version synced</span>
        </div>
      )}
      {/* Header */}
      <div className="flex justify-between items-center pb-4 border-b border-outline-variant">
        <div>
          <h2 className="font-type-light text-2xl font-bold text-on-surface">
            Adaptive Comprehension Quiz Studio
          </h2>
          <p className="text-xs text-on-surface-variant mt-1">
            {activeQuiz
              ? `${activeQuiz.title} — Instant feedback, detailed explanations, and source links.`
              : 'No Quiz Loaded'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Generation Target Budget Control */}
          <div className="flex items-center gap-2 bg-surface-container-high px-3 py-1.5 rounded-lg border border-outline-variant/50">
            <span className="text-xs text-on-surface-variant font-mono">Density:</span>
            <select
              value={settings.quiz_target_budget_per_media}
              onChange={(e) => updateSettings({ quiz_target_budget_per_media: Number(e.target.value) })}
              className="bg-transparent text-xs font-mono text-primary outline-none cursor-pointer"
            >
              <option value={10} className="bg-surface text-on-surface">Compact</option>
              <option value={15} className="bg-surface text-on-surface">Standard</option>
              <option value={30} className="bg-surface text-on-surface">Deep</option>
            </select>
          </div>

          {activeQuiz && (
            <span className="font-mono text-xs text-secondary bg-secondary/10 px-3 py-1 rounded border border-secondary/30">
              Quiz v{activeQuiz.version} · {totalQuestions} Qs
            </span>
          )}
          {!attempt && totalQuestions > 0 && (
            <span className="font-mono text-xs text-on-surface-variant bg-surface-container-low px-3 py-1 rounded border border-outline-variant">
              ⏱ {formatTime(elapsed)}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            icon="add_chart"
            disabled={generating}
            onClick={() => generateQuiz()}
          >
            {generating ? 'Generating...' : activeQuiz ? 'Regenerate' : 'Generate Quiz'}
          </Button>
        </div>
      </div>

      {/* Independent Quiz Artifact Lifecycle Status Bar */}
      <div className="px-4 py-2 border border-outline-variant bg-surface-container-low rounded flex items-center gap-3 text-[11px] font-mono">
        <span className="text-on-surface-variant">Artifact:</span>
        <span className={`font-bold uppercase ${artifact?.status === 'failed' ? 'text-rose-400' : artifact?.status === 'ready' ? 'text-emerald-400' : 'text-secondary'}`}>
          {artifact?.status || 'idle'}
        </span>
        {artifact?.stage && artifact.stage !== 'ready' && (
          <span className="text-on-surface-variant/70">{artifact.stage.replace(/_/g, ' ')}</span>
        )}
        <span className="text-on-surface-variant/60">progress {artifact?.progress ?? 0}%</span>
        {artifact?.message && (
          <span className="text-on-surface-variant truncate">{artifact.message}</span>
        )}
        <div className="flex-1 h-1.5 rounded-full bg-surface-container-highest overflow-hidden">
          <div
            className="h-full rounded-full bg-secondary transition-all"
            style={{ width: `${artifact?.progress ?? 0}%` }}
          />
        </div>
      </div>

      {/* Version selector */}
      {quizzes.length > 1 && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-mono text-[10px] text-on-surface-variant uppercase tracking-wider">
            Quiz versions:
          </span>
          {quizzes.map((quiz) => (
            <button
              key={quiz.id}
              onClick={() => selectVersion(quiz.version)}
              className={`font-mono text-xs px-3 py-1 rounded border transition-colors ${
                selectedVersion === quiz.version
                  ? 'bg-secondary text-on-secondary border-secondary'
                  : 'bg-surface-container-low text-on-surface-variant border-outline-variant hover:bg-surface-container-high'
              }`}
            >
              v{quiz.version}
              {quiz.status !== 'ready' && <span className="ml-1">({quiz.status})</span>}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="p-3 rounded border border-error/40 bg-error/10 text-xs text-error font-mono">
          {error}
        </div>
      )}

      {loading && (
        <div className="p-12 text-center text-xs text-on-surface-variant font-mono">
          Generating quiz questions...
        </div>
      )}

      {!loading && !error && totalQuestions === 0 && !attempt && (
        <div className="p-12 border border-dashed border-outline-variant rounded-lg bg-surface-container-low text-center space-y-3">
          <span className="text-4xl block">🧩</span>
          <h4 className="font-bold text-sm text-on-surface">No Comprehension Quiz Generated Yet</h4>
          <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
            Process a lecture video to extract concepts, then generate a concept-balanced
            comprehension quiz grounded in your knowledge graph.
          </p>
          <div className="flex justify-center gap-3">
            <Button variant="primary" icon="upload_file" onClick={() => setActiveView('view-ingestion')}>
              Upload Lecture
            </Button>
            <Button variant="outline" icon="auto_awesome" disabled={generating} onClick={() => generateQuiz()}>
              Generate Quiz
            </Button>
          </div>
        </div>
      )}

      {/* Results panel */}
      {!loading && attempt && (
        <div className="p-8 border rounded-lg bg-surface-container-low text-center space-y-4">
          <span className="text-4xl block">
            {attempt.score >= 80 ? '🏆' : attempt.score >= 50 ? '📈' : '📚'}
          </span>
          <h3 className="font-type-light text-2xl font-bold text-on-surface">
            Quiz Complete — {attempt.score.toFixed(0)}%
          </h3>
          <p className="text-xs text-on-surface-variant font-mono">
            {attempt.correct_count} of {attempt.total_questions} correct · {formatTime(attempt.time_taken)} elapsed
          </p>
          <div className="w-full max-w-sm mx-auto h-2 rounded-full bg-surface-container-highest overflow-hidden">
            <div
              className="h-full rounded-full bg-secondary transition-all"
              style={{ width: `${attempt.score || 0}%` }}
            />
          </div>
          <div className="pt-2">
            <Button variant="outline" size="sm" icon="refresh" onClick={() => selectVersion(activeQuiz?.version || 1)}>
              Review Questions
            </Button>
          </div>
        </div>
      )}

      {/* Question Card */}
      {!loading && currentQuestion && !attempt && (
        <div className="p-6 bg-surface-container-low border border-outline-variant rounded space-y-6">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-bold text-on-surface leading-relaxed">
              {currentQuestion.question}
            </h4>
          </div>

          {/* Options List */}
          <div className="space-y-3">
            {currentQuestion.options.map((opt) => {
              const isSelected = selectedOptId === opt.id;
              let borderStyle = 'border-outline-variant hover:border-secondary';
              let bgStyle = 'bg-surface-container';

              if (showExplanation && isSelected) {
                if (opt.isCorrect) {
                  borderStyle = 'border-emerald-400';
                  bgStyle = 'bg-emerald-950/40 text-emerald-300';
                } else {
                  borderStyle = 'border-rose-400';
                  bgStyle = 'bg-rose-950/40 text-rose-300';
                }
              } else if (showExplanation && opt.isCorrect) {
                borderStyle = 'border-emerald-400/60';
                bgStyle = 'bg-emerald-950/20';
              }

              return (
                <div
                  key={opt.id}
                  onClick={() => handleSelectOption(opt.id)}
                  className={`p-3.5 border rounded text-xs cursor-pointer transition-all ${borderStyle} ${bgStyle}`}
                >
                  {opt.text}
                </div>
              );
            })}
          </div>

          {/* Explanation Block */}
          {showExplanation && (
            <div className="p-4 rounded bg-surface-container-highest border border-secondary/40 text-xs space-y-1">
              <span className="font-bold text-secondary font-mono block mb-1">
                Explanation Feedback:
              </span>
              <p className="text-on-surface-variant leading-relaxed">{currentQuestion.explanation}</p>
              {currentQuestion.mediaId && currentQuestion.startTime != null && (
                <button
                  onClick={() => jumpToSource(currentQuestion.mediaId, currentQuestion.startTime)}
                  className="text-[10px] font-mono text-secondary/80 hover:text-secondary underline underline-offset-2 pt-1"
                >
                  Jump to source at {currentQuestion.startTime.toFixed(1)}s ⏱
                </button>
              )}
            </div>
          )}

          {/* Action Controls */}
          {showExplanation && !isLastQuestion && (
            <div className="pt-2 flex justify-end">
              <Button variant="primary" size="md" onClick={handleNext}>
                Next Question →
              </Button>
            </div>
          )}

          {showExplanation && isLastQuestion && (
            <div className="pt-2 flex justify-end">
              <Button variant="primary" size="md" icon="check_circle" onClick={submitQuiz}>
                Submit Quiz
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
