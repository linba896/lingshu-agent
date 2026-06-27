@echo off
chcp 65001 >nul
cd /d "%~dp0"
set ROOT=%~dp0
if "%ROOT:~-1%"=="\" set ROOT=%ROOT:~0,-1%

echo [LingShu] Starting GUI Launcher...
echo [LingShu] Initializing Neural Core...

:: Find Python - try multiple sources
set "PYTHON="

:: 1. Local venv
if exist "%ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
    echo [LingShu] Found local venv Python
    goto found
)

:: 2. Kimi Python (known good environment)
set "KIMI_PYTHON=C:\Users\daisx\AppData\Roaming\kimi-desktop\daimon-share\daimon\runtime\python\.venv\Scripts\python.exe"
if exist "%KIMI_PYTHON%" (
    set "PYTHON=%KIMI_PYTHON%"
    echo [LingShu] Found Kimi Python
    goto found
)

:: 3. System Python via where
for /f "delims=" %%i in ('where python 2^>nul') do (
    set "PYTHON=%%i"
    echo [LingShu] Found system Python: %%i
    goto found
)
for /f "delims=" %%i in ('where python3 2^>nul') do (
    set "PYTHON=%%i"
    echo [LingShu] Found python3: %%i
    goto found
)

:found
if "%PYTHON%"=="" (
    echo [ERROR] Python not found! Please install Python 3.10+
    pause
    exit /b 1
)

echo [LingShu] Python: %PYTHON%

:: Test Python works
echo [LingShu] Testing Python...
"%PYTHON%" -c "print('Python OK')" 2>nul
if errorlevel 1 (
    echo [ERROR] Python test failed! The Python installation may be broken.
    pause
    exit /b 1
)

:: Check tkinter
echo [LingShu] Checking tkinter...
"%PYTHON%" -c "import tkinter" 2>nul
if errorlevel 1 (
    echo [ERROR] tkinter not available! Please reinstall Python with tkinter support.
    pause
    exit /b 1
)

:: Launch GUI
cd /d "%ROOT%"
echo [LingShu] Launching GUI...
"%PYTHON%" "%ROOT%gui_launcher.py" %*

:: Pause on any error so user can see what happened
if errorlevel 1 (
    echo.
    echo [ERROR] GUI exited with error code %errorlevel%
    echo.
    echo Common fixes:
    echo   1. Install Pillow: %PYTHON% -m pip install pillow
    echo   2. Check that icon.ico exists in the project folder
    echo   3. Run in console to see full error: %PYTHON% gui_launcher.py
    echo.
    pause
)
