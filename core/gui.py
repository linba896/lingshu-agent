#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 图形界面模块（增补卷十一：灵枢台）
功能：Gradio可视化界面、状态监控、快捷指令、语音波形、授权弹窗

界面布局：
  ┌────────────────────────────────────────┐
  │  🟢 灵枢 v0.2.0  [待命]  [撤销授权]     │  ← 标题栏 + 状态灯
  ├────────────────────────────────────────┤
  │  🎙️ 语音波形  │  📊 系统资源监控        │  ← 实时状态区
  │  ━━━━━━━━    │  CPU: 45%  MEM: 60%    │
  ├────────────────────────────────────────┤
  │  [整理桌面] [打开PS] [截图] [查询]      │  ← 快捷指令栏
  ├────────────────────────────────────────┤
  │  📝 实时日志（滚动）                    │  ← 日志区
  │  [15:32:01] 灵枢待命...               │
  ├────────────────────────────────────────┤
  │  💬 输入指令或语音唤醒...               │  ← 交互输入区
  └────────────────────────────────────────┘

"""

import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional


class LingShuGUI:
    """
    灵枢台 — Gradio图形界面
    支持：实时状态、语音波形、快捷指令、日志显示、授权弹窗
    """

    def __init__(
        self,
        config: Dict,
        root: Path,
        on_command: Optional[Callable[[str], str]] = None,
        on_auth_grant: Optional[Callable[[], bool]] = None,
        on_auth_revoke: Optional[Callable[[], bool]] = None,
    ):
        self.config = config or {}
        self.root = root
        self.port = config.get("port", 7860)
        self.host = config.get("host", "127.0.0.1")
        self.auto_launch = config.get("auto_launch", True)
        self.theme = config.get("theme", "dark")
        self.refresh_interval = config.get("status_refresh_interval", 2)

        self._on_command = on_command
        self._on_auth_grant = on_auth_grant
        self._on_auth_revoke = on_auth_revoke

        self._app = None
        self._running = False
        self._server_thread: Optional[threading.Thread] = None

        # 状态数据
        self._status = "待命"
        self._status_color = "green"
        self._logs: List[str] = []
        self._cpu_percent = 0.0
        self._memory_percent = 0.0
        self._voice_waveform: List[float] = []

        self._available = False
        self._init_gradio()

    def _init_gradio(self):
        """尝试初始化Gradio"""
        try:
            import gradio as gr
            self._gr = gr
            self._available = True
            print("[GUI] ✅ Gradio 已加载，灵枢台可用")
        except ImportError:
            print("[GUI] ⚠️ Gradio 未安装，灵枢台不可用。请运行: pip install gradio")
            self._available = False

    def is_available(self) -> bool:
        return self._available

    # ============================================================
    # 界面构建
    # ============================================================

    def _build_ui(self):
        """构建Gradio界面"""
        gr = self._gr

        with gr.Blocks(
            title="灵枢台 — 数字元神",
            theme=gr.themes.Soft() if self.theme == "dark" else gr.themes.Default(),
        ) as demo:
            # 状态存储（用于跨组件通信）
            status_state = gr.State({
                "status": "待命",
                "color": "green",
                "auth": False,
            })

            # ========== 标题栏 ==========
            with gr.Row():
                gr.Markdown("## 🧠 灵枢台 — 数字元神控制中心")
                with gr.Column(scale=0.3):
                    status_indicator = gr.Button(
                        "🟢 待命",
                        variant="secondary",
                        size="sm",
                    )
                    auth_btn = gr.Button(
                        "🛑 撤销授权",
                        variant="stop",
                        size="sm",
                        visible=False,  # 未授权时隐藏
                    )

            # ========== 授权弹窗（首次使用） ==========
            with gr.Group(visible=True) as auth_group:
                gr.Markdown("### 📋 首次使用授权")
                gr.Markdown("""
                灵枢需要以下权限才能操控您的电脑：
                - 📺 屏幕读取（识别界面元素）
                - 🖱️ 键鼠模拟（执行操作）
                - 📁 文件访问（读取/保存数据）
                - 🎙️ 麦克风使用（语音指令）
                """)
                auth_agree = gr.Button("✅ 我已阅读并同意授权", variant="primary")
                auth_result = gr.Textbox(label="授权结果", visible=False)

            # ========== 主控制面板 ==========
            with gr.Row():
                # 左侧：语音与状态
                with gr.Column(scale=1):
                    gr.Markdown("### 🎙️ 语音交互")
                    mic_btn = gr.Button("🎤 按住说话（或语音唤醒）", variant="primary")
                    voice_wave = gr.LinePlot(
                        x="time",
                        y="amplitude",
                        title="实时语音波形",
                        height=150,
                    )

                    gr.Markdown("### 📊 系统资源")
                    cpu_bar = gr.Slider(0, 100, value=0, label="CPU", interactive=False)
                    mem_bar = gr.Slider(0, 100, value=0, label="内存", interactive=False)

                # 右侧：快捷指令与日志
                with gr.Column(scale=1):
                    gr.Markdown("### ⚡ 快捷指令")
                    with gr.Row():
                        btn_clean = gr.Button("🧹 整理桌面")
                        btn_ps = gr.Button("🎨 打开Photoshop")
                        btn_ppt = gr.Button("📊 打开PPT")
                    with gr.Row():
                        btn_ss = gr.Button("📸 截图")
                        btn_browser = gr.Button("🌐 打开浏览器")
                        btn_explorer = gr.Button("📁 打开文件管理器")

                    gr.Markdown("### 📝 实时日志")
                    log_box = gr.Textbox(
                        label="",
                        lines=15,
                        max_lines=30,
                        interactive=False,
                        autoscroll=True,
                    )

            # ========== 底部交互区 ==========
            with gr.Row():
                cmd_input = gr.Textbox(
                    label="💬 输入指令",
                    placeholder="说出您的需求，或在此输入...",
                    scale=4,
                )
                send_btn = gr.Button("📤 发送", variant="primary", scale=1)

            response_box = gr.Textbox(
                label="🤖 灵枢回应",
                interactive=False,
            )

            # ========== 事件绑定 ==========

            # 授权按钮
            auth_agree.click(
                self._handle_auth_grant,
                outputs=[auth_result, auth_group, status_indicator, auth_btn],
            )

            # 撤销授权
            auth_btn.click(
                self._handle_auth_revoke,
                outputs=[status_indicator, auth_btn, auth_group],
            )

            # 快捷指令
            buttons = {
                btn_clean: "整理桌面文件",
                btn_ps: "打开Photoshop",
                btn_ppt: "打开PowerPoint",
                btn_ss: "截取屏幕",
                btn_browser: "打开Chrome浏览器",
                btn_explorer: "打开文件管理器",
            }
            for btn, cmd in buttons.items():
                btn.click(
                    self._handle_command,
                    inputs=[gr.State(cmd)],
                    outputs=[response_box, log_box],
                )

            # 文本输入
            send_btn.click(
                self._handle_command,
                inputs=[cmd_input],
                outputs=[response_box, log_box],
            )
            cmd_input.submit(
                self._handle_command,
                inputs=[cmd_input],
                outputs=[response_box, log_box],
            )

            # 麦克风按钮（占位，实际语音由后台模块处理）
            mic_btn.click(
                self._handle_voice_button,
                outputs=[response_box, log_box],
            )

            # 定时刷新状态
            demo.load(
                self._get_status_update,
                outputs=[status_indicator, cpu_bar, mem_bar, log_box],
                every=self.refresh_interval,
            )

        return demo

    # ============================================================
    # 事件处理器
    # ============================================================

    def _handle_auth_grant(self):
        """处理授权同意"""
        if self._on_auth_grant:
            success = self._on_auth_grant()
            if success:
                return (
                    "✅ 授权成功！灵枢已获电脑控制权",
                    self._gr.update(visible=False),  # 隐藏授权组
                    "🟢 已授权",  # 状态按钮
                    self._gr.update(visible=True),  # 显示撤销按钮
                )
        return (
            "❌ 授权失败",
            self._gr.update(visible=True),
            "🔴 未授权",
            self._gr.update(visible=False),
        )

    def _handle_auth_revoke(self):
        """处理撤销授权"""
        if self._on_auth_revoke:
            self._on_auth_revoke()
        return (
            "🔴 未授权",  # 状态按钮
            self._gr.update(visible=False),  # 隐藏撤销按钮
            self._gr.update(visible=True),  # 显示授权组
        )

    def _handle_command(self, command: str) -> Tuple[str, str]:
        """处理文本/快捷指令"""
        if not command or not command.strip():
            return "请输入指令", self._get_logs_text()

        self.add_log(f"[指令] {command}")

        if self._on_command:
            try:
                result = self._on_command(command)
                self.add_log(f"[结果] {result}")
                return result, self._get_logs_text()
            except Exception as e:
                self.add_log(f"[错误] {e}")
                return f"执行出错: {e}", self._get_logs_text()

        return f"收到指令: {command}", self._get_logs_text()

    def _handle_voice_button(self):
        """处理语音按钮点击"""
        self.add_log("[语音] 用户触发语音输入...")
        return "请直接说话（灵枢正在监听）", self._get_logs_text()

    def _get_status_update(self):
        """获取状态更新（定时调用）"""
        status_text = f"{'🟢' if self._status == '待命' else '🔴' if self._status == '需确认' else '🔵'} {self._status}"
        return status_text, self._cpu_percent, self._memory_percent, self._get_logs_text()

    # ============================================================
    # 公开API（供其他模块调用）
    # ============================================================

    def add_log(self, message: str):
        """添加日志条目"""
        timestamp = time.strftime("%H:%M:%S")
        self._logs.append(f"[{timestamp}] {message}")
        # 限制日志数量
        if len(self._logs) > 500:
            self._logs = self._logs[-400:]

    def update_status(self, status: str, color: str = "green"):
        """更新状态"""
        self._status = status
        self._status_color = color

    def update_system_stats(self, cpu: float, memory: float):
        """更新系统资源数据"""
        self._cpu_percent = cpu
        self._memory_percent = memory

    def update_voice_waveform(self, waveform: List[float]):
        """更新语音波形数据"""
        self._voice_waveform = waveform[-200:]  # 保留最近200个点

    def _get_logs_text(self) -> str:
        """获取日志文本"""
        return "\n".join(self._logs[-50:])  # 显示最近50条

    # ============================================================
    # 服务生命周期
    # ============================================================

    def start(self, blocking: bool = False):
        """启动GUI服务"""
        if not self._available:
            print("[GUI] Gradio 不可用，跳过启动灵枢台")
            return False

        if self._running:
            return True

        demo = self._build_ui()
        self._app = demo

        if blocking:
            # 阻塞模式（主线程）
            demo.launch(
                server_name=self.host,
                server_port=self.port,
                show_error=True,
                inbrowser=self.auto_launch,
            )
        else:
            # 后台线程模式
            self._server_thread = threading.Thread(
                target=self._run_server,
                daemon=True,
                name="LingShu-GUI",
            )
            self._server_thread.start()
            self._running = True
            print(f"[GUI] 🌐 灵枢台已启动: http://{self.host}:{self.port}")

        return True

    def _run_server(self):
        """后台运行服务器"""
        self._app.launch(
            server_name=self.host,
            server_port=self.port,
            show_error=True,
            inbrowser=False,  # 后台模式不自动打开浏览器
            quiet=True,
        )

    def stop(self):
        """停止GUI服务"""
        self._running = False
        if self._app:
            try:
                self._app.close()
            except Exception:
                pass
        print("[GUI] 灵枢台已关闭")
