@echo off
title QUANT INDUSTRY v10.0 - Desktop Application
cd /d "%~dp0"

echo.
echo  ============================================
echo      QUANT INDUSTRY v10.0 - DESKTOP APP
echo  ============================================
echo      Institutional Grade Trading Platform
echo  ============================================
echo.

:: Check prerequisites
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found. Install from https://python.org/
    pause
    exit /b 1
)

where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js not found. Install from https://nodejs.org/
    pause
    exit /b 1
)

echo [OK] Prerequisites verified
echo.

:: Start backend in background (minimized)
echo [1/3] Starting Backend API Server...
if exist "%~dp0backend\venv\Scripts\python.exe" (
    start "QUANT Backend" /min cmd /c ""%~dp0backend\venv\Scripts\python.exe" "%~dp0backend\start_server.py""
) else (
    start "QUANT Backend" /min cmd /c "cd /d %~dp0backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000"
)

:: Wait for backend with verification
echo      Waiting for API to initialize...
set /a "attempts=0"
:wait_backend
timeout /t 2 /nobreak > nul
set /a "attempts+=1"
curl -s http://localhost:8000/api/health >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if %attempts% LSS 15 goto wait_backend
    echo      [WARNING] Backend may not be fully ready
)
echo      Backend ready!

:: Start frontend dev server (minimized)
echo [2/3] Starting Frontend Server...
start "QUANT Frontend" /min cmd /c "cd /d %~dp0frontend && npm run dev"

:: Wait for frontend with verification
echo      Waiting for UI to initialize...
set /a "attempts=0"
:wait_frontend
timeout /t 2 /nobreak > nul
set /a "attempts+=1"
curl -s http://localhost:3000 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    if %attempts% LSS 15 goto wait_frontend
    echo      [WARNING] Frontend may not be fully ready
)
echo      Frontend ready!

:: Start Electron Desktop App
echo [3/3] Launching Desktop Application...
echo.
cd /d "%~dp0desktop"

:: Install Electron dependencies if needed
if not exist "node_modules" (
    echo      Installing Electron dependencies...
    call npm install
)

:: Launch Electron
echo.
echo  ============================================
echo      Desktop Application Starting...
echo  ============================================
echo      - Backend API: http://localhost:8000
echo      - API Docs:    http://localhost:8000/docs
echo      - Close this window to exit all services
echo  ============================================
echo.

call "%~dp0desktop\node_modules\.bin\electron.cmd" . --dev

:: Cleanup when Electron closes
echo.
echo Desktop application closed.
echo Stopping background services...
taskkill /FI "WINDOWTITLE eq QUANT Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq QUANT Frontend*" /F >nul 2>&1
echo Done.
pause
