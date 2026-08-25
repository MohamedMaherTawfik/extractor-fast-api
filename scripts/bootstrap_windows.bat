@echo off
setlocal

cd /d "%~dp0.."

where py >nul 2>&1
if errorlevel 1 (
    echo ERROR: The Windows Python launcher ^(py^) is not available.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating project virtual environment...
    py -m venv .venv
    if errorlevel 1 (
        echo ERROR: Failed to create the virtual environment.
        exit /b 1
    )
)

echo Upgrading pip inside the project virtual environment...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip inside the virtual environment.
    exit /b 1
)

if exist "requirements.txt" (
    echo Installing project requirements...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install project requirements.
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.prefix != sys.base_prefix else 1)"
if errorlevel 1 (
    echo ERROR: Python is not running inside the project virtual environment.
    exit /b 1
)

echo Bootstrap completed successfully.
exit /b 0
