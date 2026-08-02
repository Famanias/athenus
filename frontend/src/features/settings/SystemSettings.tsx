'use client';

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';
import { getProviderSettings, saveProviderSettings } from '@/services/settingsService';

export const SystemSettings: React.FC = () => {
  const { llmProvider, sttProvider, gpuAcceleration, setProviderSettings } = useAppStore();
  const [selectedLlm, setSelectedLlm] = useState<string>(llmProvider);
  const [selectedStt, setSelectedStt] = useState<string>(sttProvider);
  const [gpuEnabled, setGpuEnabled] = useState<boolean>(gpuAcceleration);
  const [apiKey, setApiKey] = useState<string>('');
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    async function hydrateSettings() {
      try {
        const data = await getProviderSettings();
        setSelectedLlm(data.default_llm);
        setSelectedStt(data.default_stt);
        setGpuEnabled(data.gpu_acceleration);
        setApiKey(data.api_key || '');
        setProviderSettings(data.default_llm, data.default_stt, data.gpu_acceleration);
      } catch (_err) {
        // Fall back to store values
      }
    }
    hydrateSettings();
  }, [setProviderSettings]);

  const handleSave = async () => {
    setIsSaving(true);
    setToastMessage(null);

    try {
      const updated = await saveProviderSettings({
        default_llm: selectedLlm,
        default_stt: selectedStt,
        gpu_acceleration: gpuEnabled,
        api_key: apiKey,
      });

      setProviderSettings(updated.default_llm, updated.default_stt, updated.gpu_acceleration);
      setToastMessage({
        type: 'success',
        text: `✓ ${selectedLlm.toUpperCase()} Provider & API Key saved successfully!`,
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

  const isCloudProvider = selectedLlm === 'openrouter' || selectedLlm === 'groq';

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
          Configure local vs cloud model routing, dynamic API keys, and vector database indices.
        </p>
      </div>

      {/* Model Form */}
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
            <option value="ollama">Ollama (Local - llama3:8b)</option>
            <option value="groq">Groq API (Cloud LPU)</option>
            <option value="openrouter">OpenRouter API (Cloud Universal)</option>
          </select>
        </div>

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
    </div>
  );
};
