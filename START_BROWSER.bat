@echo off
title QUANT INDUSTRY v10.0 - Browser Mode
cd /d "%~dp0"

echo.
echo  ============================================
echo      QUANT INDUSTRY v10.0 - BROWSER MODE
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

:: Start backend (using api.main:app - the unified entry point)
echo [1/2] Starting Backend API Server...
start "QUANT Backend" cmd /c "cd /d %~dp0 && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"

:: Wait for backend
echo      Waiting for API to initialize...
timeout /t 4 /nobreak > nul

:: Start frontend
echo [2/2] Starting Frontend Server...
start "QUANT Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

:: Wait and open browser
timeout /t 3 /nobreak > nul
echo.
echo  ============================================
echo      Services Running
echo  ============================================
echo      - Backend API: http://localhost:8000
echo      - Frontend UI: http://localhost:3000
echo      - API Docs:    http://localhost:8000/docs
echo  ============================================
echo.
echo Opening browser...
start http://localhost:3000

echo.
echo Press any key to stop all services...
pause > nul

echo Stopping services...
taskkill /FI "WINDOWTITLE eq QUANT Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq QUANT Frontend*" /F >nul 2>&1
echo Done.
