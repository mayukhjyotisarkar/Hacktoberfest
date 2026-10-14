@echo off
setlocal enabledelayedexpansion

title PaperPilot — Running Dashboard

echo ==============================================================
echo   PaperPilot - Exam Paper Analyzer
echo   Launching local dashboard...
echo ==============================================================
echo.

:: 1. Navigate to script directory
cd /d "%~dp0"

:: 2. Verify virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not detected!
    echo.
    echo Please run 'setup_windows.bat' first to install required packages.
    echo.
    pause
    exit /b 1
)

:: 3. Activate virtual environment
call .venv\Scripts\activate.bat

:: 4. Check if Streamlit is available
streamlit --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Streamlit is not installed in the virtual environment!
    echo Please re-run 'setup_windows.bat' to fix dependencies.
    echo.
    pause
    exit /b 1
)

:: 5. Check if port 8501 is already in use
netstat -ano | findstr :8501 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [*] Note: Port 8501 is currently active.
    echo [*] Streamlit will launch on the next available port (e.g. 8502)
    echo     or open your existing session in the browser.
    echo.
)

echo [*] Starting Streamlit dashboard...
echo [*] Local URL: http://localhost:8501
echo [*] Press Ctrl+C in this window when you want to stop the server.
echo.

streamlit run app.py --server.headless false

if %ERRORLEVEL% neq 0 (
    echo.
    echo [NOTE] Streamlit stopped or encountered an error (exit code: %ERRORLEVEL%).
    pause
)

