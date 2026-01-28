@echo off
title QUANT INDUSTRY Desktop
cd /d "%~dp0"

echo ========================================
echo  QUANT INDUSTRY Desktop v10.0
echo ========================================
echo.

:: Check if node_modules exists
if not exist "node_modules" (
    echo Installing dependencies...
    call npm install
    echo.
)

:: Check if frontend is built
if not exist "..\frontend\dist\index.html" (
    echo Building frontend...
    cd ..\frontend
    call npm install
    call npm run build
    cd ..\desktop
    echo.
)

echo Starting QUANT INDUSTRY Desktop...
echo.

:: Start in development mode (connects to localhost:3000)
npm run dev
