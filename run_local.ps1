# FORGE-Vision — Local Development Runner (no Docker)
# Starts FastAPI backend and React (Vite) frontend in separate PowerShell windows.
# Usage: double-click run_local.bat  OR  .\run_local.ps1

$root = $PSScriptRoot

Write-Host ""
Write-Host " FORGE-Vision Local Startup"
Write-Host " ==========================="
Write-Host ""

# ── Verify .env ───────────────────────────────────────────────────────────────
if (-not (Test-Path "$root\.env")) {
    Copy-Item "$root\.env.example" "$root\.env"
    Write-Host " WARNING: .env created from .env.example."
    Write-Host "          Add your API keys in .env, then re-run."
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Check Python ──────────────────────────────────────────────────────────────
try { $null = & python --version 2>&1 } catch {
    Write-Host " ERROR: Python not found on PATH."
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Check Node ────────────────────────────────────────────────────────────────
try { $null = & node --version 2>&1 } catch {
    Write-Host " ERROR: Node.js not found on PATH."
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Start FastAPI backend ─────────────────────────────────────────────────────
Write-Host " [1/3] Starting FastAPI backend  ->  http://localhost:8000"
$apiScript = @"
`$host.UI.RawUI.WindowTitle = 'FORGE-Vision API'
Set-Location '$root'
`$env:PYTHONPATH = '$root'
`$env:PYTHONUTF8 = '1'
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
"@
Start-Process powershell -ArgumentList "-NoExit -Command $apiScript"

# Give the API a few seconds to initialise before the UI services start
Start-Sleep 4

# ── Start Streamlit dashboard ─────────────────────────────────────────────────
Write-Host " [2/3] Starting Streamlit dashboard  ->  http://localhost:8501"
$streamlitScript = @"
`$host.UI.RawUI.WindowTitle = 'FORGE-Vision Streamlit'
Set-Location '$root'
`$env:PYTHONPATH = '$root'
`$env:PYTHONUTF8 = '1'
`$env:API_BASE_URL = 'http://localhost:8000'
streamlit run src/ui/app.py --server.port 8501 --server.address 127.0.0.1 --server.headless true
"@
Start-Process powershell -ArgumentList "-NoExit -Command $streamlitScript"

Start-Sleep 2

# ── Start React / Vite frontend ───────────────────────────────────────────────
Write-Host " [3/3] Starting React (Vite) frontend  ->  https://localhost:5173"
$frontendScript = @"
`$host.UI.RawUI.WindowTitle = 'FORGE-Vision React'
Set-Location '$root\frontend'
npm run dev
"@
Start-Process powershell -ArgumentList "-NoExit -Command $frontendScript"

Write-Host ""
Write-Host " ┌──────────────────────────────────────────────────┐"
Write-Host " │  Service             URL                          │"
Write-Host " │  ────────────────    ──────────────────────────── │"
Write-Host " │  React (login/reg)   https://localhost:5173       │"
Write-Host " │  Streamlit (app)     http://localhost:8501        │"
Write-Host " │  FastAPI             http://localhost:8000        │"
Write-Host " │  API Docs            http://localhost:8000/docs   │"
Write-Host " └──────────────────────────────────────────────────┘"
Write-Host ""
Write-Host " Close each PowerShell window to stop that service."
Write-Host ""
Read-Host "Press Enter to close this window"
