#!/bin/bash
# 灵枢（LingShu）Agent — macOS 双击启动器
# 用法：双击 start.command 文件

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 调用通用启动脚本
exec ./start.sh
