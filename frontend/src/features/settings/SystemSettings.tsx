'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/Button';

export const SystemSettings: React.FC = () => {
  const [llmProvider, setLlmProvider] = useState<string>('ollama');
  const [sttProvider, setSttProvider] = useState<string>('faster-whisper');
  const [gpuAcceleration, setGpuAcceleration] = useState<boolean>(true);

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-3xl mx-auto space-y-6 w-full">
      {/* Header */}
      <div className="pb-4 border-b border-outline-variant">
        <h2 className="font-carvist text-2xl font-bold text-on-surface">
          AI Models & Capability Bus Providers
        </h2>
        <p className="text-xs text-on-surface-variant mt-1">
          Configure local vs cloud model routing, hardware acceleration, and vector database indices.
        </p>
      </div>

      {/* Model Form */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-6">
        <div>
          <label className="block text-xs font-bold text-on-surface mb-2 font-mono uppercase">
            Text Generation Provider (LLM)
          </label>
          <select
            value={llmProvider}
            onChange={(e) => setLlmProvider(e.target.value)}
            className="w-full bg-surface-container border border-outline-variant rounded p-2.5 text-xs text-on-surface focus:border-secondary focus:outline-none"
          >
            <option value="ollama">Ollama (Local - llama3:8b)</option>
            <option value="groq">Groq API (Cloud Hybrid)</option>
            <option value="openrouter">OpenRouter / Gemini / Claude</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-bold text-on-surface mb-2 font-mono uppercase">
            Speech-to-Text Provider (STT)
          </label>
          <select
            value={sttProvider}
            onChange={(e) => setSttProvider(e.target.value)}
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
            checked={gpuAcceleration}
            onChange={(e) => setGpuAcceleration(e.target.checked)}
            className="rounded accent-secondary w-4 h-4"
          />
        </div>

        <div className="pt-4 border-t border-outline-variant/40 flex justify-end">
          <Button variant="primary">Save Configuration</Button>
        </div>
      </div>
    </div>
  );
};
