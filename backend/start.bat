@echo off
echo ========================================
echo   QUANT INDUSTRY - Backend API Server
echo ========================================
echo.

:: Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed!
    echo.
    echo Please install Python from: https://python.org/
    echo.
    pause
    exit /b 1
)

echo Python found:
python --version

:: Check if venv exists
if not exist "venv" (
    echo.
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate venv and install dependencies
echo.
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting FastAPI server...
echo.
echo API will be available at: http://localhost:8000
echo API Documentation at: http://localhost:8000/docs
echo Press Ctrl+C to stop the server
echo.

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
