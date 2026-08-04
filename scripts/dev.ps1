# Athenus development stack.
#   ./scripts/dev.ps1          -> CPU stack (default)
#   ./scripts/dev.ps1 --gpu    -> GPU-accelerated stack (NVIDIA Container Toolkit)
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Host "Created .env from .env.example"
}

if ($args[0] -eq "--gpu") {
    Write-Host "Starting GPU-accelerated development stack..."
    docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
} else {
    Write-Host "Starting CPU development stack..."
    docker compose up -d --build
}

Write-Host ""
Write-Host "Web app:      http://localhost:3000"
Write-Host "Backend API:  http://localhost:8000/api/v1"
Write-Host "Ollama:       http://localhost:11434"
