@echo off
setlocal enabledelayedexpansion

title Terminus - Setting up...
echo.
echo  ==============================================
echo   TERMINUS - The Last Stand Begins Here
echo  ==============================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found.
    echo.
    echo  Please install Python 3.11 or newer from:
    echo    https://www.python.org/downloads/
    echo.
    echo  Make sure to tick "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

:: Check Python version is 3.11+
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Python %PYVER% found.

:: Create venv if it doesn't exist
if not exist ".venv\" (
    echo  Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo  [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate venv
call .venv\Scripts\activate.bat

:: Install or upgrade dependencies (fast if already installed)
echo  Checking dependencies...
pip install -e . -q --disable-pip-version-check
if errorlevel 1 (
    echo  [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: Launch the game
echo  Launching Terminus...
echo.
python -m terminus
if errorlevel 1 (
    echo.
    echo  [ERROR] Terminus exited with an error.
    pause
)
