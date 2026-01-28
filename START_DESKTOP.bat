@echo off
title QUANT INDUSTRY Desktop Launcher
cd /d "%~dp0"

echo ========================================
echo  QUANT INDUSTRY v10.0 Desktop
echo ========================================
echo.

:: Start backend in background
echo Starting backend server...
start "QUANT Backend" /min cmd /c "cd backend && start.bat"

:: Wait for backend to start
echo Waiting for backend to initialize...
timeout /t 5 /nobreak > nul

:: Start frontend dev server
echo Starting frontend...
start "QUANT Frontend" /min cmd /c "cd frontend && npm run dev"

:: Wait for frontend to start
echo Waiting for frontend to initialize...
timeout /t 5 /nobreak > nul

:: Start Electron
echo Launching desktop application...
cd desktop
if not exist "node_modules" (
    echo Installing Electron dependencies...
    call npm install
)

npm run dev

echo.
echo Desktop application closed.
pause
