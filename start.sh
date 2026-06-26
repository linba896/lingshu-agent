#!/usr/bin/env bash
# 灵枢（LingShu）Agent — Linux/macOS 启动器
# 用法：./start.sh [参数]

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# 优先使用虚拟环境
if [ -f "$ROOT/venv/bin/python" ]; then
    PYTHON="$ROOT/venv/bin/python"
elif [ -f "$ROOT/.venv/bin/python" ]; then
    PYTHON="$ROOT/.venv/bin/python"
else
    PYTHON="python3"
fi

# 检查 Python 可用
if ! $PYTHON --version >/dev/null 2>&1; then
    echo "[ERROR] 未找到可用的 Python 解释器: $PYTHON"
    echo "[HINT] 请运行: python3 scripts/build_portable_env.py"
    exit 1
fi

echo "==========================================="
echo "  灵枢（LingShu）Agent — Unix 启动器"
echo "==========================================="
echo "  Python: $PYTHON"
echo "  根目录: $ROOT"
echo "==========================================="
echo ""

# 启动主程序
exec "$PYTHON" "$ROOT/core/launcher.py" "$@"
