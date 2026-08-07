'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';
import {
  getProviderSettings,
  patchProviderSettings,
  getProviderCatalog,
  getLocalProviderStatus,
  getLocalProviderModels,
  testProviderConnection,
  clearAllData,
  ProviderCatalogProviderDTO,
  LocalProviderStatusDTO,
  CatalogModelDTO,
  TestConnectionResponse,
} from '@/services/settingsService';

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

export const SystemSettings: React.FC = () => {
  const { llmProvider, sttProvider, gpuAcceleration, activeModel: storeActiveModel, setProviderSettings, setActiveMediaId } = useAppStore();
  const [selectedLlm, setSelectedLlm] = useState<string>(llmProvider);
  const [selectedModel, setSelectedModel] = useState<string>(storeActiveModel);
  const [selectedStt, setSelectedStt] = useState<string>(sttProvider);
  const [gpuEnabled, setGpuEnabled] = useState<boolean>(gpuAcceleration);
  const [apiKey, setApiKey] = useState<string>('');

  // Autosave Status & Error Tracking
  const [saveStatus, setSaveStatus] = useState<SaveStatus>('idle');
  const [saveErrorMessage, setSaveErrorMessage] = useState<string | null>(null);

  // Diagnostic metrics & refresh tracking
  const [lastCheckedTime, setLastCheckedTime] = useState<string>('');
  const [restLatencyMs, setRestLatencyMs] = useState<number | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState<boolean>(true);

  // Live Ollama Daemon REST API State
  const [ollamaStatus, setOllamaStatus] = useState<LocalProviderStatusDTO | null>(null);
  const [liveOllamaModels, setLiveOllamaModels] = useState<CatalogModelDTO[]>([]);
  const [isRefreshingDaemon, setIsRefreshingDaemon] = useState<boolean>(false);

  // Connection Testing State
  const [isTestingConnection, setIsTestingConnection] = useState<boolean>(false);
  const [testResult, setTestResult] = useState<TestConnectionResponse | null>(null);

  const [catalogProviders, setCatalogProviders] = useState<ProviderCatalogProviderDTO[]>([]);

  // Danger Zone Reset state
  const [isResetModalOpen, setIsResetModalOpen] = useState<boolean>(false);
  const [confirmInputText, setConfirmInputText] = useState<string>('');
  const [isResetting, setIsResetting] = useState<boolean>(false);

  // Refs for tracking baseline saved values and preventing hydration race conditions
  const isHydratedRef = useRef<boolean>(false);
  const saveRequestIdRef = useRef<number>(0);

  const apiKeyDebounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  const lastSavedRef = useRef({
    llm: '',
    model: '',
    stt: '',
    gpu: false,
    apiKey: '',
  });

  const normalizeLlmProvider = (providerStr: string): string => {
    const p = (providerStr || '').toLowerCase();
    if (p.includes('groq')) return 'groq';
    if (p.includes('openrouter')) return 'openrouter';
    if (p.includes('openai')) return 'openai';
    if (p.includes('anthropic')) return 'anthropic';
    return p || 'ollama';
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
        const [data, catalogRes] = await Promise.all([
          getProviderSettings(),
          getProviderCatalog().catch(() => null),
        ]);

        const normLlm = normalizeLlmProvider(data.default_llm);
        setSelectedLlm(normLlm);
        setSelectedStt(data.default_stt);
        setGpuEnabled(data.gpu_acceleration);
        setApiKey(data.api_key || '');

        const backendSavedModel = data.selected_model || data.selected_ollama_model || storeActiveModel || '';
        setSelectedModel(backendSavedModel);
        setProviderSettings(normLlm, data.default_stt, data.gpu_acceleration, backendSavedModel);

        if (catalogRes) {
          setCatalogProviders(catalogRes.providers);
          if (catalogRes.active?.provider) {
            setSelectedLlm(catalogRes.active.provider);
            if (catalogRes.active.model) {
              setSelectedModel(catalogRes.active.model);
            }
          }
        }

        // Establish baseline of confirmed saved values to prevent spurious autosaves
        lastSavedRef.current = {
          llm: normLlm,
          model: backendSavedModel,
          stt: data.default_stt,
          gpu: data.gpu_acceleration,
          apiKey: data.api_key || '',
        };

        await fetchOllamaDaemonInfo();
      } catch (_err) {
        // Fall back to store / cached state if backend is booting
      } finally {
        setIsInitialLoading(false);
        setTimeout(() => {
          isHydratedRef.current = true;
        }, 150);
      }
    }

    hydrateSettings();
  }, [fetchOllamaDaemonInfo, setProviderSettings, storeActiveModel]);

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

  // Centralized Server Sync Handler for Core Settings
  const executeServerSync = useCallback(
    async (overrideValues?: {
      llm?: string;
      model?: string;
      stt?: string;
      gpu?: boolean;
      apiKey?: string;
    }) => {
      if (!isHydratedRef.current) return;

      // On a provider switch, never carry the previous provider's model into the new one
      const isProviderChange = !!overrideValues?.llm && overrideValues.llm !== selectedLlm;

      const currentValues = {
        llm: overrideValues?.llm ?? selectedLlm,
        model: isProviderChange ? '' : (overrideValues?.model ?? selectedModel),
        stt: overrideValues?.stt ?? selectedStt,
        gpu: overrideValues?.gpu ?? gpuEnabled,
        apiKey: overrideValues?.apiKey ?? apiKey,
      };

      // Skip save if values match current baseline
      const isUnchanged =
        currentValues.llm === lastSavedRef.current.llm &&
        currentValues.model === lastSavedRef.current.model &&
        currentValues.stt === lastSavedRef.current.stt &&
        currentValues.gpu === lastSavedRef.current.gpu &&
        currentValues.apiKey === lastSavedRef.current.apiKey;

      if (isUnchanged && saveStatus !== 'error') {
        return;
      }

      const requestId = ++saveRequestIdRef.current;
      setSaveStatus('saving');
      setSaveErrorMessage(null);

      try {
        const payload: Record<string, any> = {
          default_llm: currentValues.llm,
          selected_model: currentValues.model,
          default_stt: currentValues.stt,
          gpu_acceleration: currentValues.gpu,
        };
        if (currentValues.apiKey && currentValues.apiKey.trim()) {
          payload.api_key = currentValues.apiKey.trim();
        }

        const patchData = await patchProviderSettings(payload);

        if (requestId !== saveRequestIdRef.current) return;

        // Keep the local model mirror aligned with the server's per-provider selection
        const serverModel = patchData.selected_model || '';
        setSelectedModel(serverModel || currentValues.model);

        setProviderSettings(
          patchData.default_llm,
          patchData.default_stt,
          patchData.gpu_acceleration,
          serverModel || currentValues.model
        );

        lastSavedRef.current = {
          llm: patchData.default_llm,
          model: serverModel || currentValues.model,
          stt: patchData.default_stt,
          gpu: patchData.gpu_acceleration,
          apiKey: currentValues.apiKey,
        };

        setSaveStatus('saved');
        refreshCatalog();
        setTimeout(() => {
          if (saveRequestIdRef.current === requestId) {
            setSaveStatus('idle');
          }
        }, 2000);
      } catch (err: any) {
        if (requestId !== saveRequestIdRef.current) return;
        setSaveStatus('error');
        setSaveErrorMessage(err.message || 'Failed to update provider settings.');
      }
    },
    [apiKey, gpuEnabled, selectedLlm, selectedModel, selectedStt, setProviderSettings, saveStatus]
  );

  // Handler for LLM Provider Switch
  const handleLlmChange = (newVal: string) => {
    setSelectedLlm(newVal);
    setTestResult(null);
    executeServerSync({ llm: newVal });
  };

  // Handler for Active Model Switch
  const handleModelChange = (newVal: string) => {
    setSelectedModel(newVal);
    executeServerSync({ model: newVal });
  };

  // Handler for STT Provider Switch
  const handleSttChange = (newVal: string) => {
    setSelectedStt(newVal);
    executeServerSync({ stt: newVal });
  };

  // Handler for GPU Acceleration Toggle Switch
  const handleGpuToggle = (newVal: boolean) => {
    setGpuEnabled(newVal);
    executeServerSync({ gpu: newVal });
  };

  // Debounced API Key Change Handler
  const handleApiKeyChange = (newVal: string) => {
    setApiKey(newVal);
    if (apiKeyDebounceTimerRef.current) {
      clearTimeout(apiKeyDebounceTimerRef.current);
    }
    apiKeyDebounceTimerRef.current = setTimeout(() => {
      executeServerSync({ apiKey: newVal });
    }, 600);
  };

  // Manual Retry Handler for Autosave Failures
  const handleRetrySave = () => {
    executeServerSync();
  };

  // Interactive Test Connection Action Handler
  const handleTestConnection = async () => {
    setIsTestingConnection(true);
    setTestResult(null);
    try {
      const res = await testProviderConnection(selectedLlm);
      setTestResult(res);
    } catch (err: any) {
      setTestResult({
        provider_id: selectedLlm,
        is_available: false,
        is_configured: false,
        active_model: 'unknown',
        error: err.message || 'Connection test failed',
      });
    } finally {
      setIsTestingConnection(false);
    }
  };

  // Danger Zone Data Reset Handlers
  const handleOpenResetModal = () => {
    setIsResetModalOpen(true);
    setConfirmInputText('');
  };

  const handleConfirmReset = async () => {
    if (confirmInputText !== 'DELETE ATHENUS DATA') return;
    setIsResetting(true);

    try {
      await clearAllData();

      setActiveMediaId(null);
      if (typeof window !== 'undefined') {
        Object.keys(localStorage)
          .filter((k) => k.startsWith('athenus_'))
          .forEach((k) => localStorage.removeItem(k));
      }

      setIsResetModalOpen(false);
      setConfirmInputText('');
      setTimeout(() => {
        window.location.reload();
      }, 1000);
    } catch (_err) {
      // Ignore
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

  const activeProviderObj = catalogProviders.find((p) => p.id === selectedLlm);
  const activeModels = activeProviderObj?.models ?? [];
  const isCloudProvider = selectedLlm !== 'ollama';

  // Check if saved Ollama model is missing from live daemon catalog
  const isSelectedModelMissing =
    selectedLlm === 'ollama' &&
    Boolean(selectedModel) &&
    liveOllamaModels.length > 0 &&
    !liveOllamaModels.some(
      (m) => m.full_id === selectedModel || m.name === selectedModel || `${m.name}:${m.tag}` === selectedModel
    );

  // Runtime environment detection
  const isNativeHost = typeof window !== 'undefined' && (window as any).__TAURI__ !== undefined;

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-4xl mx-auto space-y-6 w-full">
      {/* Header & Top Live Status Summary Banner */}
      <div className="space-y-4 pb-4 border-b border-outline-variant">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="font-type-light text-2xl font-bold text-on-surface">
              AI System Settings & Capability Bus
            </h2>
            <p className="text-xs text-on-surface-variant mt-1">
              Configure provider routing, inspect credential health, and monitor system capabilities.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Live Autosave Status Indicator */}
            {saveStatus === 'saving' && (
              <div className="flex items-center gap-2 px-3 py-1 bg-indigo-950/70 border border-indigo-500/40 text-indigo-300 rounded-full text-xs font-mono font-medium animate-pulse">
                <span className="w-2 h-2 rounded-full bg-indigo-400 border-2 border-indigo-200"></span>
                <span>Saving...</span>
              </div>
            )}

            {saveStatus === 'saved' && (
              <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-950/70 border border-emerald-500/40 text-emerald-300 rounded-full text-xs font-mono font-medium">
                <span>✓ All changes saved</span>
              </div>
            )}

            {saveStatus === 'error' && (
              <div className="flex items-center gap-2 px-3 py-1 bg-rose-950/70 border border-rose-500/40 text-rose-300 rounded-full text-xs font-mono font-medium">
                <span>⚠️ {saveErrorMessage || 'Failed to save'}</span>
                <button
                  onClick={handleRetrySave}
                  className="underline hover:text-white font-bold ml-1 font-sans cursor-pointer"
                >
                  Retry
                </button>
              </div>
            )}

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
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block">Catalog Providers</span>
            <span className="font-bold text-secondary">{catalogProviders.length} Registered</span>
          </div>

          {/* Active LLM Model */}
          <div className="space-y-0.5 truncate">
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block">Active LLM</span>
            <span className="font-bold text-on-surface truncate block">
              {selectedLlm.toUpperCase()}
            </span>
          </div>

          {/* Last Checked Timestamp */}
          <div className="space-y-0.5">
            <span className="text-[10px] text-on-surface-variant uppercase tracking-wider block">Last Checked</span>
            <span className="text-on-surface-variant">{lastCheckedTime || 'Just now'}</span>
          </div>
        </div>
      </div>

      {/* 1. AI Provider Configuration Inspector Card */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-5">
        <div className="flex items-center justify-between pb-3 border-b border-outline-variant/40">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-secondary text-base">tune</span>
            <h3 className="font-bold text-sm text-on-surface font-type-light uppercase tracking-wider">
              AI Provider Routing Configuration
            </h3>
          </div>
          <span className="text-[10px] font-mono text-emerald-400 font-semibold flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            Hot-Swappable
          </span>
        </div>

        <div className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-bold text-on-surface font-mono uppercase">
                Text Generation Provider (LLM)
              </label>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleTestConnection}
                disabled={isTestingConnection}
                className="text-xs py-1 px-3"
              >
                {isTestingConnection ? '🧪 Testing...' : '🧪 Test Connection'}
              </Button>
            </div>

            <select
              value={selectedLlm}
              onChange={(e) => handleLlmChange(e.target.value)}
              className="w-full bg-surface-container border border-outline-variant rounded p-2.5 text-xs text-on-surface focus:border-secondary focus:outline-none"
            >
              {catalogProviders.length > 0 ? (
                catalogProviders.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label} {p.is_configured ? '🟢' : '⚪'}
                  </option>
                ))
              ) : (
                <>
                  <option value="ollama">Ollama (Local)</option>
                  <option value="openrouter">OpenRouter API (Cloud Universal)</option>
                  <option value="groq">Groq API (Cloud LPU)</option>
                  <option value="openai">OpenAI API</option>
                  <option value="anthropic">Anthropic Claude API</option>
                </>
              )}
            </select>
          </div>

          {/* Test Connection Result Banner */}
          {testResult && (
            <div
              className={`p-3.5 rounded border text-xs flex items-center justify-between ${
                testResult.is_available && testResult.is_configured
                  ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-950/40 border-rose-500/30 text-rose-300'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-base">
                  {testResult.is_available ? 'check_circle' : 'error'}
                </span>
                <span>
                  <strong>{selectedLlm.toUpperCase()}:</strong>{' '}
                  {testResult.is_available
                    ? `Available & Configured (Active Model: ${testResult.active_model})`
                    : testResult.error || 'Connection Unreachable'}
                </span>
              </div>
              <button
                onClick={() => setTestResult(null)}
                className="text-xs hover:text-white font-bold px-2 py-0.5 rounded"
              >
                ✕
              </button>
            </div>
          )}

          {/* Dynamic Active Model Selector Dropdown */}
          <div className="space-y-2">
            <label className="block text-xs font-bold text-on-surface mb-1 font-mono uppercase">
              Active Model Selection ({selectedLlm.toUpperCase()})
            </label>
            <select
              value={selectedModel || activeProviderObj?.active_model || ''}
              onChange={(e) => handleModelChange(e.target.value)}
              className="w-full bg-surface-container border border-outline-variant rounded p-2.5 text-xs font-mono text-on-surface focus:border-secondary focus:outline-none"
            >
              {activeModels.length > 0 ? (
                activeModels.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name || m.id} {m.size_bytes ? `(${formatSizeBytes(m.size_bytes)})` : ''}
                  </option>
                ))
              ) : (
                <option value="">-- Configured Default Model --</option>
              )}
            </select>

            {isSelectedModelMissing && (
              <div className="p-3 bg-amber-950/40 border border-amber-500/30 rounded text-xs text-amber-300 flex items-center gap-2">
                <span className="material-symbols-outlined text-sm shrink-0">warning</span>
                <span>
                  Saved model <code className="font-mono bg-amber-900/50 px-1 rounded">{selectedModel}</code> is not currently installed on your running Ollama service daemon.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 2. Registered Providers Credential Overview & Health Matrix */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-outline-variant/40">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-secondary text-base">shield_lock</span>
            <h3 className="font-bold text-sm text-on-surface font-type-light uppercase tracking-wider">
              Provider Credential & Capability Overview
            </h3>
          </div>
          <span className="text-[10px] font-mono text-on-surface-variant">Read-only Inspector</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {catalogProviders.map((p) => (
            <div
              key={p.id}
              className={`p-3.5 border rounded-lg flex flex-col justify-between space-y-2 ${
                p.id === selectedLlm
                  ? 'bg-surface-container border-secondary/50 ring-1 ring-secondary/30'
                  : 'bg-surface-container-low border-outline-variant/50'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-xs text-on-surface font-mono">{p.label}</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold ${
                    p.is_configured
                      ? 'bg-emerald-950/70 text-emerald-300 border border-emerald-500/40'
                      : 'bg-rose-950/70 text-rose-300 border border-rose-500/40'
                  }`}
                >
                  {p.is_configured ? '🟢 Configured' : '🔴 Key missing in .env'}
                </span>
              </div>

              <div className="text-[11px] font-mono text-on-surface-variant flex items-center justify-between">
                <span>Discovered Models: {p.models?.length ?? 0}</span>
                <span className="text-[10px] opacity-75">{p.is_local ? 'Local Daemon' : 'Cloud API'}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="p-3 bg-surface-container border border-outline-variant/60 rounded text-xs text-on-surface-variant flex items-start gap-2">
          <span className="material-symbols-outlined text-secondary text-base shrink-0 mt-0.5">info</span>
          <span>
            <strong>Credential Security Notice:</strong> API keys are loaded securely from process environment variables or your local <code className="font-mono bg-surface-container-high px-1 py-0.5 rounded text-secondary">.env</code> file. Changing the active provider takes effect instantly without server restarts.
          </span>
        </div>
      </div>

      {/* 3. Speech-to-Text & GPU Acceleration Controls */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-5">
        <div className="flex items-center justify-between pb-3 border-b border-outline-variant/40">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-secondary text-base">mic</span>
            <h3 className="font-bold text-sm text-on-surface font-type-light uppercase tracking-wider">
              Speech-to-Text & Compute Acceleration
            </h3>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-on-surface mb-1.5 font-mono uppercase">
              Speech-to-Text Provider (STT)
            </label>
            <select
              value={selectedStt}
              onChange={(e) => handleSttChange(e.target.value)}
              className="w-full bg-surface-container border border-outline-variant rounded p-2.5 text-xs text-on-surface focus:border-secondary focus:outline-none"
            >
              <option value="faster_whisper">Faster-Whisper (Local CPU/GPU Engine)</option>
              <option value="whisper_cpp">Whisper.cpp (Embedded C++ Engine)</option>
            </select>
          </div>

          <div className="flex items-center justify-between pt-2">
            <div>
              <span className="block text-xs font-bold text-on-surface font-mono uppercase">
                Hardware GPU Acceleration
              </span>
              <span className="text-[11px] text-on-surface-variant">
                Enable CUDA / Apple Silicon Metal acceleration for whisper & embeddings
              </span>
            </div>
            <button
              onClick={() => handleGpuToggle(!gpuEnabled)}
              className={`w-12 h-6 rounded-full transition-colors relative ${
                gpuEnabled ? 'bg-secondary' : 'bg-surface-container-high border border-outline-variant'
              }`}
            >
              <span
                className={`w-4 h-4 rounded-full bg-white absolute top-1 transition-transform ${
                  gpuEnabled ? 'right-1' : 'left-1'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* 4. Danger Zone Data Reset */}
      <div className="p-6 bg-rose-950/20 border border-rose-500/30 rounded-lg space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-bold text-sm text-rose-300 font-type-light uppercase tracking-wider">
              Danger Zone — Reset Application State
            </h3>
            <p className="text-xs text-rose-200/70 mt-0.5">
              Clear all SQLite databases, local vector stores, and application caches.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={handleOpenResetModal} className="border-rose-500/50 text-rose-300 hover:bg-rose-950/50">
            Reset All Data
          </Button>
        </div>
      </div>

      {/* Danger Zone Reset Confirmation Modal */}
      {isResetModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface-container-low border border-rose-500/50 rounded-lg p-6 max-w-md w-full space-y-4 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-400">
              <span className="material-symbols-outlined text-2xl">warning</span>
              <h4 className="font-bold text-lg font-type-light">Confirm Irreversible Reset</h4>
            </div>

            <p className="text-xs text-on-surface-variant leading-relaxed">
              This action will permanently delete all processed media items, transcripts, knowledge graph nodes, vector embeddings, and persistent settings.
            </p>

            <div className="space-y-2">
              <label className="block text-xs font-bold text-rose-300 font-mono">
                Type <code className="bg-rose-950 px-1 py-0.5 rounded">DELETE ATHENUS DATA</code> to confirm:
              </label>
              <input
                type="text"
                value={confirmInputText}
                onChange={(e) => setConfirmInputText(e.target.value)}
                placeholder="DELETE ATHENUS DATA"
                className="w-full bg-surface-container border border-rose-500/40 rounded p-2.5 text-xs font-mono text-rose-200 focus:outline-none focus:border-rose-400"
              />
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setIsResetModalOpen(false)}
                disabled={isResetting}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirmReset}
                disabled={confirmInputText !== 'DELETE ATHENUS DATA' || isResetting}
                className="bg-rose-600 hover:bg-rose-700 text-white"
              >
                {isResetting ? 'Deleting...' : 'Permanently Delete'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
