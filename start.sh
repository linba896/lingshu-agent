#!/usr/bin/env bash
# ============================================================
# 灵枢（LingShu）Agent — Linux/macOS 启动器
# 功能：检测U盘内嵌Python环境，启动主程序
# ============================================================

set -euo pipefail

LS_ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON_DIR="$LS_ROOT/python"
VENV_DIR="$LS_ROOT/venv"
LOGS_DIR="$LS_ROOT/logs"

# 创建日志目录
mkdir -p "$LOGS_DIR"

LOG_FILE="$LOGS_DIR/lingshu_$(date +%Y%m%d_%H%M%S).log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 灵枢启动器运行" >> "$LOG_FILE"

# 检测Python
PYTHON_EXE=""
if [ -x "$PYTHON_DIR/bin/python3" ]; then
    PYTHON_EXE="$PYTHON_DIR/bin/python3"
    echo "[INFO] 使用内嵌Python环境"
elif [ -x "$VENV_DIR/bin/python3" ]; then
    PYTHON_EXE="$VENV_DIR/bin/python3"
    echo "[INFO] 使用虚拟环境"
else
    if command -v python3 &>/dev/null; then
        PYTHON_EXE="python3"
        echo "[WARN] 未找到内嵌Python，使用系统Python"
    elif command -v python &>/dev/null; then
        PYTHON_EXE="python"
        echo "[WARN] 未找到内嵌Python，使用系统Python"
    else
        echo "[ERROR] 未找到Python。请先运行 scripts/build_portable_env.py 构建环境。"
        exit 1
    fi
fi

echo "[INFO] Python路径: $PYTHON_EXE"
echo "[INFO] 灵枢根目录: $LS_ROOT"

# 检查核心模块
if [ ! -f "$LS_ROOT/core/launcher.py" ]; then
    echo "[ERROR] 核心模块 launcher.py 缺失。请检查文件完整性。"
    exit 1
fi

# 启动主程序
echo ""
echo "============================================================"
echo "  灵枢在此，主上何令？"
echo "============================================================"
echo ""

"$PYTHON_EXE" -m core.launcher --root "$LS_ROOT" "$@" 2>>"$LOG_FILE" || {
    EXIT_CODE=$?
    echo "[ERROR] 灵枢异常退出（码: $EXIT_CODE），查看日志: $LOG_FILE"
    exit $EXIT_CODE
}

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 灵枢正常退出" >> "$LOG_FILE"
