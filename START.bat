@echo off
echo ================================================
echo QUANT_INDUSTRY_V1 - Starting Services
echo ================================================

cd /d %~dp0

echo.
echo Starting API server on port 8000...
start "QUANT API" cmd /k "cd /d %~dp0 && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak > nul

echo Starting Frontend dev server on port 5173...
start "QUANT Frontend" cmd /k "cd /d %~dp0\frontend && npm run dev"

echo.
echo ================================================
echo Services starting...
echo   API:      http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo ================================================
echo.
echo Press any key to open the frontend in browser...
pause > nul
start http://localhost:5173
