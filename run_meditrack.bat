@echo off
setlocal enabledelayedexpansion
title MediTrack Pro - Pharmacy Management System
echo ===================================================
echo     MediTrack Pro - Pharmacy Management System
echo ===================================================
echo.

:: 1. Check if 'python' command works
set "PY_CMD=python"
python --version >nul 2>&1
if %errorlevel% equ 0 goto FOUND_PYTHON

:: 2. Check if 'py' launcher works
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=py"
    goto FOUND_PYTHON
)

:: 3. Search in common LocalAppData Programs Python folders
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
    if exist "%%D\python.exe" (
        set "PY_CMD=%%D\python.exe"
        goto FOUND_PYTHON
    )
)

:: 4. Search in common Program Files Python folders
for /d %%D in ("%ProgramFiles%\Python*") do (
    if exist "%%D\python.exe" (
        set "PY_CMD=%%D\python.exe"
        goto FOUND_PYTHON
    )
)

echo [WARNING] Could not find python in standard paths automatically.
echo Please open app.py directly using Python IDLE (File - Open - app.py - Press F5).
pause
exit /b

:FOUND_PYTHON
echo [Found Python] Using: !PY_CMD!
echo.
echo [1/2] Verifying and installing dependencies...
"!PY_CMD!" -m pip install flask werkzeug

echo.
echo [2/2] Starting MediTrack Pro Server...
echo Opening browser at http://127.0.0.1:5000 in 3 seconds...
start http://127.0.0.1:5000
"!PY_CMD!" app.py
pause
