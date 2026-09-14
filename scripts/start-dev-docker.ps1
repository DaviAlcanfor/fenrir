# Dev launcher, Docker variant: same as start-dev.ps1 but runs HexStrike in a
# local Docker container (via ../docker-compose.yml) instead of WSL — use this
# if you don't have/want a WSL Kali distro set up. Requires Docker Desktop.

$ErrorActionPreference = "Stop"

$FenrirRoot = Split-Path $PSScriptRoot -Parent
$PyScripts = Join-Path $env:APPDATA "Python\Python313\Scripts"  # uv + ripgrep live here

Write-Host "Building/starting HexStrike AI server (:8888, Docker)..."
Set-Location $FenrirRoot
docker compose up --build -d hexstrike

Write-Host "Starting fenrir-api (:8000)..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "`$env:PATH = '$PyScripts;' + `$env:PATH; Set-Location '$FenrirRoot'; uv run fenrir-api"
)

Write-Host "Starting web frontend (:3000)..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$FenrirRoot\web'; npm run dev -- --port 3000 --strictPort"
)

Write-Host "HexStrike running in Docker (docker compose logs -f hexstrike to watch it)."
Write-Host "fenrir-api and the web UI launched in their own windows."
