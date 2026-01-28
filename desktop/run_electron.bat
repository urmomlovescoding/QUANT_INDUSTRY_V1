@echo off
echo ================================================
echo QUANT INDUSTRY v10.0 - Desktop App Launcher
echo ================================================
echo.

cd /d "c:\quant_industry_v1\desktop"
echo Working directory: %CD%
echo.

:: Check if backend is running
echo Checking backend status...
curl -s http://localhost:8000/api/health >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Backend not running, starting it...
    start "Backend" /d "c:\quant_industry_v1\backend" cmd /c "c:\quant_industry_v1\backend\venv\Scripts\python.exe c:\quant_industry_v1\backend\start_server.py"
    timeout /t 10 /nobreak >nul
) else (
    echo [OK] Backend is running
)

:: Check if frontend is running
echo Checking frontend status...
curl -s http://localhost:3000 >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Frontend not running, starting it...
    start "Frontend" /d "c:\quant_industry_v1\frontend" cmd /c "npm run dev"
    timeout /t 10 /nobreak >nul
) else (
    echo [OK] Frontend is running
)

:: Launch Electron
echo.
echo Starting Electron...
call "c:\quant_industry_v1\desktop\node_modules\.bin\electron.cmd" . --dev
pause
