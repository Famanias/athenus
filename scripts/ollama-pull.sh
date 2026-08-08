#!/usr/bin/env bash
# Athenus — pull the default Ollama model into the running container.
# Usage:
#   ./scripts/ollama-pull.sh               # pull DEFAULT_LLM_MODEL (dev stack)
#   ./scripts/ollama-pull.sh --prod        # pull into the production stack
#   ./scripts/ollama-pull.sh <model>       # pull a specific model
set -euo pipefail
cd "$(dirname "$0")/.."

# Resolve the model to pull: explicit arg > .env DEFAULT_LLM_MODEL > llama3:8b
MODEL="${1:-}"
if [[ "${1:-}" == "--prod" ]]; then
    STACK="prod"
    MODEL="${2:-}"
    CONTAINER="athenus-prod-ollama"
else
    STACK="dev"
    CONTAINER="athenus-ollama"
fi

if [ -z "$MODEL" ]; then
    MODEL="$(grep -E '^DEFAULT_LLM_MODEL=' .env 2>/dev/null | tail -n1 | cut -d'=' -f2 | tr -d '"' || true)"
    MODEL="${MODEL:-llama3:8b}"
fi

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "ERROR: container '${CONTAINER}' is not running. Start the stack first:" >&2
    if [ "$STACK" == "prod" ]; then
        echo "  docker compose -f docker-compose.prod.yml up -d" >&2
    else
        echo "  ./scripts/dev.sh   (or: docker compose up -d)" >&2
    fi
    exit 1
fi

echo "Pulling '${MODEL}' into container '${CONTAINER}' (${STACK} stack)..."
docker exec -it "${CONTAINER}" ollama pull "${MODEL}"

echo
echo "Done. The backend reaches this Ollama via OLLAMA_BASE_URL=http://ollama:11434."
echo "Models are discoverable at GET http://localhost:11434/api/tags."
