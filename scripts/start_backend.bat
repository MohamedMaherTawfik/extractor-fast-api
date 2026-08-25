@echo off
setlocal

cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Project virtual environment not found.
    echo Run scripts\bootstrap_windows.bat first.
    exit /b 1
)

".venv\Scripts\python.exe" -m backend.main
set "emy_backend_exit=%errorlevel%"

if not "%emy_backend_exit%"=="0" (
    echo ERROR: Backend stopped with exit code %emy_backend_exit%.
)

exit /b %emy_backend_exit%
