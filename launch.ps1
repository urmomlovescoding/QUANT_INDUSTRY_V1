# QUANT INDUSTRY v10.0 - Master Launcher (PowerShell)
# Defaults to Electron desktop application with all services
# ============================================================

param(
    [string]$Mode = "desktop"  # Options: desktop, web
)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "           QUANT INDUSTRY v10.0 - LAUNCHER" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting all services..." -ForegroundColor Yellow
Write-Host ""

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

# Start Backend API Server
Write-Host "[1/3] Starting Backend API Server..." -ForegroundColor White
$backendJob = Start-Process -FilePath "python" -ArgumentList "main.py" -WorkingDirectory "$scriptPath\backend" -PassThru -WindowStyle Minimized

Write-Host "      Waiting for backend to initialize..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Start Frontend Dev Server
Write-Host "[2/3] Starting Frontend Server..." -ForegroundColor White
$frontendJob = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WorkingDirectory "$scriptPath\frontend" -PassThru -WindowStyle Minimized

Start-Sleep -Seconds 3

if ($Mode -eq "desktop") {
    Write-Host "[3/3] Launching Electron Desktop App..." -ForegroundColor White
    Set-Location "$scriptPath\desktop"
    npm start
} elseif ($Mode -eq "web") {
    Write-Host "[3/3] Opening Web Browser..." -ForegroundColor White
    Start-Process "http://localhost:3000"
    Write-Host ""
    Write-Host "Web UI available at: http://localhost:3000" -ForegroundColor Green
    Write-Host "Backend API at: http://localhost:8000" -ForegroundColor Green
    Write-Host "Press Enter to stop all services..." -ForegroundColor Yellow
    Read-Host
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "QUANT INDUSTRY v10.0 - Services Started" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Desktop App: Running in Electron" -ForegroundColor White
Write-Host "Backend API: http://localhost:8000" -ForegroundColor White
Write-Host "Frontend:    http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
