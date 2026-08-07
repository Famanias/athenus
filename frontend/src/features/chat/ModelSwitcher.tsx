'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { useAppStore } from '@/store/useAppStore';
import {
  getProviderCatalog,
  patchProviderSettings,
  ProviderCatalogProviderDTO,
} from '@/services/settingsService';

interface ModelSwitcherProps {
  className?: string;
}

const selectClass =
  'bg-surface-container-high px-2 py-1 rounded border border-outline-variant text-[11px] font-mono text-secondary focus:outline-none focus:border-secondary disabled:opacity-50 max-w-[180px]';

export const ModelSwitcher: React.FC<ModelSwitcherProps> = ({ className }) => {
  const llmProvider = useAppStore((s) => s.llmProvider);
  const activeModel = useAppStore((s) => s.activeModel);
  const setProviderSettings = useAppStore((s) => s.setProviderSettings);

  const [catalog, setCatalog] = useState<ProviderCatalogProviderDTO[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadCatalog = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await getProviderCatalog();
      setCatalog(res.providers);
      const state = useAppStore.getState();
      const nextProvider = res.active.provider;
      const nextModel = res.active.model || state.activeModel;
      if (nextProvider !== state.llmProvider || (nextModel && nextModel !== state.activeModel)) {
        setProviderSettings(nextProvider, state.sttProvider, state.gpuAcceleration, nextModel);
      }
    } catch {
      setError('Model list unavailable');
    } finally {
      setIsLoading(false);
    }
  }, [setProviderSettings]);

  useEffect(() => {
    loadCatalog();
  }, [loadCatalog]);

  const activeProvider = catalog.find((p) => p.id === llmProvider) ?? catalog[0];
  const ollamaModels = activeProvider?.id === 'ollama' ? activeProvider.models : [];
  const isStaleOllamaModel =
    activeProvider?.id === 'ollama' &&
    !!activeModel &&
    ollamaModels.length > 0 &&
    !ollamaModels.some((m) => m.id === activeModel);

  const modelValue = activeProvider ? activeModel : '';

  const handleProviderChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const provider = e.target.value;
    if (provider === llmProvider) return;
    setIsSaving(true);
    setError(null);
    try {
      const res = await patchProviderSettings({ default_llm: provider });
      setProviderSettings(
        res.default_llm,
        res.default_stt,
        res.gpu_acceleration,
        res.selected_model || ''
      );
    } catch {
      setError('Failed to switch provider');
    } finally {
      setIsSaving(false);
    }
  };

  const handleModelChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const model = e.target.value;
    if (model === modelValue) return;
    setIsSaving(true);
    setError(null);
    try {
      const res = await patchProviderSettings({
        default_llm: llmProvider,
        selected_model: model,
      });
      setProviderSettings(
        res.default_llm,
        res.default_stt,
        res.gpu_acceleration,
        res.selected_model || ''
      );
    } catch {
      setError('Failed to switch model');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <span className="bg-surface-container-high px-2.5 py-1 rounded border border-outline-variant text-[10px] font-mono text-secondary">
        Loading models...
      </span>
    );
  }

  if (!activeProvider || catalog.length === 0) {
    return (
      <span
        className="bg-surface-container-high px-2.5 py-1 rounded border border-outline-variant text-[10px] font-mono text-secondary"
        title={error ?? undefined}
      >
        Model unavailable
      </span>
    );
  }

  return (
    <div className={`flex items-center gap-2 ${className ?? ''}`}>
      <select
        value={llmProvider}
        onChange={handleProviderChange}
        disabled={isSaving}
        className={selectClass}
        title="Text generation provider"
      >
        {catalog.map((p) => (
          <option key={p.id} value={p.id}>
            {p.label}
          </option>
        ))}
      </select>
      <select
        value={modelValue}
        onChange={handleModelChange}
        disabled={isSaving || (activeProvider.models.length === 0 && !activeModel)}
        className={selectClass}
        title="Active model"
      >
        {!activeModel && activeProvider.id === 'ollama' && (
          <option value="" disabled>
            -- Select a model --
          </option>
        )}
        {activeModel && !activeProvider.models.some((m) => m.id === activeModel) && (
          <option key={activeModel} value={activeModel}>
            {activeModel}
          </option>
        )}
        {activeProvider.models.map((m) => (
          <option key={m.id} value={m.id}>
            {m.id}
          </option>
        ))}
      </select>
      {isStaleOllamaModel && (
        <span className="text-[10px] font-mono text-amber-300" title="Selected model is no longer available in catalog">
          ⚠
        </span>
      )}
      {error && (
        <span className="text-[10px] font-mono text-rose-300" title={error}>
          ⚠
        </span>
      )}
    </div>
  );
};
