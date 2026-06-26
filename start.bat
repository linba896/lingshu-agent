@echo off
chcp 65001 >nul
:: 灵枢（LingShu）Agent — Windows 启动器
:: 用法：双击运行 或 命令行执行 start.bat

set "ROOT=%~dp0"
set "PYTHON=%ROOT%python\python.exe"

:: 检查嵌入式 Python
if not exist "%PYTHON%" (
    echo [WARN] 嵌入式 Python 未找到: %PYTHON%
    echo [INFO] 尝试使用系统 Python...
    set "PYTHON=python"
)

:: 检查虚拟环境
if not exist "%PYTHON%" (
    set "VENV_PY=%ROOT%venv\Scripts\python.exe"
    if exist "%VENV_PY%" (
        set "PYTHON=%VENV_PY%"
    )
)

:: 确认 Python 可用
%PYTHON% --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 未找到可用的 Python 解释器
    echo [HINT] 请运行: python scripts/build_portable_env.py --python-version 3.11
    pause
    exit /b 1
)

echo ===========================================
echo   灵枢（LingShu）Agent — Windows 启动器
echo ===========================================
echo  Python: %PYTHON%
echo  根目录: %ROOT%
echo ===========================================
echo.

:: 启动主程序
%PYTHON% "%ROOT%core\launcher.py" %*

:: 暂停查看输出（如果双击运行）
if "%1"=="" pause
