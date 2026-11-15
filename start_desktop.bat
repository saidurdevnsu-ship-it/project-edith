@echo off
title Project EDITH - Desktop Mode
cd /d "%~dp0"

echo ========================================================
echo   Launching Project EDITH (Native Desktop Window)
echo   Local LLMs and Server will start automatically...
echo ========================================================

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" run_desktop.py
) else (
    python run_desktop.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred. Press any key to exit.
    pause >nul
)
