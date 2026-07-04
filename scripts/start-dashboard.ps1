# Start the local GC used gear dashboard (LAN-friendly).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$Port = 8765
if ($env:GC_DASHBOARD_PORT) {
    $Port = [int]$env:GC_DASHBOARD_PORT
}

Write-Host ""
Write-Host "Starting dashboard on port $Port ..."
Write-Host "  This machine:  http://127.0.0.1:$Port/"
Write-Host "  Same WiFi:     see LAN URLs printed below"
Write-Host "  Stop server:   Ctrl+C"
Write-Host ""

& $Python (Join-Path $Root "dashboard\server.py") --host 0.0.0.0 --port $Port
