#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 启动器主入口
负责：配置加载、日志初始化、模块编排、生命周期管理
"""

import argparse
import sys
import os
from pathlib import Path


def resolve_root() -> Path:
    """解析灵枢根目录（U盘挂载点）"""
    # 方式1: 通过启动器传入 --root
    # 方式2: 从当前文件位置推断
    core_dir = Path(__file__).resolve().parent
    root = core_dir.parent
    return root


def load_config(root: Path) -> dict:
    """加载 YAML 配置"""
    import yaml

    config_path = root / "config" / "lingshu.yaml"
    if not config_path.exists():
        print(f"[WARN] 配置文件不存在: {config_path}，使用默认配置")
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def init_logger(config: dict, root: Path):
    """初始化日志系统"""
    from loguru import logger

    log_level = config.get("app", {}).get("log_level", "INFO")
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # 移除默认控制台输出，重新配置
    logger.remove()
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(
        log_dir / "lingshu_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention=f"{config.get('app', {}).get('log_retention_days', 7)} days",
        level=log_level,
        encoding="utf-8",
    )

    return logger


def check_environment(root: Path, config: dict) -> bool:
    """环境预检：Python版本、依赖、模型文件存在性"""
    import platform

    checks = []

    # Python 版本
    py_ver = sys.version_info
    checks.append(("Python 版本", f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}", py_ver >= (3, 9)))

    # 关键目录
    for name, subdir in [("配置目录", "config"), ("核心模块", "core"), ("日志目录", "logs")]:
        path = root / subdir
        checks.append((name, str(path), path.exists()))

    # 模型目录（仅检查存在性，不强制要求，因为可能按需下载）
    models_dir = root / "models"
    checks.append(("模型目录", str(models_dir), models_dir.exists()))

    # 依赖检查（简化版，只检查关键库）
    try:
        import yaml
        checks.append(("PyYAML 依赖", "已安装", True))
    except ImportError:
        checks.append(("PyYAML 依赖", "未安装", False))

    try:
        import loguru
        checks.append(("Loguru 依赖", "已安装", True))
    except ImportError:
        checks.append(("Loguru 依赖", "未安装", False))

    # 打印检查结果
    print("\n" + "=" * 60)
    print("  灵枢环境自检")
    print("=" * 60)
    all_pass = True
    for name, value, ok in checks:
        status = "✅ 通过" if ok else "❌ 失败"
        if not ok:
            all_pass = False
        print(f"  {name:20s} {value:30s} {status}")
    print("=" * 60 + "\n")

    return all_pass


def print_banner(config: dict):
    """打印启动横幅"""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    name = config.get("app", {}).get("name", "灵枢")
    version = config.get("app", {}).get("version", "0.1.0")
    console.print(Panel.fit(
        f"[bold cyan]{name}[/bold cyan] [dim]v{version}[/dim]\n"
        f"[italic]超级电脑元神 · 数字智能体运行时[/italic]\n"
        f"[green]\"灵枢在此，主上何令？\"[/green]",
        title="启动",
        border_style="bright_blue",
    ))


def main():
    parser = argparse.ArgumentParser(description="灵枢（LingShu）Agent 启动器")
    parser.add_argument("--root", type=str, default=None, help="灵枢根目录路径")
    parser.add_argument("--config", type=str, default=None, help="自定义配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="模拟执行模式（不实际操作）")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    args = parser.parse_args()

    # 解析根目录
    root = Path(args.root) if args.root else resolve_root()
    root = root.resolve()

    # 加载配置
    config = load_config(root)
    if args.config:
        import yaml
        with open(args.config, "r", encoding="utf-8") as f:
            override = yaml.safe_load(f) or {}
            # 简单合并（后续可加强）
            config.update(override)

    # 应用命令行覆盖
    if args.dry_run:
        config.setdefault("development", {})
        config["development"]["dry_run"] = True
    if args.debug:
        config.setdefault("development", {})
        config["development"]["debug_mode"] = True

    # 初始化日志
    logger = init_logger(config, root)

    print_banner(config)
    logger.info(f"灵枢根目录: {root}")

    # 环境自检
    if not check_environment(root, config):
        logger.error("环境自检未通过，请运行 scripts/build_portable_env.py 构建环境")
        sys.exit(1)

    logger.info("环境自检通过，初始化核心模块...")

    # ============================================================
    # 核心模块编排（Phase 1 仅初始化桩，后续阶段逐步填充）
    # ============================================================

    # 系统监控（观星术）
    try:
        from core.monitor import SystemMonitor
        monitor = SystemMonitor(config.get("monitor", {}), root)
        monitor.start()
        logger.info("系统监控模块已启动")
    except ImportError:
        logger.warning("系统监控模块未就绪（Phase 1 桩）")
        monitor = None

    # 语音模块（Phase 2 填充）
    try:
        from core.asr import VoiceModule
        voice = VoiceModule(config.get("voice", {}), config.get("models", {}).get("asr", {}))
        logger.info("语音模块已加载")
    except ImportError:
        logger.warning("语音模块未就绪（Phase 2 待实现）")
        voice = None

    # 视觉模块（Phase 3 填充）
    try:
        from core.vision import VisionModule
        vision = VisionModule(config.get("models", {}).get("vlm", {}))
        logger.info("视觉模块已加载")
    except ImportError:
        logger.warning("视觉模块未就绪（Phase 3 待实现）")
        vision = None

    # 执行模块（Phase 4 填充）
    try:
        from core.executor import ExecutorModule
        executor = ExecutorModule(config.get("executor", {}))
        logger.info("执行模块已加载")
    except ImportError:
        logger.warning("执行模块未就绪（Phase 4 待实现）")
        executor = None

    # 记忆模块（Phase 5 填充）
    try:
        from core.memory import MemoryModule
        memory = MemoryModule(config.get("memory", {}), root)
        logger.info("记忆模块已加载")
    except ImportError:
        logger.warning("记忆模块未就绪（Phase 5 待实现）")
        memory = None

    # ============================================================
    # 主循环（Phase 1 为命令行交互，后续升级为语音唤醒）
    # ============================================================
    logger.info("进入主循环...")
    print("\n当前为 Phase 1 命令行模式。输入 'help' 查看命令，'quit' 退出。\n")

    while True:
        try:
            user_input = input("灵枢 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("灵枢告退。")
            break
        elif user_input.lower() in ("help", "h"):
            print(
                "\n可用命令:\n"
                "  status    — 查看系统状态\n"
                "  config    — 查看当前配置\n"
                "  modules   — 查看已加载模块\n"
                "  help      — 显示此帮助\n"
                "  quit      — 退出灵枢\n"
            )
        elif user_input.lower() == "status":
            if monitor:
                monitor.print_status()
            else:
                print("系统监控模块未加载")
        elif user_input.lower() == "config":
            import json
            print(json.dumps(config, indent=2, ensure_ascii=False))
        elif user_input.lower() == "modules":
            mods = {
                "monitor": monitor is not None,
                "voice": voice is not None,
                "vision": vision is not None,
                "executor": executor is not None,
                "memory": memory is not None,
            }
            for name, ok in mods.items():
                print(f"  {name:12s} {'✅ 已加载' if ok else '❌ 未就绪'}")
        else:
            print(f"未知命令: '{user_input}'。输入 'help' 查看帮助。")

    # 清理
    logger.info("灵枢正在关闭...")
    if monitor:
        monitor.stop()
        logger.info("系统监控已停止")

    logger.info("灵枢已安全退出")


if __name__ == "__main__":
    main()
