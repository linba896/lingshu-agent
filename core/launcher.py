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
    core_dir = Path(__file__).resolve().parent
    root = core_dir.parent
    return root


def load_config(root: Path) -> dict:
    import yaml
    config_path = root / "config" / "lingshu.yaml"
    if not config_path.exists():
        print(f"[WARN] 配置文件不存在: {config_path}，使用默认配置")
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def init_logger(config: dict, root: Path):
    from loguru import logger
    log_level = config.get("app", {}).get("log_level", "INFO")
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
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
    import platform
    checks = []
    py_ver = sys.version_info
    checks.append(("Python 版本", f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}", py_ver >= (3, 9)))
    for name, subdir in [("配置目录", "config"), ("核心模块", "core"), ("日志目录", "logs")]:
        path = root / subdir
        checks.append((name, str(path), path.exists()))
    models_dir = root / "models"
    checks.append(("模型目录", str(models_dir), models_dir.exists()))
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
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    name = config.get("app", {}).get("name", "灵枢")
    version = config.get("app", {}).get("version", "0.1.0")
    console.print(Panel.fit(
        f"[bold cyan]{name}[/bold cyan] [dim]v{version}[/dim]\n"
        f"[italic]超级电脑元神 · 数字智能体运行时[/italic]\n"
        f'[green]"灵枢在此，主上何令？"[/green]',
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

    root = Path(args.root) if args.root else resolve_root()
    root = root.resolve()

    config = load_config(root)
    if args.config:
        import yaml
        with open(args.config, "r", encoding="utf-8") as f:
            override = yaml.safe_load(f) or {}
            config.update(override)

    if args.dry_run:
        config.setdefault("development", {})
        config["development"]["dry_run"] = True
    if args.debug:
        config.setdefault("development", {})
        config["development"]["debug_mode"] = True

    logger = init_logger(config, root)
    print_banner(config)
    logger.info(f"灵枢根目录: {root}")

    if not check_environment(root, config):
        logger.error("环境自检未通过，请运行 scripts/build_portable_env.py 构建环境")
        sys.exit(1)

    logger.info("环境自检通过，初始化核心模块...")

    try:
        from core.monitor import SystemMonitor
        monitor = SystemMonitor(config.get("monitor", {}), root)
        monitor.start()
        logger.info("系统监控模块已启动")
    except ImportError:
        logger.warning("系统监控模块未就绪（Phase 1 桩）")
        monitor = None

    try:
        from core.asr import VoiceModule
        voice = VoiceModule(
            config.get("voice", {}),
            config.get("models", {}).get("asr", {}),
            config.get("models", {}).get("nlu", {}),
            root,
        )
        if voice.is_ready():
            logger.info("语音模块已加载（VAD + ASR + NLU）")
        elif voice.is_partial_ready():
            logger.info("语音模块部分就绪（ASR 可用，VAD 不可用）")
        else:
            logger.warning("语音模块未就绪（缺少依赖或模型）")
    except ImportError as e:
        logger.warning(f"语音模块未就绪（Phase 2 待实现）: {e}")
        voice = None
    except Exception as e:
        logger.error(f"语音模块初始化异常: {e}")
        voice = None

    try:
        from core.vision import VisionModule
        vision = VisionModule(config.get("models", {}).get("vlm", {}))
        logger.info("视觉模块已加载")
    except ImportError:
        logger.warning("视觉模块未就绪（Phase 3 待实现）")
        vision = None

    try:
        from core.executor import ExecutorModule
        executor = ExecutorModule(config.get("executor", {}))
        logger.info("执行模块已加载")
    except ImportError:
        logger.warning("执行模块未就绪（Phase 4 待实现）")
        executor = None

    try:
        from core.memory import MemoryModule
        memory = MemoryModule(config.get("memory", {}), root)
        logger.info("记忆模块已加载")
    except ImportError:
        logger.warning("记忆模块未就绪（Phase 5 待实现）")
        memory = None

    logger.info("进入主循环...")

    use_voice = voice is not None and voice.is_ready()
    skip_wake = config.get("development", {}).get("skip_wake_word", False)

    if use_voice and not skip_wake:
        print('\n🎙️  语音模式已激活。说出唤醒词 "灵枢" 开始指令，或输入 \'text\' 切换到文本模式。\n')
    elif use_voice and skip_wake:
        print("\n🎙️  语音模式已激活（跳过唤醒词）。直接说话即可，或输入 'text' 切换到文本模式。\n")
    else:
        print("\n⌨️  当前为文本模式。输入 'help' 查看命令，'quit' 退出。\n")

    def on_intent_detected(result: dict):
        intent_data = result.get("intent", {})
        intent_type = intent_data.get("intent", "unknown")
        raw_text = intent_data.get("raw_text", "")
        print(f'\n[🎙️ 语音指令] "{raw_text}" → intent={intent_type}')
        if intent_type == "open" and voice:
            target = intent_data.get("target", "")
            if target:
                print(f"  → 执行: 打开 {target}")
        elif intent_type == "unknown":
            print("  → 未识别意图，请重试或说得更具体一些")

    if use_voice and not skip_wake:
        voice.start_continuous_listening(on_intent_detected)
        print("[Voice] 后台监听已启动，等待唤醒词...")

    while True:
        try:
            user_input = input("灵枢 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break

        if not user_input:
            continue

        cmd = user_input.lower()

        if cmd in ("quit", "exit", "q"):
            print("灵枢告退。")
            break
        elif cmd in ("help", "h"):
            print(
                "\n可用命令:\n"
                "  status       — 查看系统状态\n"
                "  config       — 查看当前配置\n"
                "  modules      — 查看已加载模块\n"
                "  listen       — 手动触发一次语音录制\n"
                "  text         — 切换到文本模式（停止语音监听）\n"
                "  voice        — 切换到语音模式（启动语音监听）\n"
                "  stt <秒数>   — 录制 N 秒并转文字\n"
                "  nlu <文本>   — 直接测试意图理解\n"
                "  help         — 显示此帮助\n"
                "  quit         — 退出灵枢\n"
            )
        elif cmd == "status":
            if monitor:
                monitor.print_status()
            else:
                print("系统监控模块未加载")
        elif cmd == "config":
            import json
            print(json.dumps(config, indent=2, ensure_ascii=False))
        elif cmd == "modules":
            mods = {
                "monitor": monitor is not None,
                "voice": voice is not None and (voice.is_ready() or voice.is_partial_ready()),
                "vision": vision is not None,
                "executor": executor is not None,
                "memory": memory is not None,
            }
            for name, ok in mods.items():
                status = "✅ 已加载" if ok else "❌ 未就绪"
                print(f"  {name:12s} {status}")

        elif cmd == "listen":
            if voice and voice.is_ready():
                print("[Voice] 手动触发录音，请说话...")
                result = voice.record_and_understand()
                if result:
                    intent = result.get("intent", {})
                    print(f'  转录: "{result.get("text", "")}"')
                    print(f'  意图: {json.dumps(intent, ensure_ascii=False, indent=2)}')
                else:
                    print("  未检测到语音或识别失败")
            else:
                print("语音模块未就绪，无法录音")

        elif cmd == "voice":
            if voice and voice.is_ready():
                voice.start_continuous_listening(on_intent_detected)
                print("🎙️  已启动语音监听模式（唤醒词 + VAD）")
            else:
                print("语音模块未就绪")

        elif cmd == "text":
            if voice:
                voice.stop_continuous_listening()
                print("⌨️  已停止语音监听，切换到文本模式")
            else:
                print("语音模块未加载")

        elif cmd.startswith("stt "):
            parts = user_input.split(maxsplit=1)
            duration = float(parts[1]) if len(parts) > 1 else 5.0
            if voice and voice.is_ready():
                print(f"[Voice] 录制 {duration} 秒...")
                text = voice.record_and_transcribe(duration=duration)
                print(f'  ASR 结果: "{text}"')
            else:
                print("语音模块未就绪")

        elif cmd.startswith("nlu "):
            parts = user_input.split(maxsplit=1)
            if len(parts) > 1 and voice:
                text = parts[1]
                result = voice.process_text(text)
                intent = result.get("intent", {})
                print(f'  输入: "{text}"')
                print(f'  意图: {json.dumps(intent, ensure_ascii=False, indent=2)}')
            else:
                print("用法: nlu <要分析的文本>")

        elif cmd.startswith("record "):
            parts = user_input.split(maxsplit=1)
            duration = float(parts[1]) if len(parts) > 1 else 5.0
            if voice and voice.is_ready():
                print(f"[Voice] 录制 {duration} 秒并保存...")
                audio, _ = voice._vad.record_fixed_duration(duration)
                if audio:
                    from datetime import datetime
                    fname = f"record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                    save_path = root / "logs" / fname
                    voice.save_audio(audio, save_path)
                    print(f"  已保存: {save_path}")
                else:
                    print("  录制失败")
            else:
                print("语音模块未就绪")

        else:
            if voice and voice.is_ready():
                result = voice.process_text(user_input)
                intent = result.get("intent", {})
                print(f'[NLU] 意图解析: {json.dumps(intent, ensure_ascii=False, indent=2)}')
            else:
                print(f"未知命令: '{user_input}'。输入 'help' 查看帮助。")

    logger.info("灵枢正在关闭...")
    if voice:
        voice.stop_continuous_listening()
    if monitor:
        monitor.stop()
        logger.info("系统监控已停止")
    logger.info("灵枢已安全退出")


if __name__ == "__main__":
    main()
