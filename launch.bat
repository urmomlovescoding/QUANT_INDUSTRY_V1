@echo off
title QUANT_INDUSTRY v10.0 - Trading Platform
color 0A

:menu
cls
echo ================================================================
echo        QUANT INDUSTRY v10.0 - Institutional Trading Platform
echo ================================================================
echo.
echo   [1] Launch Desktop App (Electron) - RECOMMENDED
echo   [2] Launch Web UI (React + Backend)
echo   [3] Run Trading Engine (Console)
echo   [4] Run Backtest Mode
echo   [5] Run Self-Grading Analysis
echo   [6] Run Health Check
echo   [7] Run All Tests (258 parity tests)
echo   [8] Show Version Info
echo   [9] Open Project Folder
echo   [0] Exit
echo.
echo ================================================================
echo   Quick Launch: Press ENTER for Desktop App
echo ================================================================
set /p choice="Select an option: "

if "%choice%"=="" goto electron
if "%choice%"=="1" goto electron
if "%choice%"=="2" goto webui
if "%choice%"=="3" goto console
if "%choice%"=="4" goto backtest
if "%choice%"=="5" goto grade
if "%choice%"=="6" goto health
if "%choice%"=="7" goto tests
if "%choice%"=="8" goto version
if "%choice%"=="9" goto folder
if "%choice%"=="0" goto exit

echo Invalid option. Press any key to try again...
pause >nul
goto menu

:electron
cls
echo ================================================================
echo   Starting QUANT INDUSTRY Desktop App (Electron)
echo ================================================================
echo.
echo [1/4] Starting Backend API Server...
cd /d C:\quant_industry_v1\backend
start "QUANT INDUSTRY Backend" /min cmd /c "python main.py"
echo      Backend starting on http://localhost:8000
timeout /t 8 /nobreak > nul

echo [2/4] Bootstrapping AI Brain with live market data...
curl -s -X POST "http://localhost:8000/api/brain-v6/bootstrap?symbols=SPY,AAPL,NVDA,AMD,TSLA,MSFT&num_trades=50" > nul 2>&1
echo      Brain initialized with historical trades!

echo [3/4] Starting Frontend Dev Server...
cd /d C:\quant_industry_v1\frontend
start "QUANT INDUSTRY Frontend" /min cmd /c "npm run dev"
echo      Frontend starting on http://localhost:3000
timeout /t 5 /nobreak > nul

echo [4/4] Launching Electron Desktop App...
cd /d C:\quant_industry_v1\desktop
if exist "node_modules" (
    npm start
) else (
    echo      Electron not installed, opening in browser...
    start http://localhost:3000
)
goto menu

:webui
cls
echo ================================================================
echo   Starting QUANT INDUSTRY Web UI
echo ================================================================
echo.
echo [1/3] Starting Backend API Server...
cd /d C:\quant_industry_v1\backend
start "QUANT INDUSTRY Backend" /min cmd /c "python main.py"
echo      Backend: http://localhost:8000
timeout /t 8 /nobreak > nul

echo [2/3] Bootstrapping AI Brain with live market data...
curl -s -X POST "http://localhost:8000/api/brain-v6/bootstrap?symbols=SPY,AAPL,NVDA,AMD,TSLA,MSFT&num_trades=50" > nul 2>&1
echo      Brain initialized with historical trades!

echo [3/3] Starting Frontend Dev Server...
cd /d C:\quant_industry_v1\frontend
start "QUANT INDUSTRY Frontend" cmd /c "npm run dev"
echo      Frontend: http://localhost:3000

echo.
echo Opening browser...
timeout /t 5 /nobreak > nul
start http://localhost:3000
echo.
echo ================================================================
echo   QUANT INDUSTRY is running!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo ================================================================
echo.
echo Press any key to return to menu...
pause >nul
goto menu

:console
cls
echo ================================================================
echo   Select Trading Mode:
echo   [1] Paper Trading (Simulated)
echo   [2] Live Trading (Requires API Keys)
echo   [3] Back to Menu
echo ================================================================
set /p mode="Select mode: "

if "%mode%"=="1" (
    echo Starting Paper Trading...
    cd /d C:\QUANT_INDUSTRY_V1
    python main.py --mode paper
    pause
    goto menu
)
if "%mode%"=="2" (
    echo.
    echo WARNING: Live trading uses real money!
    set /p confirm="Are you sure? (yes/no): "
    if /i "%confirm%"=="yes" (
        cd /d C:\QUANT_INDUSTRY_V1
        python main.py --mode live
    )
    pause
    goto menu
)
if "%mode%"=="3" goto menu
goto console

:backtest
cls
echo Starting Backtest Mode...
echo.
cd /d C:\QUANT_INDUSTRY_V1
python main.py --mode backtest
pause
goto menu

:grade
cls
echo Running Self-Grading Analysis...
echo.
cd /d C:\QUANT_INDUSTRY_V1
python main.py --grade
pause
goto menu

:health
cls
echo Running Health Check...
echo.
cd /d C:\QUANT_INDUSTRY_V1
python main.py --health
pause
goto menu

:tests
cls
echo Running All Parity Tests (258 tests)...
echo.
cd /d C:\QUANT_INDUSTRY_V1
python -m pytest tests/ -v --tb=short
pause
goto menu

:version
cls
cd /d C:\QUANT_INDUSTRY_V1
python main.py --version
pause
goto menu

:folder
explorer C:\QUANT_INDUSTRY_V1
goto menu

:exit
echo.
echo Goodbye!
timeout /t 2 >nul
exit
