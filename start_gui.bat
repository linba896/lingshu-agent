@echo off
chcp 65001 >nul
title 灵枢启动台

REM 查找 Python 解释器
set "PYTHON_CMD="

REM 1. 先尝试同目录下的 python（如果用户安装了便携版）
if exist "%~dp0python\python.exe" (
    set "PYTHON_CMD=%~dp0python\python.exe"
    goto :found
)

REM 2. 尝试 Kimi 的 Python 运行时
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :found
)

REM 3. 尝试系统 PATH 中的 python
python --version >nul 2>&1
if %errorlevel% == 0 (
    set "PYTHON_CMD=python"
    goto :found
)

REM 4. 尝试 py 启动器
py --version >nul 2>&1
if %errorlevel% == 0 (
    set "PYTHON_CMD=py"
    goto :found
)

echo ❌ 未找到 Python 解释器！
echo.
echo 请安装 Python 3.9+ 后重试，或修改本脚本指向正确的 python.exe 路径
echo 下载地址: https://www.python.org/downloads/
echo.
pause
exit /b 1

:found
echo ☯ 灵枢启动台 — 正在启动...
echo Python路径: %PYTHON_CMD%
echo.

REM 设置项目根目录
set "ROOT_DIR=%~dp0"
set "PYTHONPATH=%ROOT_DIR%"

REM 启动 GUI（启动台本身）
"%PYTHON_CMD%" "%ROOT_DIR%gui_launcher.py"

exit /b 0
