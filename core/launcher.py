#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 启动器主入口（v0.2.0 进化版）
整合：Phase 1-2 + 增补卷（GUI、声纹锁、授权、硬件控制）+ 进化卷（主动智能、自进化、多智能体）

负责：配置加载、日志初始化、全部模块编排、生命周期管理、主循环
"""

import argparse
import sys
import os
import json
import threading
import time
from pathlib import Path


def resolve_root() -> Path:
    """解析灵枢根目录（U盘挂载点）"""
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
    """打印启动横幅"""
    from rich.console import Console
    from rich.panel import Panel
    console = Console()
    name = config.get("app", {}).get("name", "灵枢")
    version = config.get("app", {}).get("version", "0.3.0")
    console.print(Panel.fit(
        f"[bold cyan]{name}[/bold cyan] [dim]v{version}[/dim]\n"
        f"[italic]超级电脑元神 · 数字生命体运行时[/italic]\n"
        f'[green]"灵枢在此，主上何令？"[/green]',
        title="启动",
        border_style="bright_blue",
    ))


def main():
    parser = argparse.ArgumentParser(description="灵枢（LingShu）Agent 启动器")
    parser.add_argument("--root", type=str, default=None, help="灵枢根目录路径")
    parser.add_argument("--config", type=str, default=None, help="自定义配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="模拟执行模式")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    parser.add_argument("--no-gui", action="store_true", help="禁用图形界面")
    parser.add_argument("--skip-auth", action="store_true", help="跳过授权检查（仅开发）")
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

    # ============================================================
    # 模块 1: 系统监控（观星术）
    # ============================================================
    try:
        from core.monitor import SystemMonitor
        monitor = SystemMonitor(config.get("monitor", {}), root)
        monitor.start()
        logger.info("系统监控模块已启动")
    except ImportError:
        logger.warning("系统监控模块未就绪")
        monitor = None

    # ============================================================
    # 模块 2: 授权控制（增补卷十二）
    # ============================================================
    auth = None
    try:
        from core.auth import AuthManager
        auth = AuthManager(root, config.get("auth", {}))
        logger.info("授权控制模块已加载")
        if not args.skip_auth and auth.is_first_use():
            print("\n" + "=" * 60)
            print(auth.get_authorization_text())
            print("=" * 60 + "\n")
            print("⚠️  首次使用：请手动完成授权（输入 'auth' 同意授权）\n")
    except ImportError as e:
        logger.warning(f"授权控制模块加载失败: {e}")

    # ============================================================
    # 模块 3: 声纹识别（增补卷十三）
    # ============================================================
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
        logger.info("声纹识别模块已加载")
    except ImportError as e:
        logger.warning(f"声纹识别模块加载失败: {e}")

    # ============================================================
    # 模块 4: 语音交互（Phase 2）
    # ============================================================
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
            logger.info("语音模块已加载（VAD + ASR + NLU）")
        elif voice.is_partial_ready():
            logger.info("语音模块部分就绪（ASR 可用）")
        else:
            logger.warning("语音模块未就绪")
    except ImportError as e:
        logger.warning(f"语音模块未就绪: {e}")
        voice = None

    # ============================================================
    # 模块 5: 主动智能（进化卷一）
    # ============================================================
    proactive = None
    try:
        from core.proactive import ProactiveEngine
        proactive = ProactiveEngine(config.get("proactive", {}), root)
        if proactive.is_enabled():
            proactive.start()
            logger.info("主动智能引擎已启动")
    except ImportError as e:
        logger.warning(f"主动智能模块未就绪: {e}")

    # ============================================================
    # 模块 6: 硬件控制（增补卷十四 + 进化卷六）
    # ============================================================
    hardware = None
    try:
        from core.hardware import HardwareController
        hardware = HardwareController(config.get("hardware", {}), root)
        logger.info(f"硬件控制模块已加载，当前场景: {hardware.get_scene()}")
    except ImportError as e:
        logger.warning(f"硬件控制模块未就绪: {e}")

    # ============================================================
    # ============================================================
    # 模块 7: 视觉模块（Phase 4 — 视觉理解）
    # ============================================================
    try:
        from core.vision import VisionModule, VisionCapability
        vision = VisionModule(
            config.get("models", {}).get("vlm", {}),
            root=root,
        )
        cap = vision.get_capability()
        if cap.value >= VisionCapability.VLM.value:
            logger.info("视觉模块已加载（VLM 视觉理解）")
        elif cap.value >= VisionCapability.SCREENSHOT.value:
            logger.info("视觉模块已加载（截图 + 降级分析）")
        else:
            logger.warning("视觉模块后端不可用")
    except ImportError as e:
        logger.warning(f"视觉模块加载失败: {e}")
        vision = None

    # ============================================================
    # 模块 8: 执行模块（Phase 5 执行引擎）
    # ============================================================
    try:
        from core.executor import ExecutorModule
        executor = ExecutorModule(
            config.get("executor", {}),
            root=root,
            auth_manager=auth,
            vision_module=vision,
        )
        logger.info("执行模块已加载（键鼠模拟 + 安全确认 + 回滚）")
    except ImportError as e:
        logger.warning(f"执行模块未就绪: {e}")
        executor = None

    # ============================================================
    # 模块 8.5: 数字孪生（进化卷 — 沙箱预演引擎）
    # ============================================================
    twin = None
    try:
        from core.digital_twin import DigitalTwin, RehearsalMode
        twin_config = config.get("digital_twin", {})
        twin = DigitalTwin(twin_config, root=root, vision_module=vision)
        if twin.is_enabled():
            logger.info(f"数字孪生沙箱已启动（模式: {twin.mode.value}）")
        else:
            logger.info("数字孪生沙箱已加载（当前关闭）")
    except ImportError as e:
        logger.warning(f"数字孪生模块未就绪: {e}")

    # ============================================================
    # 模块 9: 记忆模块（Phase 6 记忆引擎）
    # ============================================================
    try:
        from core.memory import MemoryModule
        memory = MemoryModule(
            config.get("memory", {}),
            root=root,
            executor=executor,
        )
        logger.info(f"记忆模块已加载（录制回放 + 向量库 + 知识积累）")
    except ImportError as e:
        logger.warning(f"记忆模块未就绪: {e}")
        memory = None

    # ============================================================
    # 模块 10: 图形界面（增补卷十一）
    # ============================================================
    gui = None
    if not args.no_gui:
        try:
            from core.gui import LingShuGUI
            gui = LingShuGUI(
                config.get("gui", {}),
                root,
                on_command=lambda cmd: f"收到指令: {cmd}",
                on_auth_grant=lambda: auth.grant_authorization() if auth else False,
                on_auth_revoke=lambda: auth.revoke_authorization() if auth else False,
            )
            if gui.is_available():
                gui.start(blocking=False)
                logger.info("灵枢台图形界面已启动")
        except ImportError as e:
            logger.warning(f"图形界面模块未就绪: {e}")

    # ============================================================
    # 主循环（语音 + 文本 + 授权 + 声纹 + 主动智能）
    # ============================================================
    logger.info("进入主循环...")
    use_voice = voice is not None and voice.is_ready()
    skip_wake = config.get("development", {}).get("skip_wake_word", False)
    verbose = config.get("development", {}).get("verbose_mode", True)

    # 主动智能建议回调
    def on_proactive_suggestion(suggestion):
        if gui:
            gui.add_log(f"💡 主动建议: {suggestion.title} - {suggestion.description}")
        if verbose:
            print(f"\n💡 [主动建议] {suggestion.title} ({suggestion.confidence:.0%})")
            print(f"   {suggestion.description}")
            if suggestion.suggested_action:
                print(f"   → 建议操作: {suggestion.suggested_action}")

    if proactive:
        proactive._on_suggestion = on_proactive_suggestion

    # 语音意图处理
    def on_intent_detected(result: dict):
        intent_data = result.get("intent", {})
        intent_type = intent_data.get("intent", "unknown")
        raw_text = intent_data.get("raw_text", "")
        print(f'\n[🎙️ 语音指令] "{raw_text}" → intent={intent_type}')

        # 权限检查
        if auth and not auth.is_authorized():
            print("  → ❌ 灵枢未获授权，拒绝执行")
            return

        # 声纹验证（如果已注册）
        if speaker and speaker.has_enrolled_users():
            # 声纹验证在语音录制阶段已完成（理想）
            # 实际应在 record_and_understand 中集成
            pass

        # 权限检查
        if auth:
            allowed, level, msg = auth.check_permission(intent_type, is_speaker_verified=True)
            if not allowed:
                print(f"  → ❌ 权限拒绝: {msg}")
                return
            print(f"  → ℹ️ 权限: {msg}")

        # 审计日志
        if auth:
            auth.log_operation(intent_type, raw_text, "pending")

        # 场景模式指令
        if hardware and hardware.is_command_allowed(intent_type):
            result = hardware.execute_scene_command(intent_type, intent_data.get("params", {}))
            if result:
                print(f"  → ✅ 硬件控制已执行")
                return

        # 日常操作
        if intent_type == "open" and voice:
            target = intent_data.get("target", "")
            if target:
                print(f"  → 执行: 打开 {target}")
        elif intent_type == "unknown":
            print("  → 未识别意图，请重试")

    # 启动后台语音监听
    if use_voice and not skip_wake:
        voice.start_continuous_listening(on_intent_detected)
        print("\n🎙️  语音模式已激活。说出唤醒词 \"灵枢\" 开始指令。\n")
    else:
        print("\n⌨️  当前为文本模式。输入 'help' 查看命令，'quit' 退出。\n")

    # 主循环
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
                "  auth         — 查看授权状态并授权\n"
                "  revoke       — 撤销授权（一键急停）\n"
                "  speaker      — 声纹管理（注册/验证/列表）\n"
                "  scene        — 切换硬件场景（computer/stage/hotel/meeting）\n"
                "  listen       — 手动触发语音录制\n"
                "  voice        — 启动语音监听\n"
                "  text         — 停止语音监听\n"
                "  stt <秒>     — 录制N秒并转文字\n"
                "  nlu <文本>   — 测试意图理解\n"
                "  screenshot   — 截取屏幕并保存到 logs/\n"
                "  look [提问]  — 截图并用 VLM 分析屏幕\n"
                "  vision info  — 查看视觉模块状态\n"
                "  exec         — 执行操作（click/type/move/scroll/hotkey/undo）\n"
                "  exec status  — 查看执行模块状态\n"
                "  exec history — 查看操作历史\n"
                "  undo         — 撤销最近操作\n"
                "  redo         — 重做最近撤销\n"
                "  memory       — 记忆管理（search/store/record/replay/list）\n"
                "  twin         — 数字孪生沙箱预演（rehearse/simulate/status）\n"
                "  modules      — 查看已加载模块\n"
                "  config       — 查看当前配置\n"
                "  help         — 显示此帮助\n"
                "  quit         — 退出灵枢\n"
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
                    confirm = input("确认授权？输入 'yes' 同意: ").strip().lower()
                    if confirm == "yes":
                        auth.grant_authorization()
                    else:
                        print("授权已取消")
            else:
                print("授权模块未加载")

        elif cmd == "revoke":
            if auth:
                auth.revoke_authorization()
            else:
                print("授权模块未加载")

        elif cmd == "speaker":
            if not speaker:
                print("声纹模块未加载")
                continue
            print("\n声纹管理:")
            print("  1. 注册声纹 (register)")
            print("  2. 验证声纹 (verify)")
            print("  3. 用户列表 (list)")
            print("  4. 删除用户 (delete)")
            sub = input("选择操作: ").strip().lower()
            if sub == "register":
                if not voice or not voice.is_ready():
                    print("语音模块未就绪，无法录制")
                    continue
                name = input("请输入用户名称: ").strip()
                uid = f"user_{int(time.time())}"
                print(f"请朗读以下文本，共5次:\n  \"灵枢在此，主上何令？\"")
                samples = []
                for i in range(5):
                    input(f"第 {i+1}/5 次，按回车开始录制...")
                    audio, _ = voice._vad.record_fixed_duration(3.0)
                    if audio:
                        samples.append(audio)
                        print("  ✅ 录制完成")
                    else:
                        print("  ❌ 录制失败")
                if len(samples) >= 3:
                    ok, msg = speaker.enroll(uid, name, samples)
                    print(msg)
                else:
                    print("❌ 样本不足，注册失败")
            elif sub == "verify":
                if not voice or not voice.is_ready():
                    print("语音模块未就绪")
                    continue
                input("按回车开始录制验证语音...")
                audio, _ = voice._vad.record_fixed_duration(3.0)
                if audio:
                    ok, uid, score = speaker.verify(audio)
                    if ok and uid != "guest":
                        name = speaker.get_user_name(uid) or uid
                        print(f"✅ 验证通过: {name} (相似度: {score:.3f})")
                    else:
                        print(f"❌ 验证失败 (相似度: {score:.3f})")
                else:
                    print("❌ 录制失败")
            elif sub == "list":
                users = speaker.list_users()
                if users:
                    for u in users:
                        status = "✅" if u["is_active"] else "❌"
                        print(f"  {status} {u['name']} ({u['user_id']}) - {u['sample_count']} 样本")
                else:
                    print("  暂无注册用户")
            elif sub == "delete":
                uid = input("输入用户ID: ").strip()
                if speaker.delete_user(uid):
                    print("✅ 已删除")
                else:
                    print("❌ 删除失败")

        elif cmd == "scene":
            if not hardware:
                print("硬件控制模块未加载")
                continue
            print("可选场景: computer / stage / hotel / meeting")
            new_scene = input("输入场景名称: ").strip().lower()
            if hardware.set_scene(new_scene):
                print(f"✅ 场景已切换为: {new_scene}")
            else:
                print("❌ 场景切换失败")

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
                print("语音模块未就绪")

        elif cmd == "voice":
            if voice and voice.is_ready():
                voice.start_continuous_listening(on_intent_detected)
                print("🎙️  已启动语音监听模式")
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

        elif cmd == "proactive":
            if not proactive:
                print("主动智能模块未加载")
                continue
            suggestions = proactive.get_pending_suggestions()
            if suggestions:
                for s in suggestions:
                    print(f"\n💡 {s.title} ({s.confidence:.0%} 置信度)")
                    print(f"   {s.description}")
                    if s.suggested_action:
                        print(f"   → 建议操作: {s.suggested_action}")
            else:
                print("暂无待处理建议")

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
                "digital_twin": twin is not None and twin.is_enabled(),
            }
            for name, ok in mods.items():
                status = "✅ 已加载" if ok else "❌ 未就绪"
                print(f"  {name:15s} {status}")

        elif cmd == "vision":
            if not vision:
                print("视觉模块未加载")
                continue
            cap = vision.get_capability()
            print(f"视觉模块状态: {cap.name}")
            if cap.value >= 1:
                print(f"  截图后端: {vision._capture_backend}")
            if cap.value >= 3:
                print("  VLM 模型: 已加载")
            else:
                print("  VLM 模型: 未加载（首次调用时会尝试加载）")
            print(f"  屏幕分辨率: {vision.get_screen_size()}")

        elif cmd.startswith("look"):
            if not vision:
                print("视觉模块未加载")
                continue
            query = user_input[4:].strip() or "描述当前屏幕内容"
            print(f"[Vision] 📸 截图中... 查询: {query}")
            result = vision.analyze(query)
            print(f"\n🔍 场景描述: {result.scene_description}")
            if result.elements:
                print(f"  检测到 {len(result.elements)} 个元素:")
                for e in result.elements[:10]:
                    coords = f"[{e.bbox[0]},{e.bbox[1]}->{e.bbox[2]},{e.bbox[3]}]"
                    print(f"    - {e.element_type}: {e.description[:40]} {coords}")
            if result.suggested_actions:
                print(f"  建议操作:")
                for a in result.suggested_actions[:5]:
                    print(f"    - {a}")

        elif cmd == "screenshot":
            if not vision:
                print("视觉模块未加载")
                continue
            from datetime import datetime
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = root / "logs" / f"screenshot_{ts}.jpg"
            if vision.capture_to_file(path):
                print(f"✅ 截图已保存: {path}")
            else:
                print("❌ 截图失败")

        elif cmd == "config":
            print(json.dumps(config, indent=2, ensure_ascii=False))

        elif cmd == "undo":
            if not executor:
                print("执行模块未加载")
                continue
            if executor.can_undo():
                undone = executor.undo(1)
                if undone:
                    print(f"✅ 已撤销 {len(undone)} 个操作")
                else:
                    print("⚠️ 撤销操作执行失败")
            else:
                print("无操作可撤销")

        elif cmd == "redo":
            if not executor:
                print("执行模块未加载")
                continue
            if executor.can_redo():
                redone = executor.redo(1)
                if redone:
                    print(f"✅ 已重做 {len(redone)} 个操作")
                else:
                    print("⚠️ 重做操作执行失败")
            else:
                print("无操作可重做")

        elif cmd == "exec status":
            if not executor:
                print("执行模块未加载")
                continue
            status = executor.get_status()
            print(f"执行模块状态:")
            print(f"  就绪: {'✅' if status['ready'] else '❌'}")
            print(f"  安全级别: {status['safety_level']}")
            print(f"  演习模式: {'✅' if status['dry_run'] else '❌'}")
            print(f"  屏幕分辨率: {status['screen_size']}")
            print(f"  历史操作: {status['history_count']}")
            print(f"  可撤销: {'✅' if status['can_undo'] else '❌'}")
            print(f"  可重做: {'✅' if status['can_redo'] else '❌'}")

        elif cmd == "exec history":
            if not executor:
                print("执行模块未加载")
                continue
            history = executor.get_history(20)
            if history:
                print(f"最近 {len(history)} 个操作:")
                for h in history:
                    status = "✅" if h['success'] else "❌"
                    confirmed = "🔒" if h['confirmed'] else ""
                    print(f"  {status} {confirmed} [{h['time']}] {h['type']:20s} {h['desc']}")
            else:
                print("暂无操作历史")

        elif cmd.startswith("exec "):
            if not executor:
                print("执行模块未加载")
                continue
            parts = user_input.split(maxsplit=3)
            if len(parts) < 2:
                print("用法: exec <click/move/type/scroll/hotkey/shell/screenshot/wait>")
                continue

            sub_cmd = parts[1].lower()
            try:
                if sub_cmd == "click":
                    if len(parts) < 4:
                        # 执行当前鼠标位置的点击
                        executor.click(0, 0)
                    else:
                        coords = parts[2].split(",")
                        x, y = int(coords[0]), int(coords[1])
                        executor.click(x, y)

                elif sub_cmd == "move":
                    if len(parts) < 4:
                        print("用法: exec move <x>,<y>")
                        continue
                    coords = parts[2].split(",")
                    x, y = int(coords[0]), int(coords[1])
                    executor.move(x, y)

                elif sub_cmd == "type":
                    text = parts[2] if len(parts) > 2 else ""
                    executor.type_text(text)

                elif sub_cmd == "scroll":
                    clicks = int(parts[2]) if len(parts) > 2 else 3
                    executor.scroll(clicks)

                elif sub_cmd == "hotkey":
                    keys = parts[2].split(",") if len(parts) > 2 else []
                    executor.hotkey(*keys)

                elif sub_cmd == "shell":
                    command = parts[2] if len(parts) > 2 else ""
                    executor.shell(command)

                elif sub_cmd == "screenshot":
                    executor.screenshot()

                elif sub_cmd == "wait":
                    seconds = float(parts[2]) if len(parts) > 2 else 1.0
                    executor.wait(seconds)

                else:
                    print(f"未知 exec 子命令: {sub_cmd}")
                    print("支持的子命令: click, move, type, scroll, hotkey, shell, screenshot, wait")
            except Exception as e:
                print(f"❌ 执行失败: {e}")

        elif cmd.startswith("memory"):
            if not memory:
                print("记忆模块未加载")
                continue
            parts = user_input.split(maxsplit=3)
            if len(parts) < 2:
                print("用法: memory <search/store/record/replay/list/stats>")
                continue

            sub_cmd = parts[1].lower()
            try:
                if sub_cmd == "search":
                    query = parts[2] if len(parts) > 2 else ""
                    top_k = int(parts[3]) if len(parts) > 3 else 5
                    results = memory.search(query, top_k=top_k)
                    if results:
                        print(f"找到 {len(results)} 条相关记忆:")
                        for r in results:
                            sim = r.get('similarity', 0)
                            print(f"  [{r['memory_type']}] (相似度: {sim:.2f}) {r['content'][:100]}...")
                    else:
                        print("未找到相关记忆")

                elif sub_cmd == "store":
                    content = parts[2] if len(parts) > 2 else ""
                    if not content:
                        print("用法: memory store <内容>")
                        continue
                    mid = memory.store_knowledge(content)
                    print(f"✅ 知识已存储: {mid}")

                elif sub_cmd == "list":
                    mem_type = parts[2] if len(parts) > 2 else None
                    entries = memory.list_memories(memory_type=mem_type, limit=20)
                    if entries:
                        print(f"最近 {len(entries)} 条记忆:")
                        for e in entries[:10]:
                            print(f"  [{e['memory_type']}] {e['content'][:80]}... (分数: {e.get('score', 1.0):.2f})")
                    else:
                        print("暂无记忆")

                elif sub_cmd == "record":
                    if not executor:
                        print("执行模块未加载，无法录制")
                        continue
                    history = executor.get_history(50)
                    if not history:
                        print("无操作可录制")
                        continue
                    actions = []
                    for h in history:
                        from core.executor import ActionType
                        try:
                            at = ActionType[h['type']]
                        except KeyError:
                            continue
                        actions.append({
                            "action_type": h['type'],
                            "description": h['desc'],
                            "params": {},
                        })
                    name = parts[2] if len(parts) > 2 else f"录制_{int(time.time())}"
                    rid = memory.store_action_record(name, actions)
                    print(f"✅ 操作录制已保存: {rid} ({len(actions)} 个操作)")

                elif sub_cmd == "replay":
                    rid = parts[2] if len(parts) > 2 else ""
                    if not rid:
                        print("用法: memory replay <record_id>")
                        continue
                    success = memory.replay_record(rid, executor=executor)
                    print(f"{'✅' if success else '❌'} 回放{'成功' if success else '失败'}")

                elif sub_cmd == "stats":
                    stats = memory.get_stats()
                    print(f"记忆统计:")
                    print(f"  总条目: {stats['total_entries']}")
                    print(f"  录制数: {stats['total_records']}")
                    print(f"  类型分布: {stats['type_distribution']}")
                    print(f"  平均分数: {stats['avg_score']:.2f}")
                    print(f"  ChromaDB: {'✅' if stats['chromadb_ready'] else '❌'}")
                    print(f"  嵌入模型: {'✅' if stats['embedding_ready'] else '❌'}")

                else:
                    print(f"未知 memory 子命令: {sub_cmd}")
                    print("支持的子命令: search, store, list, record, replay, stats")
            except Exception as e:
                print(f"❌ 记忆操作失败: {e}")

        elif cmd.startswith("twin"):
            if not twin:
                print("数字孪生模块未加载")
                continue
            sub_cmd = user_input.split(" ")[1] if len(user_input.split(" ")) > 1 else ""
            if not sub_cmd or sub_cmd == "status":
                print(f"数字孪生状态: {'✅ 启用' if twin.is_enabled() else '❌ 关闭'}")
                print(f"  预演模式: {twin.mode.value}")
                print(f"  高风险阈值: {twin.high_risk_threshold}")
                print(f"  沙箱环境: {'✅ 就绪' if twin.sandbox_enabled else '❌ 不可用'}")
                print(f"  已捕获快照: {len(twin._snapshots)} 次")
            elif sub_cmd == "simulate" or sub_cmd == "rehearse":
                if not twin.is_enabled():
                    print("数字孪生当前关闭，请在配置中启用")
                    continue
                action_type = input("操作类型 (click/type/move/scroll/hotkey/shell): ").strip().upper()
                if action_type == "CLICK":
                    x = int(input("X 坐标: ").strip())
                    y = int(input("Y 坐标: ").strip())
                    action = {"action_type": "MOUSE_CLICK", "params": {"x": x, "y": y}, "description": f"点击 ({x}, {y})"}
                elif action_type == "TYPE":
                    text = input("输入文本: ").strip()
                    action = {"action_type": "KEYBOARD_TYPE", "params": {"text": text}, "description": f"输入: {text[:20]}"}
                elif action_type == "MOVE":
                    x = int(input("X 坐标: ").strip())
                    y = int(input("Y 坐标: ").strip())
                    action = {"action_type": "MOUSE_MOVE", "params": {"x": x, "y": y}, "description": f"移动至 ({x}, {y})"}
                elif action_type == "SCROLL":
                    clicks = int(input("滚动格数 (正=下, 负=上): ").strip())
                    action = {"action_type": "MOUSE_SCROLL", "params": {"clicks": clicks}, "description": f"滚动 {clicks} 格"}
                elif action_type == "HOTKEY":
                    keys = input("组合键 (空格分隔, 如 ctrl c): ").strip().split()
                    action = {"action_type": "KEYBOARD_HOTKEY", "params": {"keys": keys}, "description": f"热键: {'+'.join(keys)}"}
                elif action_type == "SHELL":
                    command = input("Shell 命令: ").strip()
                    action = {"action_type": "SHELL_EXEC", "params": {"command": command}, "description": f"Shell: {command[:40]}"}
                else:
                    print("不支持的操作类型")
                    continue

                print("\n🔄 正在沙箱预演...")
                report = twin.simulate(action)
                print(twin.format_report(report))
                print(f"\n总结: 风险 {report.overall_risk_score}/100 ({report.overall_risk_level.name}) | 建议: {report.recommendation}")
            elif sub_cmd == "snapshot":
                snap = twin.capture_snapshot()
                print(f"快照已捕获: {time.strftime('%H:%M:%S', time.localtime(snap.timestamp))}")
                if snap.mouse_position:
                    print(f"  鼠标位置: {snap.mouse_position}")
                if snap.active_window:
                    print(f"  活动窗口: {snap.active_window}")
            elif sub_cmd == "mode":
                print(f"当前模式: {twin.mode.value}")
                print("可选模式: strict / advisory / off")
            else:
                print(f"未知 twin 子命令: {sub_cmd}")
                print("支持的子命令: status, simulate, rehearse, snapshot, mode")

        else:
            # 文本模式：直接处理为自然语言输入
            if voice and voice.is_ready():
                result = voice.process_text(user_input)
                intent = result.get("intent", {})
                print(f'[NLU] 意图解析: {json.dumps(intent, ensure_ascii=False, indent=2)}')
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
    if vision:
        vision.stop_continuous_capture()
    logger.info("灵枢已安全退出，所有控制已释放。")


if __name__ == "__main__":
    main()
