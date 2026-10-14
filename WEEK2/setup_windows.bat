@echo off
setlocal enabledelayedexpansion

title PaperPilot — Student Setup Assistant

echo ==============================================================
echo   PaperPilot - Student Setup Assistant (Windows)
echo   Local-First Previous Year Question Paper Analyzer
echo ==============================================================
echo.

:: 1. Navigate to the directory of this script
cd /d "%~dp0"

:: 2. Locate Python executable
set "PYTHON_CMD="

python --version >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python"
) else (
    py --version >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set "PYTHON_CMD=py"
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python was not found on your system PATH!
    echo.
    echo To fix this:
    echo   1. Download Python 3.10+ from https://www.python.org/downloads/
    echo   2. Run the installer and CRITICALLY check the box:
    echo      "[X] Add python.exe to PATH"
    echo   3. Restart this setup script after installing.
    echo.
    pause
    exit /b 1
)

:: 3. Check Python version (requires >= 3.10)
for /f "tokens=2 delims= " %%v in ('%PYTHON_CMD% --version 2^>^&1') do set "PY_VER=%%v"
echo [*] Detected Python version: %PY_VER%

%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.10 or newer is required. Found: %PY_VER%
    echo Please install Python 3.10, 3.11, 3.12, 3.13, or 3.14.
    pause
    exit /b 1
)

:: 4. Create local virtual environment if missing
if not exist ".venv\Scripts\python.exe" (
    echo [*] Creating isolated virtual environment in .venv...
    %PYTHON_CMD% -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        echo Ensure you have write permissions in this folder: %CD%
        pause
        exit /b 1
    )
    echo [*] Virtual environment created successfully.
) else (
    echo [*] Existing virtual environment found in .venv.
)

:: 5. Install / Update dependencies
echo [*] Upgrading pip...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet

echo [*] Installing required dependencies from requirements.txt...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Dependency installation failed!
    echo Check your internet connection or proxy settings.
    echo You can retry anytime by re-running setup_windows.bat.
    pause
    exit /b 1
)

:: 6. Verify sample data
if not exist "data\sample_os_2022.pdf" (
    echo [*] Generating synthetic sample question papers...
    .venv\Scripts\python.exe data\generate_samples.py >nul 2>&1
)

echo.
echo ==============================================================
echo   [SUCCESS] PaperPilot environment is ready!
echo ==============================================================
echo.
echo Quick Start:
echo   - Double-click 'run_paperpilot.bat' to launch the app.
echo   - The dashboard opens locally in your browser at:
echo     http://localhost:8501
echo.
echo OCR Note:
echo   - Digital text PDFs extract immediately with zero additional tools.
echo   - Scanned or photo exam papers can be set up automatically with 1-click
echo     directly inside the web app ('Set Up OCR Automatically'), or manually
echo     from: https://github.com/UB-Mannheim/tesseract/wiki
echo.
echo AI Note:
echo   - Core question extraction, clustering, and checklists
echo     work 100%% offline without any AI installed.
echo   - Optional: Install Ollama (https://ollama.com) if you want
echo     AI-generated topic badges and grounded revision notes.
echo ==============================================================
echo.

pause

