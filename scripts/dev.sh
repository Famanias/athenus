#!/usr/bin/env bash
# Athenus development stack.
#   ./scripts/dev.sh          -> CPU stack (default)
#   ./scripts/dev.sh --gpu    -> GPU-accelerated stack (NVIDIA Container Toolkit)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
fi

if [[ "${1:-}" == "--gpu" ]]; then
    echo "Starting GPU-accelerated development stack..."
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
else
    echo "Starting CPU development stack..."
    docker compose up -d --build
fi

echo
echo "Web app:      http://localhost:47734"
echo "Backend API:  http://localhost:8000/api/v1"
echo "Ollama:       http://localhost:11434"
