@echo off
title QUANT_INDUSTRY_V1 - Paper Trading
cd /d C:\QUANT_INDUSTRY_V1
echo ================================================================
echo   QUANT_INDUSTRY_V1 - Paper Trading Mode
echo   Press Ctrl+C to stop
echo ================================================================
echo.
python main.py --mode paper
pause
