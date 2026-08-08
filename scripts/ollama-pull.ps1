# Athenus — pull the default Ollama model into the running container.
# Usage:
#   ./scripts/ollama-pull.ps1              # pull DEFAULT_LLM_MODEL (dev stack)
#   ./scripts/ollama-pull.ps1 --prod       # pull into the production stack
#   ./scripts/ollama-pull.ps1 <model>      # pull a specific model
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$stack = "dev"
$container = "athenus-ollama"
$model = $null

if ($args[0] -eq "--prod") {
    $stack = "prod"
    $container = "athenus-prod-ollama"
    $model = $args[1]
} else {
    $model = $args[0]
}

if (-not $model) {
    $envModel = $null
    if (Test-Path -LiteralPath ".env") {
        $line = Select-String -LiteralPath ".env" -Pattern "^DEFAULT_LLM_MODEL=" | Select-Object -Last 1
        if ($line) { $envModel = $line.Line -replace "^DEFAULT_LLM_MODEL=", "" -replace '"', "" }
    }
    $model = if ($envModel) { $envModel } else { "llama3:8b" }
}

$running = docker ps --format "{{.Names}}"
if ($running -notmatch [regex]::Escape($container)) {
    Write-Host "ERROR: container '$container' is not running. Start the stack first:" -ForegroundColor Red
    if ($stack -eq "prod") {
        Write-Host "  docker compose -f docker-compose.prod.yml up -d"
    } else {
        Write-Host "  ./scripts/dev.ps1   (or: docker compose up -d)"
    }
    exit 1
}

Write-Host "Pulling '$model' into container '$container' ($stack stack)..."
docker exec -it $container ollama pull $model

Write-Host ""
Write-Host "Done. The backend reaches this Ollama via OLLAMA_BASE_URL=http://ollama:11434."
Write-Host "Models are discoverable at GET http://localhost:11434/api/tags."
