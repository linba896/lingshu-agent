#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 主程序启动器（v0.2.0 进化版）
功能：初始化环境、加载配置、启动核心模块监控循环、管理用户交互

支持的模块：
  - 系统监控 (monitor)
  - 语音交互 (voice: ASR + VAD + NLU + WakeWord)
  - 声纹验证 (speaker)
  - 授权管理 (auth)
  - 硬件控制 (hardware)
  - 主动服务 (proactive)
  - 视觉理解 (vision)
  - 执行操作 (executor)
  - 记忆学习 (memory)
  - GUI 面板 (gui)

版本历史：
  v0.1.0 - 初始骨架 + 启动脚本 + 环境构建
  v0.2.0 - 进化版：加入 Phase 2.5-3 的声纹/授权/硬件/主动服务/进化/多智能体

使用方式：
  python core/launcher.py [--root PATH] [--config PATH] [--dry-run] [--debug] [--no-gui] [--skip-auth]

"""

import argparse
import sys
import os
import json
import threading
import time
from pathlib import Path

def resolve_root() -> Path:
    """推断项目根目录：脚本所在目录的父目录"""
    core_dir = Path(__file__).resolve().parent
    root = core_dir.parent
    return root

def load_config(root: Path) -> dict:
    """加载 YAML 配置文件"""
    import yaml
    config_path = root / "config" / "lingshu.yaml"
    if not config_path.exists():
        print(f"[WARN] 配置文件不存在: {config_path}，将使用空配置")
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def init_logger(config: dict, root: Path):
    """初始化日志系统"""
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
    """环境预检"""
    import platform
    checks = []
    py_ver = sys.version_info
    checks.append(("Python 版本", f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}", py_ver >= (3, 9)))
    for name, subdir in [("配置目录", "config"), ("核心代码", "core"), ("日志目录", "logs")]:
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
    print("  灵枢环境预检")
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
    version = config.get("app", {}).get("version", "0.2.0")
    console.print(Panel.fit(
        f"[bold cyan]{name}[/bold cyan] [dim]v{version}[/dim]\n"
        f"[italic]自主感知 · 智能交互 · 持续进化 · 全能守护[/italic]\n"
        f'[green]"灵枢所辖，万物听令；心有灵犀，无远弗届。"[/green]',
        title="启动",
        border_style="bright_blue",
    ))


def main():
    parser = argparse.ArgumentParser(description="灵枢（LingShu）Agent 启动器")
    parser.add_argument("--root", type=str, default=None, help="项目根目录路径")
    parser.add_argument("--config", type=str, default=None, help="覆盖配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="仅检查环境不启动模块")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    parser.add_argument("--no-gui", action="store_true", help="禁用 GUI 面板")
    parser.add_argument("--skip-auth", action="store_true", help="跳过授权检查（仅开发调试用）")
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
    logger.info(f"项目根目录: {root}")

    if not check_environment(root, config):
        logger.error("环境预检失败，请运行 scripts/build_portable_env.py 构建环境")
        sys.exit(1)

    logger.info("环境预检通过，正在加载核心模块...")

    # ========== 模块 1: 系统监控 ==========
    try:
        from core.monitor import SystemMonitor
        monitor = SystemMonitor(config.get("monitor", {}), root)
        monitor.start()
        logger.info("系统监控模块已启动")
    except ImportError:
        logger.warning("系统监控模块加载失败，跳过")
        monitor = None

    # ========== 模块 2: 授权管理（Phase 2.5） ==========
    auth = None
    try:
        from core.auth import AuthManager
        auth = AuthManager(root, config.get("auth", {}))
        logger.info("授权管理模块已加载")
        if not args.skip_auth and auth.is_first_use():
            print("\n" + "=" * 60)
            print(auth.get_authorization_text())
            print("=" * 60 + "\n")
            print("📝 提示：首次使用请授权。输入 'auth' 进行授权。\n")
    except ImportError as e:
        logger.warning(f"授权管理模块加载失败: {e}")

    # ========== 模块 3: 声纹验证（Phase 2.5） ==========
    speaker = None
    try:
        from core.speaker import SpeakerVerifier
        speaker_config = config.get("speaker", {})
        profile_dir = root / speaker_config.get("profile_dir", "config/speaker_profiles")
        speaker = SpeakerVerifier(
            profile_dir=profile_dir,
            threshold=speaker_config.get("similarity_threshold", 0.85),
            verify_mode=speaker_config.get("verify_mode", "strict"),
            max_users=speaker_config.get("max_users", 10),
        )
        logger.info("声纹验证模块已加载")
    except ImportError as e:
        logger.warning(f"声纹验证模块加载失败: {e}")

    # ========== 模块 4: 语音交互（Phase 2） ==========
    voice = None
    try:
        from core.asr import VoiceModule
        voice = VoiceModule(
            config.get("voice", {}),
            config.get("models", {}).get("asr", {}),
            config.get("models", {}).get("nlu", {}),
            root,
        )
        if voice.is_ready():
            logger.info("语音交互模块已就绪（VAD + ASR + NLU）")
        elif voice.is_partial_ready():
            logger.info("语音交互模块部分就绪（ASR 可用）")
        else:
            logger.warning("语音交互模块未就绪")
    except ImportError as e:
        logger.warning(f"语音交互模块加载失败: {e}")
        voice = None

    # ========== 模块 5: 主动服务（Phase 3） ==========
    proactive = None
    try:
        from core.proactive import ProactiveEngine
        proactive = ProactiveEngine(config.get("proactive", {}), root)
        if proactive.is_enabled():
            proactive.start()
            logger.info("主动服务引擎已启动")
    except ImportError as e:
        logger.warning(f"主动服务模块加载失败: {e}")

    # ========== 模块 6: 硬件控制（Phase 2.5 + 3） ==========
    hardware = None
    try:
        from core.hardware import HardwareController
        hardware = HardwareController(config.get("hardware", {}), root)
        logger.info(f"硬件控制模块已加载，默认场景: {hardware.get_scene()}")
    except ImportError as e:
        logger.warning(f"硬件控制模块加载失败: {e}")

    # ========== 模块 7: 视觉理解（Phase 3） ==========
    try:
        from core.vision import VisionModule
        vision = VisionModule(config.get("models", {}).get("vlm", {}))
        logger.info("视觉理解模块已加载")
    except ImportError:
        logger.warning("视觉理解模块未加载（Phase 3 开发中）")
        vision = None

    # ========== 模块 8: 执行操作（Phase 4） ==========
    try:
        from core.executor import ExecutorModule
        executor = ExecutorModule(config.get("executor", {}))
        logger.info("执行操作模块已加载")
    except ImportError:
        logger.warning("执行操作模块未加载（Phase 4 开发中）")
        executor = None

    # ========== 模块 9: 记忆学习（Phase 5） ==========
    try:
        from core.memory import MemoryModule
        memory = MemoryModule(config.get("memory", {}), root)
        logger.info("记忆学习模块已加载")
    except ImportError:
        logger.warning("记忆学习模块未加载（Phase 5 开发中）")
        memory = None

    # ========== 模块 10: GUI 面板（Phase 2.5） ==========
    gui = None
    if not args.no_gui:
        try:
            from core.gui import LingShuGUI
            gui = LingShuGUI(
                config.get("gui", {}),
                root,
                on_command=lambda cmd: f"执行命令: {cmd}",
                on_auth_grant=lambda: auth.grant_authorization() if auth else False,
                on_auth_revoke=lambda: auth.revoke_authorization() if auth else False,
            )
            if gui.is_available():
                gui.start(blocking=False)
                logger.info("GUI 面板已启动")
        except ImportError as e:
            logger.warning(f"GUI 面板加载失败: {e}")

    # ========== 主循环：语音 + 文本 + 主动服务 ==========
    logger.info("主程序已就绪，等待用户交互...")
    use_voice = voice is not None and voice.is_ready()
    skip_wake = config.get("development", {}).get("skip_wake_word", False)
    verbose = config.get("development", {}).get("verbose_mode", True)

    # 主动服务回调
    def on_proactive_suggestion(suggestion):
        if gui:
            gui.add_log(f"💡 主动建议: {suggestion.title} - {suggestion.description}")
        if verbose:
            print(f"\n💡 [主动建议] {suggestion.title} ({suggestion.confidence:.0%})")
            print(f"  {suggestion.description}")
            if suggestion.suggested_action:
                print(f"  ➡️ 建议操作: {suggestion.suggested_action}")

    if proactive:
        proactive._on_suggestion = on_proactive_suggestion

    # 语音意图处理
    def on_intent_detected(result: dict):
        intent_data = result.get("intent", {})
        intent_type = intent_data.get("intent", "unknown")
        raw_text = intent_data.get("raw_text", "")
        print(f'\n🎙️ [语音指令] "{raw_text}" ➡️ intent={intent_type}')

        # 权限检查
        if auth and not auth.is_authorized():
            print("  ➡️ ⚠️ 灵枢未获得授权，无法执行操作")
            return

        # 声纹验证（如果已注册用户）
        if speaker and speaker.has_enrolled_users():
            # 这里简化处理：实际应使用语音片段进行声纹验证
            # 在语音处理链中集成 speaker.verify()
            pass

        # 权限检查
        if auth:
            allowed, level, msg = auth.check_permission(intent_type, is_speaker_verified=True)
            if not allowed:
                print(f"  ➡️ 🚫 权限不足: {msg}")
                return
            print(f"  ➡️ ✅ 权限级别: {msg}")

        # 记录操作日志
        if auth:
            auth.log_operation(intent_type, raw_text, "pending")

        # 硬件场景控制
        if hardware and hardware.is_command_allowed(intent_type):
            result = hardware.execute_scene_command(intent_type, intent_data.get("params", {}))
            if result:
                print("  ➡️ ✅ 硬件控制指令已执行")
                return

        # 打开文件
        if intent_type == "open" and voice:
            target = intent_data.get("target", "")
            if target:
                print(f"  ➡️ 打开: {target}")
        elif intent_type == "unknown":
            print("  ➡️ 🤔 未识别意图，请重试")

    # 启动语音监听
    if use_voice and not skip_wake:
        voice.start_continuous_listening(on_intent_detected)
        print("\n🎙️  语音监听已启动，唤醒词: \"灵枢\"\n")
    else:
        print("\n⌨️  文本交互模式，输入命令或 'help' 查看帮助\n")

    # 交互循环
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
            print("灵枢再见！")
            break
        elif cmd in ("help", "h"):
            print(
                "\n可用命令:\n"
                "  status      — 查看系统状态\n"
                "  auth        — 授权管理（首次使用）\n"
                "  revoke      — 撤销授权（需要再次授权）\n"
                "  speaker     — 声纹管理（注册/验证/列表/删除）\n"
                "  scene       — 切换硬件场景（computer/stage/hotel/meeting）\n"
                "  listen      — 开始语音识别监听\n"
                "  voice       — 启用语音模式\n"
                "  text        — 切换到文本模式\n"
                "  stt <秒>    — 录音并转文字\n"
                "  nlu <文本>  — 分析文本意图\n"
                "  proactive   — 查看主动服务建议\n"
                "  modules     — 查看已加载模块状态\n"
                "  config      — 查看当前配置\n"
                "  help        — 显示帮助\n"
                "  quit        — 退出程序\n"
            )

        elif cmd == "status":
            if monitor:
                monitor.print_status()
            else:
                print("系统监控模块未加载")

        elif cmd == "auth":
            if auth:
                if auth.is_authorized():
                    print("✅ 灵枢已获授权")
                else:
                    print(auth.get_authorization_text())
                    confirm = input("确认授权? 输入 'yes' 确认: ").strip().lower()
                    if confirm == "yes":
                        auth.grant_authorization()
                    else:
                        print("授权已取消")
            else:
                print("授权管理模块未加载")

        elif cmd == "revoke":
            if auth:
                auth.revoke_authorization()
            else:
                print("授权管理模块未加载")

        elif cmd == "speaker":
            if not speaker:
                print("声纹模块未加载")
                continue
            print("\n声纹管理:")
            print("  1. 注册声纹 (register)")
            print("  2. 验证声纹 (verify)")
            print("  3. 列出用户 (list)")
            print("  4. 删除用户 (delete)")
            sub = input("选择操作: ").strip().lower()
            if sub == "register":
                if not voice or not voice.is_ready():
                    print("语音模块未就绪，请先启用语音")
                    continue
                name = input("请输入用户名称: ").strip()
                uid = f"user_{int(time.time())}"
                print(f"请朗读以下文本 5 次:\n  \"灵枢所辖，万物听令；心有灵犀，无远弗届。\"")
                samples = []
                for i in range(5):
                    input(f"  第 {i+1}/5 次，按回车开始录音...")
                    audio, _ = voice._vad.record_fixed_duration(3.0)
                    if audio:
                        samples.append(audio)
                        print("  ✅ 录音已保存")
                    else:
                        print("  ❌ 录音失败")
                if len(samples) >= 3:
                    ok, msg = speaker.enroll(uid, name, samples)
                    print(msg)
                else:
                    print("❌ 录音样本不足，注册失败")
            elif sub == "verify":
                if not voice or not voice.is_ready():
                    print("语音模块未就绪")
                    continue
                input("按回车开始验证录音...")
                audio, _ = voice._vad.record_fixed_duration(3.0)
                if audio:
                    ok, uid, score = speaker.verify(audio)
                    if ok and uid != "guest":
                        name = speaker.get_user_name(uid) or uid
                        print(f"✅ 验证通过: {name} (相似度: {score:.3f})")
                    else:
                        print(f"❌ 验证失败 (相似度: {score:.3f})")
                else:
                    print("❌ 录音失败")
            elif sub == "list":
                users = speaker.list_users()
                if users:
                    for u in users:
                        status = "✅" if u["is_active"] else "❌"
                        print(f"  {status} {u['name']} ({u['user_id']}) - {u['sample_count']} 样本")
                else:
                    print("  暂无注册用户")
            elif sub == "delete":
                uid = input("输入要删除的用户ID: ").strip()
                if speaker.delete_user(uid):
                    print("✅ 删除成功")
                else:
                    print("❌ 删除失败")

        elif cmd == "scene":
            if not hardware:
                print("硬件控制模块未加载")
                continue
            print("可用场景: computer / stage / hotel / meeting")
            new_scene = input("输入新场景: ").strip().lower()
            if hardware.set_scene(new_scene):
                print(f"✅ 场景切换成功: {new_scene}")
            else:
                print("❌ 场景切换失败")

        elif cmd == "listen":
            if voice and voice.is_ready():
                print("[Voice] 开始监听，按 Ctrl+C 停止...")
                result = voice.record_and_understand()
                if result:
                    intent = result.get("intent", {})
                    print(f'  转录: "{result.get("text", "")}"')
                    print(f'  意图: {json.dumps(intent, ensure_ascii=False, indent=2)}')
                else:
                    print("  未能识别语音指令")
            else:
                print("语音模块未就绪")

        elif cmd == "voice":
            if voice and voice.is_ready():
                voice.start_continuous_listening(on_intent_detected)
                print("🎙️  语音监听已启动，唤醒词: \"灵枢\"")
            else:
                print("语音模块未就绪")

        elif cmd == "text":
            if voice:
                voice.stop_continuous_listening()
            print("⌨️  已切换到文本交互模式，输入命令或 'help' 查看帮助")

        elif cmd.startswith("stt "):
            parts = user_input.split(maxsplit=1)
            duration = float(parts[1]) if len(parts) > 1 else 5.0
            if voice and voice.is_ready():
                print(f"[Voice] 录音 {duration} 秒...")
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
                print(f'  [NLU] 分析: "{text}"')
                print(f'  意图: {json.dumps(intent, ensure_ascii=False, indent=2)}')
            else:
                print("用法: nlu <要分析的文本>")

        elif cmd == "proactive":
            if not proactive:
                print("主动服务模块未加载")
                continue
            suggestions = proactive.get_pending_suggestions()
            if suggestions:
                for s in suggestions:
                    print(f"\n💡 {s.title} ({s.confidence:.0%} 置信度)")
                    print(f"  {s.description}")
                    if s.suggested_action:
                        print(f"  ➡️ 建议操作: {s.suggested_action}")
            else:
                print("暂无主动建议")

        elif cmd == "modules":
            mods = {
                "monitor": monitor is not None,
                "auth": auth is not None,
                "speaker": speaker is not None and speaker.has_enrolled_users(),
                "voice": voice is not None and (voice.is_ready() or voice.is_partial_ready()),
                "proactive": proactive is not None and proactive.is_enabled(),
                "hardware": hardware is not None,
                "gui": gui is not None and gui.is_available(),
                "vision": vision is not None,
                "executor": executor is not None,
                "memory": memory is not None,
            }
            for name, ok in mods.items():
                status = "✅ 已加载" if ok else "❌ 未加载"
                print(f"  {name:15s} {status}")

        elif cmd == "config":
            print(json.dumps(config, indent=2, ensure_ascii=False))

        else:
            # 默认使用 NLU 处理
            if voice and voice.is_ready():
                result = voice.process_text(user_input)
                intent = result.get("intent", {})
                print(f'[NLU] 分析: {json.dumps(intent, ensure_ascii=False, indent=2)}')
            else:
                print(f"未知命令: '{user_input}'。输入 'help' 查看帮助。")

    # 清理
    logger.info("灵枢正在关闭...")
    if voice:
        voice.stop_continuous_listening()
    if monitor:
        monitor.stop()
    if proactive:
        proactive.stop()
    if gui:
        gui.stop()
    logger.info("灵枢已安全关闭，感谢使用！")


if __name__ == "__main__":
    main()
