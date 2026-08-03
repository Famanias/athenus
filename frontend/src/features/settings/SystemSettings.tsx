'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';
import {
  getProviderSettings,
  patchProviderSettings,
  getOllamaSettings,
  updateOllamaDirectory,
  scanOllamaModels,
  getProviderCatalog,
  clearAllData,
  OllamaSettingsResponse,
  ProviderCatalogProviderDTO,
} from '@/services/settingsService';

export const SystemSettings: React.FC = () => {
  const { llmProvider, sttProvider, gpuAcceleration, setProviderSettings, setActiveMediaId } = useAppStore();
  const [selectedLlm, setSelectedLlm] = useState<string>(llmProvider);
  const [selectedOllamaModel, setSelectedOllamaModel] = useState<string>('');
  const [selectedStt, setSelectedStt] = useState<string>(sttProvider);
  const [gpuEnabled, setGpuEnabled] = useState<boolean>(gpuAcceleration);
  const [apiKey, setApiKey] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Ollama Model Sources State
  const [ollamaDir, setOllamaDir] = useState<string>('');
  const [ollamaConfig, setOllamaConfig] = useState<OllamaSettingsResponse | null>(null);
  const [catalogProviders, setCatalogProviders] = useState<ProviderCatalogProviderDTO[]>([]);
  const [isSavingOllama, setIsSavingOllama] = useState<boolean>(false);
  const [isScanningOllama, setIsScanningOllama] = useState<boolean>(false);

  // Danger Zone Reset state
  const [isResetModalOpen, setIsResetModalOpen] = useState<boolean>(false);
  const [confirmInputText, setConfirmInputText] = useState<string>('');
  const [isResetting, setIsResetting] = useState<boolean>(false);

  const normalizeLlmProvider = (providerStr: string): string => {
    const p = (providerStr || '').toLowerCase();
    if (p.includes('groq')) return 'groq';
    if (p.includes('openrouter')) return 'openrouter';
    return 'ollama';
  };

  useEffect(() => {
    async function hydrateSettings() {
      try {
        const [data, ollamaRes, catalogRes] = await Promise.all([
          getProviderSettings(),
          getOllamaSettings().catch(() => null),
          getProviderCatalog().catch(() => null),
        ]);
        const normLlm = normalizeLlmProvider(data.default_llm);
        setSelectedLlm(normLlm);
        setSelectedStt(data.default_stt);
        setGpuEnabled(data.gpu_acceleration);
        setApiKey(data.api_key || '');
        setProviderSettings(normLlm, data.default_stt, data.gpu_acceleration, data.selected_ollama_model || '');

        if (catalogRes) {
          setCatalogProviders(catalogRes.providers);
        }

        if (ollamaRes) {
          setOllamaConfig(ollamaRes);
          if (ollamaRes.configured_dir) {
            setOllamaDir(ollamaRes.configured_dir);
          }

          // Hydrate selected Ollama model if present in discovered models
          const savedModel = data.selected_ollama_model;
          if (savedModel && ollamaRes.models.some((m) => m.full_id === savedModel)) {
            setSelectedOllamaModel(savedModel);
          } else {
            setSelectedOllamaModel('');
          }
        }
      } catch (_err) {
        // Fall back to store values
      }
    }
    hydrateSettings();
  }, [setProviderSettings]);

  const refreshCatalog = async () => {
    try {
      const catalogRes = await getProviderCatalog();
      setCatalogProviders(catalogRes.providers);
    } catch {
      // Ignore refresh failures; existing catalog state remains usable
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setToastMessage(null);

    try {
      const updated = await patchProviderSettings({
        default_llm: selectedLlm,
        selected_ollama_model: selectedLlm === 'ollama' ? selectedOllamaModel : undefined,
        default_stt: selectedStt,
        gpu_acceleration: gpuEnabled,
        api_key: apiKey,
      });

      setProviderSettings(
        updated.default_llm,
        updated.default_stt,
        updated.gpu_acceleration,
        updated.selected_ollama_model || ''
      );
      const modelDetail =
        selectedLlm === 'ollama' && selectedOllamaModel
          ? ` (${selectedOllamaModel})`
          : '';
      setToastMessage({
        type: 'success',
        text: `✓ ${selectedLlm.toUpperCase()}${modelDetail} Provider & API Key saved successfully!`,
      });
    } catch (err: any) {
      setToastMessage({
        type: 'error',
        text: `✕ Failed to save settings: ${err.message || 'Backend unreachable'}`,
      });
    } finally {
      setIsSaving(false);
    }
  };

  const syncOllamaModelSelection = (res: OllamaSettingsResponse) => {
    setOllamaConfig(res);
    if (res.configured_dir) {
      setOllamaDir(res.configured_dir);
    }
    // Preserve selection if model exists, otherwise prompt user
    setSelectedOllamaModel((prev) => {
      if (prev && res.models.some((m) => m.full_id === prev)) {
        return prev;
      }
      return '';
    });
  };

  const handleSaveOllamaDir = async () => {
    if (!ollamaDir.trim() || isSavingOllama) return;
    setIsSavingOllama(true);
    setToastMessage(null);

    try {
      const res = await updateOllamaDirectory(ollamaDir.trim());
      syncOllamaModelSelection(res);
      refreshCatalog();
      setToastMessage({
        type: 'success',
        text: `✓ Ollama models directory saved! (${res.models_count} models discovered)`,
      });
    } catch (err: any) {
      setToastMessage({
        type: 'error',
        text: `✕ Failed to save Ollama directory: ${err.message || 'Invalid path'}`,
      });
    } finally {
      setIsSavingOllama(false);
    }
  };

  const handleRefreshOllama = async () => {
    if (isScanningOllama) return;
    setIsScanningOllama(true);
    setToastMessage(null);

    try {
      const res = await scanOllamaModels();
      syncOllamaModelSelection(res);
      refreshCatalog();
      setToastMessage({
        type: 'success',
        text: `✓ Refreshed! (${res.models_count} models discovered)`,
      });
    } catch (err: any) {
      setToastMessage({
        type: 'error',
        text: `✕ Rescan failed: ${err.message || 'Error scanning models'}`,
      });
    } finally {
      setIsScanningOllama(false);
    }
  };

  const handleBrowseFolder = async () => {
    try {
      const dialog = await import('@tauri-apps/api/dialog');
      const selected = await dialog.open({ directory: true, multiple: false });
      if (typeof selected === 'string') {
        setOllamaDir(selected);
      }
    } catch {
      // Browser fallback (manual paste)
    }
  };

  const handleExecuteReset = async () => {
    if (confirmInputText.trim() !== 'CLEAR MY DATA') return;
    setIsResetting(true);
    setToastMessage(null);

    try {
      await clearAllData();

      setActiveMediaId(null);
      if (typeof window !== 'undefined') {
        Object.keys(localStorage)
          .filter((k) => k.startsWith('athenus_'))
          .forEach((k) => localStorage.removeItem(k));
      }

      setToastMessage({
        type: 'success',
        text: '✓ All application data, transcripts, and vector indices cleared successfully! Reloading...',
      });
      setIsResetModalOpen(false);
      setConfirmInputText('');
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (err: any) {
      setToastMessage({
        type: 'error',
        text: `✕ Factory reset failed: ${err.message || 'Server error'}`,
      });
    } finally {
      setIsResetting(false);
    }
  };

  const isCloudProvider = selectedLlm === 'openrouter' || selectedLlm === 'groq';
  const ollamaCatalogModels = catalogProviders.find((p) => p.id === 'ollama')?.models ?? [];

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-3xl mx-auto space-y-6 w-full">
      {/* Toast Notification Banner */}
      {toastMessage && (
        <div
          className={`p-3 rounded border text-xs flex justify-between items-center ${
            toastMessage.type === 'success'
              ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
              : 'bg-rose-950/60 border-rose-500/40 text-rose-300'
          }`}
        >
          <span>{toastMessage.text}</span>
          <button onClick={() => setToastMessage(null)} className="text-on-surface-variant hover:text-on-surface">
            ✕
          </button>
        </div>
      )}

      {/* Header */}
      <div className="pb-4 border-b border-outline-variant">
        <h2 className="font-carvist text-2xl font-bold text-on-surface">
          AI Models & Capability Bus Providers
        </h2>
        <p className="text-xs text-on-surface-variant mt-1">
          Configure local vs cloud model routing, local model directories, and vector database indices.
        </p>
      </div>

      {/* Model Provider Form */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-6">
        <div>
          <label className="block text-xs font-bold text-on-surface mb-2 font-mono uppercase">
            Text Generation Provider (LLM)
          </label>
          <select
            value={selectedLlm}
            onChange={(e) => setSelectedLlm(e.target.value)}
            className="w-full bg-surface-container border border-outline-variant rounded p-2.5 text-xs text-on-surface focus:border-secondary focus:outline-none"
          >
            {catalogProviders.length > 0 ? (
              catalogProviders.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))
            ) : (
              <>
                <option value="ollama">Ollama (Local)</option>
                <option value="groq">Groq API (Cloud LPU)</option>
                <option value="openrouter">OpenRouter API (Cloud Universal)</option>
              </>
            )}
          </select>
        </div>

        {/* Dynamic Active Ollama Model Dropdown */}
        {selectedLlm === 'ollama' && (
          <div className="space-y-2">
            <label className="block text-xs font-bold text-on-surface mb-2 font-mono uppercase">
              Active Ollama Local Model
            </label>
            {ollamaCatalogModels.length > 0 ? (
              <select
                value={selectedOllamaModel}
                onChange={(e) => setSelectedOllamaModel(e.target.value)}
                className="w-full bg-surface-container border border-outline-variant rounded p-2.5 text-xs font-mono text-on-surface focus:border-secondary focus:outline-none"
              >
                <option value="" disabled>
                  -- Select an Ollama Model --
                </option>
                {ollamaCatalogModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.id}
                  </option>
                ))}
              </select>
            ) : (
              <div className="p-3 bg-amber-950/40 border border-amber-500/30 rounded text-xs text-amber-300">
                ⚠️ No local Ollama models discovered. Configure your local models directory below to scan installed models.
              </div>
            )}
          </div>
        )}

        {/* Dynamic API Key Input for Cloud Providers */}
        {isCloudProvider && (
          <div className="p-4 bg-surface-container border border-secondary/30 rounded space-y-2">
            <label className="block text-xs font-bold text-secondary font-mono uppercase">
              🔑 {selectedLlm.toUpperCase()} API Key
            </label>
            <input
              type="password"
              placeholder={`Enter your ${selectedLlm.toUpperCase()} API Key (e.g. sk-or-v1-...)`}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full bg-surface-container-low border border-outline-variant rounded p-2.5 text-xs text-on-surface font-mono focus:border-secondary focus:outline-none"
            />
            <p className="text-[11px] text-on-surface-variant">
              Key is stored securely in memory for dynamic provider routing without hardcoding.
            </p>
          </div>
        )}

        <div>
          <label className="block text-xs font-bold text-on-surface mb-2 font-mono uppercase">
            Speech-to-Text Provider (STT)
          </label>
          <select
            value={selectedStt}
            onChange={(e) => setSelectedStt(e.target.value)}
            className="w-full bg-surface-container border border-outline-variant rounded p-2.5 text-xs text-on-surface focus:border-secondary focus:outline-none"
          >
            <option value="faster-whisper">Faster-Whisper (Local CTranslate2)</option>
          </select>
        </div>

        <div className="flex items-center justify-between pt-2">
          <div>
            <span className="text-xs font-bold text-on-surface block">
              CUDA GPU Hardware Acceleration
            </span>
            <span className="text-[11px] text-on-surface-variant">
              Utilize NVIDIA CUDA tensor cores for transcription & inference acceleration.
            </span>
          </div>
          <input
            type="checkbox"
            checked={gpuEnabled}
            onChange={(e) => setGpuEnabled(e.target.checked)}
            className="rounded accent-secondary w-4 h-4"
          />
        </div>

        <div className="pt-4 border-t border-outline-variant/40 flex justify-end">
          <Button variant="primary" onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving Configuration...' : 'Save Configuration'}
          </Button>
        </div>
      </div>

      {/* Model Sources Section */}
      <div className="space-y-4">
        <div className="pb-2 border-b border-outline-variant/60">
          <h3 className="font-bold text-base text-on-surface font-carvist">
            Model Sources
          </h3>
          <p className="text-xs text-on-surface-variant mt-0.5">
            Configure local model storage directories and scan discovered models.
          </p>
        </div>

        {/* Local Ollama Models Directory Card */}
        <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-secondary text-sm">folder_managed</span>
              <h4 className="font-bold text-xs text-on-surface font-mono uppercase">
                Local Ollama Models Directory
              </h4>
            </div>

            {/* Status Badge */}
            {ollamaConfig && (
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded border font-semibold ${
                  ollamaConfig.valid
                    ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300'
                    : 'bg-rose-950/60 border-rose-500/40 text-rose-300'
                }`}
              >
                {ollamaConfig.valid
                  ? `✓ Valid (${ollamaConfig.models_count} models discovered)`
                  : '✕ Invalid Directory'}
              </span>
            )}
          </div>

          <div className="space-y-2">
            <label className="block text-[11px] text-on-surface-variant font-mono">
              DIRECTORY PATH
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={ollamaDir}
                onChange={(e) => setOllamaDir(e.target.value)}
                placeholder="e.g. C:\Users\YourName\.ollama\models"
                className="flex-1 bg-surface-container border border-outline-variant rounded px-3 py-2 text-xs font-mono text-on-surface focus:border-secondary focus:outline-none"
              />
              <Button type="button" variant="secondary" size="sm" onClick={handleBrowseFolder}>
                Browse
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleSaveOllamaDir}
                disabled={isSavingOllama || !ollamaDir.trim()}
              >
                {isSavingOllama ? 'Saving...' : 'Save'}
              </Button>
              {ollamaConfig && ollamaConfig.valid && (
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleRefreshOllama}
                  disabled={isScanningOllama}
                >
                  {isScanningOllama ? 'Scanning...' : 'Refresh'}
                </Button>
              )}
            </div>
          </div>

          {/* Configured vs Resolved Directory Paths Display */}
          {ollamaConfig && ollamaConfig.valid && (
            <div className="p-3 bg-surface-container/60 border border-outline-variant/40 rounded space-y-1 text-[11px] font-mono">
              <div className="flex items-center gap-2 text-on-surface-variant">
                <span className="text-secondary font-semibold">Configured Path:</span>
                <span className="truncate">{ollamaConfig.configured_dir}</span>
              </div>
              <div className="flex items-center gap-2 text-on-surface-variant">
                <span className="text-secondary font-semibold">Resolved Path:</span>
                <span className="truncate">{ollamaConfig.resolved_dir}</span>
              </div>
            </div>
          )}

          {/* Error Details if Invalid */}
          {ollamaConfig && !ollamaConfig.valid && ollamaConfig.error && (
            <div className="p-3 bg-rose-950/40 border border-rose-500/30 rounded text-xs text-rose-300">
              {ollamaConfig.error}
            </div>
          )}

          {/* Available Local Models Grid */}
          <div className="pt-2 border-t border-outline-variant/30 space-y-2">
            <h5 className="text-[11px] font-mono text-secondary uppercase font-semibold">
              Available Local Models ({ollamaConfig?.models_count || 0})
            </h5>

            {ollamaConfig && ollamaConfig.models.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-48 overflow-y-auto custom-scrollbar p-1">
                {ollamaConfig.models.map((m) => (
                  <div
                    key={m.full_id}
                    className="p-2.5 bg-surface-container border border-outline-variant rounded flex justify-between items-center text-xs"
                  >
                    <div className="flex items-center gap-2 truncate pr-2">
                      <span className="material-symbols-outlined text-xs text-secondary shrink-0">
                        smart_toy
                      </span>
                      <span className="font-bold text-on-surface truncate">{m.model_name}</span>
                    </div>
                    <span className="bg-secondary/15 text-secondary border border-secondary/30 px-2 py-0.5 rounded font-mono text-[10px] shrink-0 font-semibold">
                      :{m.tag}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 text-center border border-dashed border-outline-variant/40 rounded text-xs text-on-surface-variant italic">
                {ollamaConfig?.valid
                  ? 'No Ollama models found in configured directory.'
                  : 'Configure a valid Ollama models directory to discover local models.'}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Danger Zone: Application Factory Reset */}
      <div className="p-6 bg-rose-950/20 border border-rose-500/30 rounded-lg space-y-4">
        <div className="flex items-center gap-2 text-rose-400">
          <span className="material-symbols-outlined text-base">warning</span>
          <h3 className="font-bold text-xs font-mono uppercase tracking-wider">
            Danger Zone: Factory Reset
          </h3>
        </div>
        <p className="text-xs text-on-surface-variant">
          Permanently delete all SQLite database records, uploaded video files, interactive transcripts, chat sessions, and vector indices.
        </p>

        {!isResetModalOpen ? (
          <Button
            variant="secondary"
            size="sm"
            className="text-rose-400 hover:bg-rose-950/40 border-rose-500/40"
            onClick={() => setIsResetModalOpen(true)}
          >
            Clear All Data
          </Button>
        ) : (
          <div className="p-4 bg-surface-container border border-rose-500/40 rounded space-y-3">
            <p className="text-xs font-semibold text-rose-300">
              Type <code className="bg-rose-950 px-1.5 py-0.5 rounded font-mono text-rose-200">CLEAR MY DATA</code> to confirm permanent deletion:
            </p>
            <input
              type="text"
              value={confirmInputText}
              onChange={(e) => setConfirmInputText(e.target.value)}
              placeholder="CLEAR MY DATA"
              className="w-full bg-surface-container-low border border-rose-500/40 rounded p-2 text-xs font-mono text-on-surface focus:outline-none"
            />
            <div className="flex gap-2 justify-end">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setIsResetModalOpen(false);
                  setConfirmInputText('');
                }}
              >
                Cancel
              </Button>
              <Button
                variant="secondary"
                size="sm"
                className="bg-rose-600 hover:bg-rose-700 text-white font-bold border-none"
                onClick={handleExecuteReset}
                disabled={confirmInputText.trim() !== 'CLEAR MY DATA' || isResetting}
              >
                {isResetting ? 'Purging All Data...' : 'Confirm Reset'}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
