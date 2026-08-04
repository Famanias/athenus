# Athenus setup: creates .env from .env.example if missing.
$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root ".env"

if (-not (Test-Path -LiteralPath $envPath)) {
    Copy-Item -LiteralPath (Join-Path $root ".env.example") -Destination $envPath
    Write-Host "Created .env from .env.example"
} else {
    Write-Host ".env already exists"
}
