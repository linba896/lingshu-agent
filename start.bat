@echo off
chcp 65001 >nul
:: ============================================================
:: 灵枢（LingShu）Agent — Windows 启动器
:: 功能：检测U盘内嵌Python环境，启动主程序
:: ============================================================

title 灵枢 — 数字元神

set "LS_ROOT=%~dp0"
set "LS_ROOT=%LS_ROOT:~0,-1%"
set "PYTHON_DIR=%LS_ROOT%\python"
set "VENV_DIR=%LS_ROOT%\venv"
set "LOGS_DIR=%LS_ROOT%\logs"

:: 创建日志目录
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

:: 记录启动时间
set "LOG_FILE=%LOGS_DIR%\lingshu_%~t0.log"
echo [%date% %time%] 灵枢启动器运行 >> "%LOG_FILE%"

:: 检查内嵌Python
if exist "%PYTHON_DIR%\python.exe" (
    set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
    echo [INFO] 使用内嵌Python环境
) else if exist "%VENV_DIR%\Scripts\python.exe" (
    set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
    echo [INFO] 使用虚拟环境
) else (
    echo [WARN] 未找到内嵌Python，尝试系统Python...
    python --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] 未找到Python。请先运行 scripts\build_portable_env.py 构建环境。
        pause
        exit /b 1
    )
    set "PYTHON_EXE=python"
)

echo [INFO] Python路径: %PYTHON_EXE%
echo [INFO] 灵枢根目录: %LS_ROOT%

:: 检查核心模块
if not exist "%LS_ROOT%\core\launcher.py" (
    echo [ERROR] 核心模块 launcher.py 缺失。请检查文件完整性。
    pause
    exit /b 1
)

:: 启动主程序
echo.
echo ============================================================
echo  灵枢在此，主上何令？
echo ============================================================
echo.

"%PYTHON_EXE%" -m core.launcher --root "%LS_ROOT%" %*

:: 捕获退出码
set "EXIT_CODE=%ERRORLEVEL%"
echo [%date% %time%] 灵枢退出，码: %EXIT_CODE% >> "%LOG_FILE%"

if %EXIT_CODE% neq 0 (
    echo [ERROR] 灵枢异常退出（码: %EXIT_CODE%），查看日志: %LOG_FILE%
    pause
)

exit /b %EXIT_CODE%
