# Dev launcher: opens HexStrike, fenrir-api, and the web frontend each in
# their own PowerShell window so you can watch/Ctrl+C them independently.
#
# Assumes hexstrike-ai is cloned as a sibling of this repo (..\hexstrike-ai)
# and uv/ripgrep live in the standard per-user Python Scripts folder —
# adjust below if your layout differs.
#
# HexStrike itself runs inside WSL (kali-linux distro, venv at
# /root/hexstrike-env) so its 127 CLI tools — mostly Linux-only — actually
# resolve. It still serves on localhost:8888, reachable from Windows as usual.

$ErrorActionPreference = "Stop"

$FenrirRoot = Split-Path $PSScriptRoot -Parent
$HexstrikeRoot = Join-Path (Split-Path $FenrirRoot -Parent) "hexstrike-ai"
$PyScripts = Join-Path $env:APPDATA "Python\Python313\Scripts"  # uv + ripgrep live here

# Translate the Windows path to WSL's /mnt/<drive> form, e.g. C:\Users\X\hexstrike-ai -> /mnt/c/Users/X/hexstrike-ai
$HexstrikeRootWsl = "/mnt/" + $HexstrikeRoot.Substring(0, 1).ToLower() + $HexstrikeRoot.Substring(2).Replace("\", "/")

Write-Host "Starting HexStrike AI server (:8888, via WSL kali-linux)..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "wsl -d kali-linux -u root -- /root/hexstrike-env/bin/python '$HexstrikeRootWsl/hexstrike_server.py'"
)

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

Write-Host "All three launched in separate windows. Close a window (or Ctrl+C in it) to stop that piece."
