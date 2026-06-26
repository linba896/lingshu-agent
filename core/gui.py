#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — GUI 面板模块（增补卷核心）
功能：Gradio 可视化界面、状态指示、语音波形、快捷操作、实时日志、授权弹窗

界面布局：
  ┌─────────────────────────────────────────┐
  │  🟢 运行中  [授权] [撤销] [设置]        │
  │  ─────────────────────────────────────  │
  │  CPU: 45%  内存: 60%  磁盘: 30%        │
  │  ─────────────────────────────────────  │
  │  [截图] [PPT] [Excel] [浏览器] [文件]  │
  │  ─────────────────────────────────────  │
  │  🎙️ 语音波形显示区域                     │
  │  ─────────────────────────────────────  │
  │  [快捷操作] [场景切换] [紧急停止]       │
  │  ─────────────────────────────────────  │
  │  实时日志:                               │
  │  [15:32:01] 灵枢启动...                 │
  │  [15:32:05] 授权验证通过                │
  │  [15:32:10] 检测到语音指令...           │
  └─────────────────────────────────────────┘

"""

import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional


class LingShuGUI:
    """
    灵枢 GUI 面板
    
    基于 Gradio 构建的可视化控制面板：
    - 状态指示器（运行中/暂停/错误）
    - 系统资源监控（CPU/内存/磁盘）
    - 快捷操作按钮（截图、打开应用、场景切换）
    - 语音波形显示
    - 实时日志滚动
    - 授权弹窗
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

        # 状态变量
        self._status = "运行中"
        self._status_color = "green"
        self._logs: List[str] = []
        self._cpu_percent = 0.0
        self._memory_percent = 0.0
        self._voice_waveform: List[float] = []

        self._available = False
        self._init_gradio()

    def _init_gradio(self):
        """初始化 Gradio"""
        try:
            import gradio as gr
            self._gr = gr
            self._available = True
            print("[GUI] ✅ Gradio 已加载，GUI 面板可用")
        except ImportError:
            print("[GUI] ⚠️ Gradio 未安装，GUI 面板不可用。请运行: pip install gradio")
            self._available = False

    def is_available(self) -> bool:
        return self._available

    # ==================== 界面构建 ====================

    def _build_ui(self):
        """构建 Gradio 界面"""
        gr = self._gr

        with gr.Blocks(
            title="灵枢控制台 — 智能桌面助手",
            theme=gr.themes.Soft() if self.theme == "dark" else gr.themes.Default(),
        ) as demo:
            # 状态变量（用于跨回调共享）
            status_state = gr.State({
                "status": "运行中",
                "color": "green",
                "auth": False,
            })

            # ========== 标题栏 ==========
            with gr.Row():
                gr.Markdown("## 🧠 灵枢控制台 — 智能桌面助手")
                with gr.Column(scale=0.3):
                    status_indicator = gr.Button(
                        "🟢 运行中",
                        variant="secondary",
                        size="sm",
                    )
                    auth_btn = gr.Button(
                        "🚫 撤销授权",
                        variant="stop",
                        size="sm",
                        visible=False,  # 未授权时隐藏
                    )

            # ========== 授权弹窗（首次使用） ==========
            with gr.Group(visible=True) as auth_group:
                gr.Markdown("### 📋 首次使用授权协议")
                gr.Markdown("""
灵枢是一款智能桌面助手，为了保障您的系统安全，首次使用前需要您明确授权。

  - 🔒 基础权限：文件浏览、网页搜索、程序启动（安全级别：低）
  - ⚠️  中级权限：文件修改、系统设置、程序控制（需声纹验证）
  - 🛡️ 高级权限：格式化磁盘、支付操作、网络配置（需声纹+人脸）
                """)
                auth_agree = gr.Button("✅ 我同意并授权", variant="primary")
                auth_result = gr.Textbox(label="授权结果", visible=False)

            # ========== 系统监控 ==========
            with gr.Row():
                # 左侧：语音波形 + 系统资源
                with gr.Column(scale=1):
                    gr.Markdown("### 🎙️ 语音交互")
                    mic_btn = gr.Button("🎙️ 开始录音（3秒）", variant="primary")
                    voice_wave = gr.LinePlot(
                        x="time",
                        y="amplitude",
                        title="语音波形",
                        height=150,
                    )

                    gr.Markdown("### 📊 系统资源")
                    cpu_bar = gr.Slider(0, 100, value=0, label="CPU", interactive=False)
                    mem_bar = gr.Slider(0, 100, value=0, label="内存", interactive=False)

                # 右侧：快捷操作
                with gr.Column(scale=1):
                    gr.Markdown("### ⚡ 快捷操作")
                    with gr.Row():
                        btn_clean = gr.Button("🧹 清理桌面")
                        btn_ps = gr.Button("📸 截图")
                        btn_ppt = gr.Button("📊 PPT")
                    with gr.Row():
                        btn_ss = gr.Button("🖥️ 截图")
                        btn_browser = gr.Button("🌐 浏览器")
                        btn_explorer = gr.Button("📁 文件管理")

                    gr.Markdown("### 🚨 紧急操作")
                    log_box = gr.Textbox(
                        label="",
                        lines=15,
                        max_lines=30,
                        interactive=False,
                        autoscroll=True,
                    )

            # ========== 命令输入区 ==========
            with gr.Row():
                cmd_input = gr.Textbox(
                    label="💬 输入命令",
                    placeholder="请输入命令或语音指令...",
                    scale=4,
                )
                send_btn = gr.Button("📤 发送", variant="primary", scale=1)

            response_box = gr.Textbox(
                label="🤖 灵枢响应",
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

            # 快捷操作按钮
            buttons = {
                btn_clean: "清理桌面",
                btn_ps: "截图",
                btn_ppt: "截图",
                btn_ss: "截图",
                btn_browser: "浏览器",
                btn_explorer: "文件管理",
            }
            for btn, cmd in buttons.items():
                btn.click(
                    self._handle_command,
                    inputs=[gr.State(cmd)],
                    outputs=[response_box, log_box],
                )

            # 命令输入
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

            # 语音按钮（开发中）
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

    # ==================== 事件处理 ====================

    def _handle_auth_grant(self):
        """处理授权按钮点击"""
        if self._on_auth_grant:
            success = self._on_auth_grant()
            if success:
                return (
                    "✅ 授权成功，灵枢已获得操作权限",
                    self._gr.update(visible=False),  # 隐藏授权组
                    "🟢 已授权",  # 状态指示器
                    self._gr.update(visible=True),   # 显示撤销按钮
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
            "🔴 未授权",  # 状态指示器
            self._gr.update(visible=False),  # 隐藏撤销按钮
            self._gr.update(visible=True),   # 显示授权组
        )

    def _handle_command(self, command: str) -> Tuple[str, str]:
        """处理命令/快捷操作"""
        if not command or not command.strip():
            return "请输入命令", self._get_logs_text()

        self.add_log(f"[指令] {command}")

        if self._on_command:
            try:
                result = self._on_command(command)
                self.add_log(f"[结果] {result}")
                return result, self._get_logs_text()
            except Exception as e:
                self.add_log(f"[错误] {e}")
                return f"执行出错: {e}", self._get_logs_text()

        return f"执行: {command}", self._get_logs_text()

    def _handle_voice_button(self):
        """处理语音按钮点击"""
        self.add_log("[语音] 开始录音...")
        return "语音功能开发中，请使用文本输入", self._get_logs_text()

    def _get_status_update(self):
        """获取状态更新（定时回调）"""
        status_text = f"{'🟢' if self._status == '运行中' else '🔴' if self._status == '已停止' else '🟡'} {self._status}"
        return status_text, self._cpu_percent, self._memory_percent, self._get_logs_text()

    # ==================== 公共API ====================

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
        """更新系统资源统计"""
        self._cpu_percent = cpu
        self._memory_percent = memory

    def update_voice_waveform(self, waveform: List[float]):
        """更新语音波形数据"""
        self._voice_waveform = waveform[-200:]  # 保留最近200个采样点

    def _get_logs_text(self) -> str:
        """获取日志文本"""
        return "\n".join(self._logs[-50:])  # 显示最近50条

    # ==================== 启动/停止 ====================

    def start(self, blocking: bool = False):
        """启动 GUI 面板"""
        if not self._available:
            print("[GUI] Gradio 不可用，无法启动 GUI")
            return False

        if self._running:
            return True

        demo = self._build_ui()
        self._app = demo

        if blocking:
            # 阻塞模式（仅用于调试）
            demo.launch(
                server_name=self.host,
                server_port=self.port,
                show_error=True,
                inbrowser=self.auto_launch,
            )
        else:
            # 非阻塞模式
            self._server_thread = threading.Thread(
                target=self._run_server,
                daemon=True,
                name="LingShu-GUI",
            )
            self._server_thread.start()
            self._running = True
            print(f"[GUI] 🌐  GUI 面板已启动: http://{self.host}:{self.port}")

        return True

    def _run_server(self):
        """后台运行服务器"""
        self._app.launch(
            server_name=self.host,
            server_port=self.port,
            show_error=True,
            inbrowser=False,  # 非阻塞模式不自动打开浏览器
            quiet=True,
        )

    def stop(self):
        """停止 GUI 面板"""
        self._running = False
        if self._app:
            try:
                self._app.close()
            except Exception:
                pass
        print("[GUI] 灵枢 GUI 面板已关闭")

