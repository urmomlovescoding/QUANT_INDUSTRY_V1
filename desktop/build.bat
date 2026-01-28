@echo off
title QUANT INDUSTRY Build
cd /d "%~dp0"

echo ========================================
echo  QUANT INDUSTRY Desktop Build
echo ========================================
echo.

:: Install dependencies if needed
if not exist "node_modules" (
    echo Installing Electron dependencies...
    call npm install
)

:: Build frontend first
echo Building frontend...
cd ..\frontend
if not exist "node_modules" (
    call npm install
)
call npm run build
cd ..\desktop
echo Frontend built successfully.
echo.

:: Build Electron app
echo Building Electron app for Windows...
call npm run build:win

echo.
echo ========================================
echo  Build Complete!
echo ========================================
echo.
echo Installers are in: desktop\dist\
echo.
pause
