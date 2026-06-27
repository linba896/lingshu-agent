@echo off
chcp 65001 >nul
cd /d "%~dp0"
set ROOT=%~dp0
if "%ROOT:~-1%"=="\" set ROOT=%ROOT:~0,-1%

echo [LingShu] Starting GUI Launcher...
echo [LingShu] Initializing Neural Core...

:: Find Python
set "PYTHON="
if exist "%ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
) else (
    for /f "delims=" %%i in ('where python 2^>nul') do set "PYTHON=%%i" & goto found
    for /f "delims=" %%i in ('where python3 2^>nul') do set "PYTHON=%%i" & goto found
    for /f "delims=" %%i in ('where KimiPython 2^>nul') do set "PYTHON=%%i" & goto found
)
:found
if "%PYTHON%"=="" (
    echo [ERROR] Python not found! Please install Python 3.10+
    pause
    exit /b 1
)

:: Check dependencies
"%PYTHON%" -c "import tkinter, PIL" 2>nul
if errorlevel 1 (
    echo [LingShu] Installing GUI dependencies...
    "%PYTHON%" -m pip install pillow pystray 2>nul
)

:: Launch GUI
cd /d "%ROOT%"
"%PYTHON%" "%ROOT%gui_launcher.py" %*
if errorlevel 1 (
    echo [ERROR] GUI failed to start!
    pause
)
