@echo off
chcp 65001 >nul
cd /d "%~dp0"
set ROOT=%~dp0
if "%ROOT:~-1%"=="\" set ROOT=%ROOT:~0,-1%

echo [LingShu] Starting GUI Launcher...
echo [LingShu] Initializing Neural Core...

:: Find Python - try local venv first, then system Python
set "PYTHON="
if exist "%ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
    echo [LingShu] Found local venv Python
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

echo [LingShu] Python: %PYTHON%

:: Launch GUI directly - tkinter is built-in, Pillow is pre-installed
cd /d "%ROOT%"
"%PYTHON%" "%ROOT%gui_launcher.py" %*
if errorlevel 1 (
    echo [ERROR] GUI failed to start! 
    echo.
    echo If you see "No module named PIL", run: %PYTHON% -m pip install pillow
    pause
)
