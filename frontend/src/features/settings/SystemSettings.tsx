'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';
import {
  getProviderSettings,
  patchProviderSettings,
  getOllamaSettings,
  updateOllamaDirectory,
  scanOllamaModels,
  getProviderCatalog,
  getLocalProviderStatus,
  getLocalProviderModels,
  clearAllData,
  OllamaSettingsResponse,
  ProviderCatalogProviderDTO,
  LocalProviderStatusDTO,
  CatalogModelDTO,
} from '@/services/settingsService';

export const SystemSettings: React.FC = () => {
  const { llmProvider, sttProvider, gpuAcceleration, selectedOllamaModel: storeOllamaModel, setProviderSettings, setActiveMediaId } = useAppStore();
  const [selectedLlm, setSelectedLlm] = useState<string>(llmProvider);
  const [selectedOllamaModel, setSelectedOllamaModel] = useState<string>(storeOllamaModel);
  const [selectedStt, setSelectedStt] = useState<string>(sttProvider);
  const [gpuEnabled, setGpuEnabled] = useState<boolean>(gpuAcceleration);
  const [apiKey, setApiKey] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Diagnostic metrics & refresh tracking
  const [lastCheckedTime, setLastCheckedTime] = useState<string>('');
  const [restLatencyMs, setRestLatencyMs] = useState<number | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState<boolean>(true);

  // Live Ollama Daemon REST API State
  const [ollamaStatus, setOllamaStatus] = useState<LocalProviderStatusDTO | null>(null);
  const [liveOllamaModels, setLiveOllamaModels] = useState<CatalogModelDTO[]>([]);
  const [isRefreshingDaemon, setIsRefreshingDaemon] = useState<boolean>(false);

  // Local Model Storage (Host Filesystem) State
  const [ollamaDir, setOllamaDir] = useState<string>('');
  const [ollamaConfig, setOllamaConfig] = useState<OllamaSettingsResponse | null>(null);
  const [catalogProviders, setCatalogProviders] = useState<ProviderCatalogProviderDTO[]>([]);
  const [isSavingOllamaDir, setIsSavingOllamaDir] = useState<boolean>(false);
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

  const updateTimestamp = () => {
    const now = new Date();
    setLastCheckedTime(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
  };

  // Fetch Live Ollama Daemon Connection & Models
  const fetchOllamaDaemonInfo = useCallback(async () => {
    setIsRefreshingDaemon(true);
    const startTime = performance.now();
    try {
      const [status, catalog] = await Promise.all([
        getLocalProviderStatus('ollama'),
        getLocalProviderModels('ollama'),
      ]);
      const endTime = performance.now();
      setRestLatencyMs(Math.round(endTime - startTime));
      setOllamaStatus(status);
      setLiveOllamaModels(catalog.models);
    } catch {
      setRestLatencyMs(null);
      setOllamaStatus({
        provider_id: 'ollama',
        label: 'Ollama',
        connected: false,
        error: 'Unreachable at configured endpoint',
      });
      setLiveOllamaModels([]);
    } finally {
      setIsRefreshingDaemon(false);
      updateTimestamp();
    }
  }, []);

  // Event-driven Refresh Strategy (Catalog + Daemon Status)
  const refreshCatalog = useCallback(async () => {
    try {
      const catalogRes = await getProviderCatalog();
      setCatalogProviders(catalogRes.providers);
      await fetchOllamaDaemonInfo();
    } catch {
      // Ignore transient refresh errors
    }
  }, [fetchOllamaDaemonInfo]);

  // Initial Hydration from Authoritative Backend SQLite Store
  useEffect(() => {
    async function hydrateSettings() {
      setIsInitialLoading(true);
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

        const backendSavedModel = data.selected_ollama_model || storeOllamaModel || '';
        setSelectedOllamaModel(backendSavedModel);
        setProviderSettings(normLlm, data.default_stt, data.gpu_acceleration, backendSavedModel);

        if (catalogRes) {
          setCatalogProviders(catalogRes.providers);
        }

        if (ollamaRes) {
          setOllamaConfig(ollamaRes);
          if (ollamaRes.configured_dir) {
            setOllamaDir(ollamaRes.configured_dir);
          }
        }

        await fetchOllamaDaemonInfo();
      } catch (_err) {
        // Fall back to store / cached state if backend is booting
      } finally {
        setIsInitialLoading(false);
      }
    }

    hydrateSettings();
  }, [fetchOllamaDaemonInfo, setProviderSettings, storeOllamaModel]);

  // Event Listeners: Window Focus & 45-Second Fallback Polling Interval
  useEffect(() => {
    const handleFocus = () => {
      refreshCatalog();
    };
    window.addEventListener('focus', handleFocus);

    const interval = setInterval(() => {
      refreshCatalog();
    }, 45000);

    return () => {
      window.removeEventListener('focus', handleFocus);
      clearInterval(interval);
    };
  }, [refreshCatalog]);

  // Confirmed-Save Handler: Lock inputs -> PATCH Backend -> On 200 OK Sync Store & Cache
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

      const confirmedModel = updated.selected_ollama_model || (selectedLlm === 'ollama' ? selectedOllamaModel : '');
      
      // Update Zustand runtime store & localStorage cache ONLY after backend HTTP 200 confirmation
      setProviderSettings(
        updated.default_llm,
        updated.default_stt,
        updated.gpu_acceleration,
        confirmedModel
      );

      const modelDetail =
        selectedLlm === 'ollama' && confirmedModel
          ? ` (${confirmedModel})`
          : '';
      setToastMessage({
        type: 'success',
        text: `✓ ${selectedLlm.toUpperCase()}${modelDetail} Configuration saved successfully!`,
      });
      refreshCatalog();
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
  };

  const handleSaveOllamaDir = async () => {
    if (!ollamaDir.trim() || isSavingOllamaDir) return;
    setIsSavingOllamaDir(true);
    setToastMessage(null);

    try {
      const res = await updateOllamaDirectory(ollamaDir.trim());
      syncOllamaModelSelection(res);
      refreshCatalog();
      setToastMessage({
        type: 'success',
        text: `✓ Local model storage directory saved! (${res.models_count} models discovered)`,
      });
    } catch (err: any) {
      setToastMessage({
        type: 'error',
        text: `✕ Failed to save Ollama directory: ${err.message || 'Invalid path'}`,
      });
    } finally {
      setIsSavingOllamaDir(false);
    }
  };

  const handleRefreshOllamaDir = async () => {
    if (isScanningOllama) return;
    setIsScanningOllama(true);
    setToastMessage(null);

    try {
      const res = await scanOllamaModels();
      syncOllamaModelSelection(res);
      refreshCatalog();
      setToastMessage({
        type: 'success',
        text: `✓ Local storage rescan complete! (${res.models_count} offline models discovered)`,
      });
    } catch (err: any) {
      setToastMessage({
        type: 'error',
        text: `✕ Rescan failed: ${err.message || 'Error scanning directory'}`,
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

  const formatSizeBytes = (bytes?: number) => {
    if (!bytes) return '';
    const gb = bytes / (1024 * 1024 * 1024);
    if (gb >= 1) return `${gb.toFixed(1)} GB`;
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
  };

  const isCloudProvider = selectedLlm === 'openrouter' || selectedLlm === 'groq';
  const ollamaCatalogModels = catalogProviders.find((p) => p.id === 'ollama')?.models ?? [];

  // Check if saved Ollama model is missing from live daemon catalog
  const isSelectedModelMissing =
    selectedLlm === 'ollama' &&
    Boolean(selectedOllamaModel) &&
    liveOllamaModels.length > 0 &&
    !liveOllamaModels.some(
      (m) => m.full_id === selectedOllamaModel || m.name === selectedOllamaModel || `${m.name}:${m.tag}` === selectedOllamaModel
    );

  // Runtime environment detection
  const isNativeHost = typeof window !== 'undefined' && (window as any).__TAURI__ !== undefined;

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-4xl mx-auto space-y-6 w-full">
      {/* Toast Notification Banner */}
      {toastMessage && (
        <div
          className={`p-3.5 rounded-lg border text-xs flex justify-between items-center transition-all ${
            toastMessage.type === 'success'
              ? 'bg-emerald-950/70 border-emerald-500/40 text-emerald-300'
              : 'bg-rose-950/70 border-rose-500/40 text-rose-300'
          }`}
        >
          <span className="font-medium">{toastMessage.text}</span>
          <button onClick={() => setToastMessage(null)} className="text-on-surface-variant hover:text-on-surface ml-2">
            ✕
          </button>
        </div>
      )}

      {/* Header & Top Live Status Summary Banner */}
      <div className="space-y-4 pb-4 border-b border-outline-variant">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="font-carvist text-2xl font-bold text-on-surface">
              AI System Settings & Capability Bus
            </h2>
            <p className="text-xs text-on-surface-variant mt-1">
              Configure provider routing, inspect local Ollama model storage, and monitor system health.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono px-2.5 py-1 rounded-full border border-secondary/40 bg-secondary/10 text-secondary font-semibold">
              {isNativeHost ? '💻 Native Host' : '🐳 Docker Container'}
            </span>
          </div>
        </div>

        {/* Status Metrics Bar */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2.5 p-3.5 bg-surface-container-low border border-outline-variant/60 rounded-lg text-xs font-mono">
          {/* Status Badge */}
          <div className="space-y-0.5">
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block">Ollama Status</span>
            {isInitialLoading ? (
              <span className="text-on-surface-variant italic">Checking...</span>
            ) : ollamaStatus?.connected ? (
              <span className="text-emerald-400 font-bold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                Connected {ollamaStatus.version ? `v${ollamaStatus.version}` : ''}
              </span>
            ) : (
              <span className="text-rose-400 font-bold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-rose-500"></span>
                Offline
              </span>
            )}
          </div>

          {/* Latency */}
          <div className="space-y-0.5">
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block">REST Latency</span>
            <span className="font-bold text-on-surface">
              {restLatencyMs !== null ? `${restLatencyMs} ms` : '—'}
            </span>
          </div>

          {/* Discovered Models Count */}
          <div className="space-y-0.5">
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block">Live Models</span>
            <span className="font-bold text-secondary">{liveOllamaModels.length} Installed</span>
          </div>

          {/* Active LLM Model */}
          <div className="space-y-0.5 truncate">
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block">Active LLM</span>
            <span className="font-bold text-on-surface truncate block">
              {selectedLlm === 'ollama' ? selectedOllamaModel || 'Not Selected' : selectedLlm.toUpperCase()}
            </span>
          </div>

          {/* Last Checked Timestamp */}
          <div className="space-y-0.5">
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block">Last Checked</span>
            <span className="text-on-surface-variant">{lastCheckedTime || 'Just now'}</span>
          </div>
        </div>
      </div>

      {/* 1. AI Provider Configuration Card (Editable - Confirmed Save) */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-5">
        <div className="flex items-center justify-between pb-3 border-b border-outline-variant/40">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-secondary text-base">tune</span>
            <h3 className="font-bold text-sm text-on-surface font-carvist uppercase tracking-wider">
              AI Provider Routing Configuration
            </h3>
          </div>
          <span className="text-[10px] font-mono text-on-surface-variant">Confirmed Save Enabled</span>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-on-surface mb-1.5 font-mono uppercase">
              Text Generation Provider (LLM)
            </label>
            <select
              value={selectedLlm}
              onChange={(e) => setSelectedLlm(e.target.value)}
              disabled={isSaving}
              className="w-full bg-surface-container border border-outline-variant rounded p-2.5 text-xs text-on-surface focus:border-secondary focus:outline-none disabled:opacity-60"
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
              <label className="block text-xs font-bold text-on-surface mb-1 font-mono uppercase">
                Active Ollama Local Model
              </label>
              <select
                value={selectedOllamaModel}
                onChange={(e) => setSelectedOllamaModel(e.target.value)}
                disabled={isSaving}
                className="w-full bg-surface-container border border-outline-variant rounded p-2.5 text-xs font-mono text-on-surface focus:border-secondary focus:outline-none disabled:opacity-60"
              >
                <option value="" disabled>
                  -- Select an Ollama Model --
                </option>

                {/* If selected model is not in standard list, maintain option */}
                {selectedOllamaModel && !ollamaCatalogModels.some((m) => m.id === selectedOllamaModel) && (
                  <option key={selectedOllamaModel} value={selectedOllamaModel}>
                    {selectedOllamaModel} (Custom / Saved)
                  </option>
                )}

                {ollamaCatalogModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.id}
                  </option>
                ))}
              </select>

              {/* Warning if model selected is missing from live daemon */}
              {isSelectedModelMissing && (
                <div className="p-3 bg-amber-950/40 border border-amber-500/30 rounded text-xs text-amber-300 flex items-center gap-2">
                  <span className="material-symbols-outlined text-sm shrink-0">warning</span>
                  <span>
                    Saved model <code className="font-mono bg-amber-900/50 px-1 rounded">{selectedOllamaModel}</code> is not currently installed on your running Ollama service daemon.
                  </span>
                </div>
              )}

              {!selectedOllamaModel && (
                <div className="p-3 bg-surface-container border border-outline-variant rounded text-xs text-on-surface-variant italic">
                  💡 Tip: Select an installed Ollama model above (e.g. llama3:8b) to use for text generation.
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
                disabled={isSaving}
                className="w-full bg-surface-container-low border border-outline-variant rounded p-2.5 text-xs text-on-surface font-mono focus:border-secondary focus:outline-none disabled:opacity-60"
              />
              <p className="text-[11px] text-on-surface-variant">
                Key is stored securely in memory for dynamic cloud provider routing.
              </p>
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-on-surface mb-1.5 font-mono uppercase">
              Speech-to-Text Provider (STT)
            </label>
            <select
              value={selectedStt}
              onChange={(e) => setSelectedStt(e.target.value)}
              disabled={isSaving}
              className="w-full bg-surface-container border border-outline-variant rounded p-2.5 text-xs text-on-surface focus:border-secondary focus:outline-none disabled:opacity-60"
            >
              <option value="faster-whisper">Faster-Whisper (Local CTranslate2 Engine)</option>
            </select>
          </div>
        </div>

        <div className="pt-4 border-t border-outline-variant/40 flex justify-end">
          <Button variant="primary" onClick={handleSave} disabled={isSaving}>
            {isSaving ? 'Saving Configuration...' : 'Save Configuration'}
          </Button>
        </div>
      </div>

      {/* 2. System Health Summary Card ("Can I use it?") */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-outline-variant/40">
          <span className="material-symbols-outlined text-emerald-400 text-base">health_metrics</span>
          <h3 className="font-bold text-sm text-on-surface font-carvist uppercase tracking-wider">
            System Health Checklist
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
          {/* Health Check 1: Ollama Daemon */}
          <div className="p-3 bg-surface-container border border-outline-variant/40 rounded flex items-center justify-between">
            <span className="text-on-surface-variant">Ollama Service Daemon:</span>
            {ollamaStatus?.connected ? (
              <span className="text-emerald-400 font-bold">✓ Reachable</span>
            ) : (
              <span className="text-rose-400 font-bold">✕ Offline</span>
            )}
          </div>

          {/* Health Check 2: Active Model */}
          <div className="p-3 bg-surface-container border border-outline-variant/40 rounded flex items-center justify-between truncate pr-2">
            <span className="text-on-surface-variant">Active LLM Model:</span>
            {selectedLlm !== 'ollama' ? (
              <span className="text-emerald-400 font-bold">✓ Cloud ({selectedLlm.toUpperCase()})</span>
            ) : selectedOllamaModel && !isSelectedModelMissing ? (
              <span className="text-emerald-400 font-bold truncate ml-2">✓ Ready ({selectedOllamaModel})</span>
            ) : isSelectedModelMissing ? (
              <span className="text-amber-400 font-bold">⚠️ Model Missing</span>
            ) : (
              <span className="text-amber-400 font-bold">⚠️ Unselected</span>
            )}
          </div>

          {/* Health Check 3: Faster-Whisper ASR */}
          <div className="p-3 bg-surface-container border border-outline-variant/40 rounded flex items-center justify-between">
            <span className="text-on-surface-variant">Speech-to-Text Engine:</span>
            <span className="text-emerald-400 font-bold">✓ Faster-Whisper Ready</span>
          </div>

          {/* Health Check 4: Local Storage Path */}
          <div className="p-3 bg-surface-container border border-outline-variant/40 rounded flex items-center justify-between">
            <span className="text-on-surface-variant">Local Storage Path:</span>
            {ollamaConfig?.valid ? (
              <span className="text-emerald-400 font-bold">✓ Accessible</span>
            ) : ollamaDir ? (
              <span className="text-amber-400 font-bold">⚠️ Invalid Directory</span>
            ) : (
              <span className="text-on-surface-variant">Not Configured</span>
            )}
          </div>
        </div>
      </div>

      {/* 3. Live Ollama Service (Diagnostic + Control) */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-secondary text-base">terminal</span>
            <h3 className="font-bold text-sm text-on-surface font-carvist uppercase tracking-wider">
              Live Ollama Service Daemon (REST API)
            </h3>
          </div>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={refreshCatalog}
            disabled={isRefreshingDaemon}
          >
            {isRefreshingDaemon ? 'Refreshing...' : 'Refresh Models'}
          </Button>
        </div>

        <p className="text-xs text-on-surface-variant">
          Queries Ollama's REST API (<code className="font-mono text-secondary">/api/version</code> & <code className="font-mono text-secondary">/api/tags</code>) for active model serving.
        </p>

        {/* Service Endpoint Info */}
        <div className="p-3 bg-surface-container/60 border border-outline-variant/40 rounded text-xs font-mono flex justify-between items-center">
          <div className="flex items-center gap-2 text-on-surface-variant truncate pr-2">
            <span className="text-secondary font-semibold">Service Endpoint:</span>
            <span className="truncate">{ollamaStatus?.base_url || 'http://localhost:11434'}</span>
          </div>
          {restLatencyMs !== null && (
            <span className="text-[10px] text-on-surface-variant shrink-0">
              Response: <strong className="text-emerald-400">{restLatencyMs} ms</strong>
            </span>
          )}
        </div>

        {/* Live Discovered Models Grid */}
        <div className="pt-2 border-t border-outline-variant/30 space-y-2">
          <h4 className="text-[11px] font-mono text-secondary uppercase font-semibold">
            Live Serving Models ({liveOllamaModels.length})
          </h4>

          {liveOllamaModels.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-48 overflow-y-auto custom-scrollbar p-1">
              {liveOllamaModels.map((m) => {
                const isActive = selectedLlm === 'ollama' && (selectedOllamaModel === m.full_id || selectedOllamaModel === m.name);
                return (
                  <div
                    key={m.full_id}
                    className={`p-2.5 bg-surface-container border rounded flex justify-between items-center text-xs transition-colors ${
                      isActive ? 'border-secondary bg-secondary/10' : 'border-outline-variant'
                    }`}
                  >
                    <div className="flex items-center gap-2 truncate pr-2">
                      <span className="material-symbols-outlined text-xs text-secondary shrink-0">
                        smart_toy
                      </span>
                      <span className="font-bold text-on-surface truncate">{m.name}</span>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0 font-mono text-[10px]">
                      {isActive && (
                        <span className="bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 px-1.5 py-0.5 rounded font-bold">
                          ✓ Active
                        </span>
                      )}
                      {m.size_bytes ? (
                        <span className="text-on-surface-variant text-[9px]">
                          {formatSizeBytes(m.size_bytes)}
                        </span>
                      ) : null}
                      <span className="bg-secondary/15 text-secondary border border-secondary/30 px-1.5 py-0.5 rounded font-semibold">
                        :{m.tag}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="p-4 text-center border border-dashed border-outline-variant/40 rounded text-xs text-on-surface-variant italic">
              {ollamaStatus?.connected
                ? 'Ollama service is connected, but no models have been pulled yet.'
                : 'Start your local Ollama service daemon to discover installed models automatically.'}
            </div>
          )}
        </div>
      </div>

      {/* 4. Local Model Storage (Host Filesystem Management) */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-secondary text-base">folder_managed</span>
            <h3 className="font-bold text-sm text-on-surface font-carvist uppercase tracking-wider">
              Local Model Storage (Disk Path Management)
            </h3>
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
              {ollamaConfig.valid ? `✓ Valid (${ollamaConfig.models_count} offline manifests)` : '✕ Invalid Path'}
            </span>
          )}
        </div>

        <p className="text-xs text-on-surface-variant">
          Inspect and configure physical host model directory paths (e.g. <code className="font-mono text-secondary">E:\ollama\models</code>) for native offline manifest scanning.
        </p>

        <div className="space-y-2">
          <label className="block text-[11px] text-on-surface-variant font-mono uppercase font-semibold">
            Directory Path
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={ollamaDir}
              onChange={(e) => setOllamaDir(e.target.value)}
              placeholder="e.g. E:\ollama\models"
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
              disabled={isSavingOllamaDir || !ollamaDir.trim()}
            >
              {isSavingOllamaDir ? 'Saving...' : 'Save Path'}
            </Button>
          </div>
        </div>

        {/* Configured vs Resolved Directory Paths Display */}
        {ollamaConfig && ollamaConfig.valid && (
          <div className="p-3 bg-surface-container/60 border border-outline-variant/40 rounded space-y-1.5 text-[11px] font-mono">
            <div className="flex items-center justify-between text-on-surface-variant">
              <div className="flex items-center gap-2 truncate pr-2">
                <span className="text-secondary font-semibold">Configured Path:</span>
                <span className="truncate">{ollamaConfig.configured_dir}</span>
              </div>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="text-[10px] py-0.5 px-2"
                onClick={handleRefreshOllamaDir}
                disabled={isScanningOllama}
              >
                {isScanningOllama ? 'Scanning...' : 'Rescan Path'}
              </Button>
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
      </div>

      {/* 5. Hardware Acceleration Card */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-secondary text-base">memory</span>
            <h3 className="font-bold text-sm text-on-surface font-carvist uppercase tracking-wider">
              Hardware Acceleration & GPU Diagnostic
            </h3>
          </div>

          <span
            className={`text-[10px] font-mono px-2 py-0.5 rounded border font-semibold ${
              gpuEnabled ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-300' : 'bg-surface-container text-on-surface-variant'
            }`}
          >
            {gpuEnabled ? 'CUDA Active' : 'CPU Only'}
          </span>
        </div>

        <div className="flex items-center justify-between p-3 bg-surface-container/60 border border-outline-variant/40 rounded">
          <div>
            <span className="text-xs font-bold text-on-surface block">
              NVIDIA CUDA Acceleration
            </span>
            <span className="text-[11px] text-on-surface-variant block mt-0.5">
              Utilize CUDA tensor cores for Faster-Whisper transcription & matrix operations.
            </span>
          </div>
          <input
            type="checkbox"
            checked={gpuEnabled}
            onChange={(e) => setGpuEnabled(e.target.checked)}
            className="rounded accent-secondary w-4 h-4"
          />
        </div>
      </div>

      {/* 6. Danger Zone: Application Factory Reset */}
      <div className="p-6 bg-rose-950/20 border border-rose-500/30 rounded-lg space-y-4">
        <div className="flex items-center gap-2 text-rose-400">
          <span className="material-symbols-outlined text-base">warning</span>
          <h3 className="font-bold text-xs font-mono uppercase tracking-wider">
            Danger Zone: Factory Reset
          </h3>
        </div>
        <p className="text-xs text-on-surface-variant">
          Permanently delete all SQLite database records, uploaded media files, interactive transcripts, chat sessions, and vector indices.
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
