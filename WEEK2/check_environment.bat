@echo off
setlocal enabledelayedexpansion

title PaperPilot — System Diagnostics

echo ==============================================================
echo   PaperPilot - System & Environment Diagnostics
echo ==============================================================
echo.

cd /d "%~dp0"

:: 1. Python Check
echo [1/5] Checking Python installation...
set "PY_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
    echo   [OK] Project virtual environment found at: .venv
) else (
    python --version >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set "PY_EXE=python"
        echo   [OK] System Python detected:
    ) else (
        echo   [FAIL] Python not found on PATH or in .venv!
        echo   Please run setup_windows.bat to set up the environment.
        goto :END
    )
)
%PY_EXE% --version

:: 2. Dependencies Check
echo.
echo [2/5] Checking required Python packages...
%PY_EXE% -c "import pymupdf, streamlit, pandas, sklearn, requests; print('  [OK] All core libraries loaded successfully.')" 2>nul
if %ERRORLEVEL% neq 0 (
    echo   [WARN] Core libraries are missing or incomplete. Run setup_windows.bat.
)

:: 3. Storage & Write Permissions Check
echo.
echo [3/5] Checking local storage and write permissions...
%PY_EXE% -c "from paperpilot.storage import get_storage; s = get_storage(); print('  [OK] SQLite persistence connected: paperpilot.db')" 2>nul
if %ERRORLEVEL% neq 0 (
    echo   [WARN] Could not initialize paperpilot.db. Check folder write permissions.
)

:: 4. Optional Ollama AI Service Check
echo.
echo [4/5] Checking optional local Ollama AI service...
%PY_EXE% -c "from paperpilot.local_ai import LocalAIClient; c = LocalAIClient(); h = c.check_health(); print('  ' + ('[OK] Ollama is active on http://localhost:11434' if h else '[INFO] Ollama is offline (Core app works 100%% without AI)'))" 2>nul

:: 5. Optional Model Check
echo.
echo [5/5] Checking candidate AI model (qwen2.5-coder:1.5b-base)...
%PY_EXE% -c "from paperpilot.local_ai import LocalAIClient; c = LocalAIClient(); m = c.is_model_available(); print('  ' + ('[OK] Model qwen2.5-coder:1.5b-base is installed and ready.' if m else '[INFO] Model not installed. To add it: ollama run qwen2.5-coder:1.5b-base'))" 2>nul

echo.
echo ==============================================================
echo   Diagnostics Complete!
echo ==============================================================
echo.

:END
pause

