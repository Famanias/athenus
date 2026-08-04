#!/usr/bin/env bash
# Athenus setup: creates .env from .env.example if missing.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example"
else
    echo ".env already exists"
fi
