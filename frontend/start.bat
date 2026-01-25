@echo off
echo ========================================
echo   QUANT INDUSTRY - Frontend Server
echo ========================================
echo.

:: Check if Node.js is installed
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Node.js is not installed!
    echo.
    echo Please install Node.js from: https://nodejs.org/
    echo Download the LTS version and run the installer.
    echo.
    pause
    exit /b 1
)

echo Node.js found:
node --version

:: Check if node_modules exists
if not exist "node_modules" (
    echo.
    echo Installing dependencies...
    call npm install
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo Starting development server...
echo.
echo The app will be available at: http://localhost:3000
echo Press Ctrl+C to stop the server
echo.

call npm run dev
