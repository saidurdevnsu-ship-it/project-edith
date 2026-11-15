@echo off
title Project EDITH - Web Browser Mode
cd /d "%~dp0"

echo ========================================================
echo   Launching Project EDITH (Web Browser Mode)
echo   Local LLMs and Server will start automatically...
echo ========================================================

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" run_web.py
) else (
    python run_web.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred. Press any key to exit.
    pause >nul
)
