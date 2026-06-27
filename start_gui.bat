@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: 启动灵枢 Agent — 绕过 Windows Store Python 沙箱
:: 自动检测可用的 Python 解释器

set "ROOT=%~dp0"
cd /d "%ROOT%"

:: 候选 Python 路径（按优先级）
set "PY=%ROOT%python\pythonw.exe"
if exist "!PY!" goto :found

set "PY=%ROOT%python\python.exe"
if exist "!PY!" goto :found

:: Kimi 托管 Python 运行时
set "PY=%USERPROFILE%\AppData\Roaming\kimi-desktop\daimon-share\daimon\runtime\python\.venv\Scripts\pythonw.exe"
if exist "!PY!" goto :found

set "PY=%USERPROFILE%\AppData\Roaming\kimi-desktop\daimon-share\daimon\runtime\python\.venv\Scripts\python.exe"
if exist "!PY!" goto :found

:: 标准安装 Python
set "PY=C:\Python312\pythonw.exe"
if exist "!PY!" goto :found

set "PY=C:\Python311\pythonw.exe"
if exist "!PY!" goto :found

set "PY=C:\Python310\pythonw.exe"
if exist "!PY!" goto :found

:: 尝试 PATH 中的 python
pythonw --version >nul 2>&1
if %errorlevel%==0 (
    set "PY=pythonw"
    goto :found
)

python --version >nul 2>&1
if %errorlevel%==0 (
    set "PY=python"
    goto :found
)

echo.
echo ============================================
echo  ERROR: 无法找到可用的 Python 解释器！
echo ============================================
echo.
echo 请安装 Python 3.9-3.12 标准版（非 Windows Store 版）
echo 或下载便携版 Python 放在项目目录的 python/ 文件夹中。
echo.
echo 推荐安装路径：C:\Python312\  或  项目目录\python\
echo.
pause
exit /b 1

:found
echo [灵枢] 使用 Python: %PY%
echo [灵枢] 启动 VS Code 风格 IDE...

"%PY%" "gui_launcher.py"
if %errorlevel% neq 0 (
    echo.
    echo 启动失败，请检查错误信息。
    pause
)
