@echo off
chcp 65001 >nul

cd /d "%~dp0"
echo [LingShu] Starting GUI Launcher...
echo [LingShu] Initializing Neural Core...

:: Find Python
set "PYTHON="
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON=%~dp0.venv\Scripts\python.exe"
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

:: Launch GUI directly - tkinter is built-in, Pillow is pre-installed
cd /d "%~dp0"
"%PYTHON%" "%~dp0gui_launcher.py" %*
if errorlevel 1 (
    echo [ERROR] GUI failed to start! 
    echo.
    echo If you see "No module named PIL", run: %PYTHON% -m pip install pillow
    pause
)
