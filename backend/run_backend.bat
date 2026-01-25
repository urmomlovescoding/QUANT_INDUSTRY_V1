@echo off
echo Starting QUANT INDUSTRY Backend
cd /d "c:\quant_industry_v1\backend"
echo Working directory: %CD%
python -c "import main; print(f'Routes: {[r.path for r in main.app.routes if \"market\" in r.path]}')"
echo.
echo Starting server...
c:\quant_industry_v1\backend\venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
pause
