# Dockerfile Optimization Plan: CPU-Only PyTorch Pre-installation

## Problem Summary
When building the backend Docker images (`docker/backend/Dockerfile.dev` and `docker/backend/Dockerfile`), `pip install -r requirements.txt` triggers an installation of `sentence-transformers`, which transitively depends on `torch`.

Because PyPI defaults to CUDA-enabled PyTorch wheels, `pip` downloads and extracts over **3.5 GB** of NVIDIA CUDA binaries (`nvidia-cublas`, `nvidia-cufft`, `nvidia-cusolver`, `nvidia-cusparse`, `nvidia-nvrtc`, `nvidia-cuda-runtime`, `triton`, etc.). This causes:
1. **BuildKit daemon crash (`rpc error: code = Unavailable desc = error reading from server: EOF`)** due to Out-Of-Memory (OOM) or disk space exhaustion on Docker/WSL.
2. Unnecessarily long build times (downloading gigabytes of unused CUDA wheels for a CPU container).
3. Image bloat (multi-gigabyte image layers).

## Proposed Solution
Mirror the existing pattern in [`docker/backend/Dockerfile.gpu`](file:///e:/repos/athenus/docker/backend/Dockerfile.gpu#L19-L23) by explicitly pre-installing the lightweight CPU wheel from the PyTorch index before running `pip install -r requirements.txt`.

This drops the PyTorch download size from ~3.5GB+ down to ~180MB, reduces memory usage during build by >80%, and eliminates all CUDA library downloads on CPU builds.

---

## Proposed Changes

### Backend Dockerfiles

#### [MODIFY] [docker/backend/Dockerfile.dev](file:///e:/repos/athenus/docker/backend/Dockerfile.dev)
- Insert CPU-only PyTorch pre-installation before installing `requirements.txt`:
```dockerfile
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r /tmp/requirements.txt
```

#### [MODIFY] [docker/backend/Dockerfile](file:///e:/repos/athenus/docker/backend/Dockerfile)
- Apply the same CPU PyTorch pre-installation in the production multi-stage build stage `runtime-deps`:
```dockerfile
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r /tmp/requirements.txt
```

---

## Verification Plan

### Automated / Build Verification
1. Test building the backend development image:
   ```bash
   docker compose build backend
   ```
2. Verify that `pip` downloads the lightweight CPU `torch` wheel (~180MB) and skips downloading `nvidia-*` / `triton` packages.
3. Test starting the container stack:
   ```bash
   docker compose up -d
   ```
4. Verify backend health:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```
