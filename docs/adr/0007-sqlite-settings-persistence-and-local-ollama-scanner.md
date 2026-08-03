# ADR 0007: SQLite System Settings Persistence & Pure Local Filesystem Model Scanner

## Context
Application settings (Ollama models directory, default LLM provider, selected local model, STT provider, GPU acceleration) were previously stored in a volatile in-memory dictionary. Backend process restarts reset settings back to static defaults. Additionally, discovering local Ollama models required a robust approach independent of daemon HTTP availability.

## Decision
1. **Single Source of Truth in SQLite**: Store all persistent system configuration in the application's canonical SQLite database (`./data/athenus.db`) inside a dedicated `system_settings` table (`SystemSettings` model).
2. **Dedicated `SettingsService`**: Access settings through a domain service (`SettingsService`) with explicit lifespan startup initialization in `app/main.py`.
3. **Pure Filesystem Model Scanner (`OllamaModelScanner`)**: Discover local Ollama models by scanning directory structures (`.ollama/models/manifests`) directly from the filesystem without HTTP API dependencies. Normalize user paths forgivingly (`.ollama` $\rightarrow$ `.ollama/models`).
4. **App-Wide Frontend Rehydration**: Rehydrate provider and local model settings during application boot in `DesktopShell.tsx`.
5. **Graceful Error Handling**: Preserve configured path strings in SQLite even when unmounted or invalid, flagging `valid: False` with descriptive error details without clearing user preferences.

## Status
Accepted and Implemented (`v1.0`).

## Rationale
- **Zero Storage Fragmentation**: Prevents introducing duplicate configuration files (`settings.json`) alongside SQLite.
- **Resilience**: Operates without external networking or running Ollama daemons.
- **Security & Scope**: Separates application settings from API credential management.

## Trade-offs
- File system scanning assumes standard Ollama model directory layouts; custom layout overrides require exact folder selection.
