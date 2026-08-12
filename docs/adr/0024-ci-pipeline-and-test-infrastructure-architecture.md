# ADR 0024: CI Pipeline & Test Infrastructure Architecture

## Status
Accepted

## Context
Athenus is a local-first AI Knowledge OS monorepo comprising a Next.js/React frontend, FastAPI Python backend, and Tauri Rust desktop shell. As the codebase grew across RAG remediation, document ingestion, and provider management phases, automated regression prevention via Continuous Integration (CI) was required.

In implementing CI, two primary platform issues emerged on GitHub Actions runners (`ubuntu-latest` / Ubuntu 24.04):
1. **Tauri v1 Linux System Dependency Missing Package**: Tauri v1 (`@tauri-apps/cli` 1.5, `Cargo.lock` with `webkit2gtk-sys` 0.18) links against `webkit2gtk-4.0`. Modern `ubuntu-latest` runner images (Ubuntu 24.04 noble) no longer package `libwebkit2gtk-4.0-dev` in standard repositories.
2. **Backend Database Test Baseline Isolation**: `test_system_clear_data_factory_reset` required initializing legacy table structures (`document_pages`) when verifying transaction-wide purges on fresh clean database instances.

## Alternatives Considered

1. **Migrate Desktop Shell to Tauri v2**: Upgrade to Tauri v2 to use `libwebkit2gtk-4.1-dev`. *Rejected*: Introduces significant breaking application and Rust API changes across the desktop shell out of scope for CI pipeline infrastructure.
2. **Disable Tauri Build in CI**: Omit desktop compilation checks from CI. *Rejected*: Leaves desktop Rust/C++ binding regressions undetected.

## Architectural Decisions

### 1. Three-Job Matrix GitHub Actions Workflow (`ci.yml`)
Implemented `.github/workflows/ci.yml` with three independent jobs:
- **`frontend`** (`ubuntu-latest`): Node 22, npm cache, `npm ci`, TypeScript typecheck (`tsc --noEmit`), static export build (`next build`).
- **`backend`** (`ubuntu-latest`): Python 3.11, pip cache, `pip install -r requirements.txt`, `mkdir -p data`, `python -m pytest tests`.
- **`tauri`** (`ubuntu-22.04`): Node 22 + Rust stable toolchain + `ubuntu-22.04` runner image pinning + `libwebkit2gtk-4.0-dev` apt dependencies, building `--bundles deb`.

### 2. Runner Pinning for Legacy GTK Compatibility (`ubuntu-22.04`)
Pinned the `tauri` CI job to `ubuntu-22.04` to guarantee native availability of `libwebkit2gtk-4.0-dev` without attempting unsafe package additions or breaking Tauri v1 linking invariants. Restricted bundle generation to `--bundles deb` to avoid FUSE/AppImage runner requirements.

### 3. Factory Reset & Migration Test Integrity (`test_system_clear_data.py`)
Standardized test fixture initialization in `test_system_clear_data_factory_reset` by dynamically ensuring table existence (`CREATE TABLE IF NOT EXISTS document_pages`) before executing legacy purge assertions.

## Consequences
- **Positive**: Reliable, fast, deterministic zero-secret CI pipeline running across frontend, backend (160 tests), and desktop shell on every push and PR to `main` and `v1`.
- **Negative**: The `tauri` job remains pinned to `ubuntu-22.04` until desktop shell migration to Tauri v2 occurs.
