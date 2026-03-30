# start-https.ps1 — Run backend (HTTPS) + Streamlit (HTTPS) on Windows
#
# Usage:
#   .\start-https.ps1
#   .\start-https.ps1 -BackendPort 9443 -FrontendPort 8443
#
# Pre-requisites:
#   certs\cert.pem and certs\key.pem must exist.
#   Run: python -m scripts.gen_cert   to create them.

param(
    [int]$BackendPort  = 9443,
    [int]$FrontendPort = 8443
)

$Cert = "certs\cert.pem"
$Key  = "certs\key.pem"

# ── Generate cert if missing ───────────────────────────────────────────────────
if (-not (Test-Path $Cert) -or -not (Test-Path $Key)) {
    Write-Host "Cert not found. Generating self-signed cert …" -ForegroundColor Yellow
    .\.venv\Scripts\python.exe -m scripts.gen_cert
}

$env:PYTHONPATH   = (Get-Location).Path
$env:BACKEND_URL  = "https://localhost:$BackendPort"

# ── Start backend ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Starting backend  →  https://localhost:$BackendPort" -ForegroundColor Cyan
$backendProc = Start-Process -PassThru -NoNewWindow `
    -FilePath ".\.venv\Scripts\uvicorn.exe" `
    -ArgumentList @(
        "backend.main:app",
        "--host", "0.0.0.0",
        "--port", "$BackendPort",
        "--ssl-keyfile", $Key,
        "--ssl-certfile", $Cert,
        "--reload"
    )

Start-Sleep -Seconds 2

# ── Start Streamlit frontend ───────────────────────────────────────────────────
Write-Host "Starting frontend →  https://localhost:$FrontendPort" -ForegroundColor Cyan
$frontendProc = Start-Process -PassThru -NoNewWindow `
    -FilePath ".\.venv\Scripts\streamlit.exe" `
    -ArgumentList @(
        "run", "ui/app.py",
        "--server.port", "$FrontendPort",
        "--server.sslCertFile", $Cert,
        "--server.sslKeyFile",  $Key,
        "--server.headless",    "true"
    )

Write-Host ""
Write-Host "─────────────────────────────────────────────────" -ForegroundColor Green
Write-Host "  Backend  : https://localhost:$BackendPort"       -ForegroundColor Green
Write-Host "  Frontend : https://localhost:$FrontendPort"      -ForegroundColor Green
Write-Host "  API docs : https://localhost:$BackendPort/docs"  -ForegroundColor Green
Write-Host "─────────────────────────────────────────────────" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl-C (or close this window) to stop both services." -ForegroundColor Yellow

try {
    # Keep script alive; wait for both child processes
    Wait-Process -Id $backendProc.Id, $frontendProc.Id -ErrorAction SilentlyContinue
} finally {
    Write-Host "Stopping services …" -ForegroundColor Yellow
    Stop-Process -Id $backendProc.Id  -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontendProc.Id -Force -ErrorAction SilentlyContinue
}
