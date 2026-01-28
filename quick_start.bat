@echo off
title QUANT INDUSTRY v10.0 - Quick Start
color 0A

echo.
echo ========================================
echo    QUANT INDUSTRY v10.0 - Quick Start
echo ========================================
echo.

:: Kill existing processes
echo [1/4] Cleaning up...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM node.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Start Backend
echo [2/4] Starting Backend...
cd /d C:\quant_industry_v1\backend
start /B /min cmd /c "python main.py > backend.log 2>&1"
timeout /t 8 /nobreak >nul

:: Bootstrap Brain
echo [3/4] Initializing AI Brain with market data...
curl -s -X POST "http://localhost:8000/api/brain-v6/bootstrap?symbols=SPY,AAPL,NVDA,AMD,TSLA,MSFT&num_trades=50" >nul 2>&1

:: Start Frontend
echo [4/4] Starting Frontend...
cd /d C:\quant_industry_v1\frontend
start /B /min cmd /c "npm run dev > frontend.log 2>&1"
timeout /t 5 /nobreak >nul

:: Open browser
start http://localhost:3000

echo.
echo ========================================
echo    QUANT INDUSTRY is now running!
echo ========================================
echo.
echo    Dashboard: http://localhost:3000
echo    API:       http://localhost:8000
echo.
echo    Close this window to stop all services.
echo ========================================

:: Keep window open - when closed, cleanup
cmd /k "echo Press Ctrl+C to stop... && pause >nul && taskkill /F /IM python.exe >nul 2>&1 && taskkill /F /IM node.exe >nul 2>&1"
