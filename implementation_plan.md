# Implementation Plan: Milestone 1 — Fix Docker Directory Detection Regression

---

## 1. Executive Summary

This plan defines **Milestone 1**, a targeted, low-risk implementation focused strictly on fixing the **Docker Path Resolution & Directory Detection Regression** in Athenus without scope creep or UI redesign.

### Scope for Milestone 1
- **Platform Runtime Detection (`RuntimeService`)**: Centralize environment detection (`NATIVE`, `DOCKER`, `TAURI`, `WEB`) in `app/core/runtime.py`.
- **Decoupled Filesystem Validation (`FilesystemService`)**: Create `app/services/filesystem_service.py` to handle path normalization and container boundary detection.
- **Fix Path Mangling**: Prevent POSIX `os.path.abspath` from converting Windows drive letters (`E:\...`) into relative paths under container working directory (`/app/E:\...`).
- **User-Friendly Messaging**: Return friendly, non-technical guidance when unmounted host paths are selected in Docker.
- **Single-Responsibility Scanner**: Refactor `OllamaModelScanner` to delegate path validation to `FilesystemService`.
- **Optional Bind Mount Support**: Document optional host volume bind mounts in `docker-compose.yml` (`- E:\ollama\models:/mnt/ollama`).

*(Future provider refactoring and UI redesigns are deferred to Milestone 2).*

---

## 2. Proposed Changes

### [Component 1] Platform Runtime Service

#### [NEW] [runtime.py](file:///e:/repos/athenus/backend/app/core/runtime.py)
- Defines `RuntimeEnvironment` enum (`NATIVE`, `DOCKER`, `TAURI`, `WEB`).
- Implements `RuntimeService` with helper properties:
  - `is_docker`: Checks for `.dockerenv` file or `ATHENUS_RUNTIME=docker` environment variable.
  - `is_native`: `True` when running directly on host OS.
  - `can_access_host_filesystem`: Returns `True` for Native, `False` for Docker (unless mounted).

#### [NEW] [test_runtime_service.py](file:///e:/repos/athenus/backend/tests/test_runtime_service.py)
- Unit tests verifying runtime detection under simulated environments.

---

### [Component 2] Filesystem Service & Path Resolution

#### [NEW] [filesystem_service.py](file:///e:/repos/athenus/backend/app/services/filesystem_service.py)
- Consumes `RuntimeService`.
- Implements `validate_and_normalize_path(raw_path: str) -> str`:
  - Detects Windows drive letters (`^[a-zA-Z]:[\\/]`).
  - If running in Docker (`runtime.is_docker`) and presented with an unmounted host Windows path, raises `HostPathInaccessibleError` with friendly messaging:
    > *"The selected folder exists on your Windows computer, but the backend is currently running inside Docker and cannot access it.\n\nTo scan this folder, either:\n• Mount the folder into Docker in docker-compose.yml (e.g. - E:\ollama\models:/mnt/ollama)\n• Run the backend natively."*
  - On valid local paths, uses `os.path.abspath()` safely.

#### [MODIFY] [ollama_scanner.py](file:///e:/repos/athenus/backend/app/services/ollama_scanner.py)
- Refactor `OllamaModelScanner` to delegate path normalization and existence checks to `FilesystemService`.

---

### [Component 3] Documentation & Infrastructure

#### [MODIFY] [DEPLOYMENT.md](file:///e:/repos/athenus/docs/DEPLOYMENT.md)
- Document native host path scanning behavior vs optional Docker Compose volume bind mounts (`- E:\ollama\models:/mnt/ollama`).

---

## 3. Step-by-Step Implementation Phases

### Phase 1: Create `RuntimeService` (`app/core/runtime.py`)
- [ ] Implement `RuntimeEnvironment` enum and `RuntimeService`.
- [ ] Add unit tests in `tests/test_runtime_service.py`.

### Phase 2: Create `FilesystemService` (`app/services/filesystem_service.py`)
- [ ] Implement `FilesystemService` consuming `RuntimeService`.
- [ ] Add Windows drive letter detection and friendly Docker error guidance.
- [ ] Add unit tests for `FilesystemService`.

### Phase 3: Refactor `OllamaModelScanner` (`app/services/ollama_scanner.py`)
- [ ] Update `normalize_and_validate_path()` in `OllamaModelScanner` to delegate to `FilesystemService`.
- [ ] Verify existing backend test suite (`python -m pytest tests`).

### Phase 4: Documentation & Final Verification
- [ ] Update `docs/DEPLOYMENT.md`.
- [ ] Verify Native Desktop (Tauri) flow with host path `E:\ollama\models`.
- [ ] Verify Docker backend flow displays friendly error guidance instead of `/app/E:\...`.

---

## 4. Verification Plan

### Automated Tests
- `python -m pytest tests/test_runtime_service.py`
- `python -m pytest tests/test_ollama_scanner.py`
- `python -m pytest tests/` (full suite regression check)

### Manual Verification Matrix
1. **Native Desktop Mode (Tauri)**:
   - Save path `E:\ollama\models`.
   - Verify `OllamaModelScanner` scans host folder directly and returns discovered models.
2. **Docker Backend Mode**:
   - Save unmounted host path `E:\ollama\models`.
   - Verify Settings UI displays friendly error message: *"The selected folder exists on your Windows computer, but the backend is currently running inside Docker and cannot access it..."*
   - Verify raw path mangling `/app/E:\...` is completely eliminated.
