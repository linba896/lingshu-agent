#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════
  灵枢启动台 — 桌面 GUI 启动器（双击即开，无需命令行）
  适合：幼儿园小朋友 / 非技术用户
═══════════════════════════════════════════════════════════════════════
"""

import sys
import os
import subprocess
import threading
import time
import pathlib
from datetime import datetime

# ── 优先设置 UTF-8 ──
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── tkinter 是 Python 内置，无需 pip 安装 ──
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font

# ── 解析根目录 ──
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

# ── 颜色主题（赛博朋克风格）───
BG_COLOR = "#0a0a12"
PANEL_COLOR = "#12121f"
ACCENT_CYAN = "#00f0ff"
ACCENT_BLUE = "#3b82f6"
ACCENT_PURPLE = "#a855f7"
ACCENT_GREEN = "#22c55e"
ACCENT_RED = "#ef4444"
TEXT_WHITE = "#f8fafc"
TEXT_DIM = "#94a3b8"


class LingshuLauncherGUI:
    """灵枢桌面启动器 GUI"""

    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("☯ 灵枢启动台 — LingShu Agent")
        self.master.geometry("800x600")
        self.master.configure(bg=BG_COLOR)
        self.master.minsize(700, 500)

        # 尝试设置窗口图标（Windows）
        try:
            self.master.iconbitmap(str(ROOT / "assets" / "icon.ico"))
        except Exception:
            pass

        self.process = None
        self.running = False
        self.log_queue = []
        self.queue_lock = threading.Lock()

        self._build_ui()
        self._start_log_poller()

    def _build_ui(self):
        """构建界面"""
        # 主容器
        main = tk.Frame(self.master, bg=BG_COLOR)
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # ═══════ 顶部标题栏 ═══════
        header = tk.Frame(main, bg=BG_COLOR)
        header.pack(fill=tk.X, pady=(0, 15))

        title_font = font.Font(family="Microsoft YaHei", size=24, weight="bold")
        subtitle_font = font.Font(family="Microsoft YaHei", size=11)

        tk.Label(
            header,
            text="☯  灵 枢 启 动 台",
            font=title_font,
            bg=BG_COLOR,
            fg=ACCENT_CYAN,
        ).pack(side=tk.LEFT)

        tk.Label(
            header,
            text="LingShu Agent v0.3.0  ·  Neural Consciousness",
            font=subtitle_font,
            bg=BG_COLOR,
            fg=TEXT_DIM,
        ).pack(side=tk.RIGHT, pady=10)

        # 分隔线
        sep = tk.Frame(main, height=2, bg=ACCENT_BLUE)
        sep.pack(fill=tk.X, pady=(0, 15))

        # ═══════ 左侧：大按钮区 ═══════
        left = tk.Frame(main, bg=BG_COLOR, width=220)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left.pack_propagate(False)

        # 状态面板
        status_panel = tk.Frame(left, bg=PANEL_COLOR, bd=1, relief=tk.RIDGE)
        status_panel.pack(fill=tk.X, pady=(0, 15))

        tk.Label(
            status_panel,
            text="系统状态",
            font=("Microsoft YaHei", 10, "bold"),
            bg=PANEL_COLOR,
            fg=ACCENT_BLUE,
        ).pack(pady=(8, 4))

        self.status_label = tk.Label(
            status_panel,
            text="🟡 未启动",
            font=("Microsoft YaHei", 12, "bold"),
            bg=PANEL_COLOR,
            fg=ACCENT_RED,
        )
        self.status_label.pack(pady=(0, 8))

        # 巨大的启动按钮
        self.start_btn = tk.Button(
            left,
            text="🚀 启 动 灵 枢",
            font=("Microsoft YaHei", 16, "bold"),
            bg=ACCENT_GREEN,
            fg="white",
            activebackground="#16a34a",
            activeforeground="white",
            cursor="hand2",
            bd=0,
            relief=tk.FLAT,
            height=2,
            command=self._on_start,
        )
        self.start_btn.pack(fill=tk.X, pady=(0, 10))
        self._hover_effect(self.start_btn, ACCENT_GREEN, "#16a34a")

        # 停止按钮
        self.stop_btn = tk.Button(
            left,
            text="🛑 停 止 灵 枢",
            font=("Microsoft YaHei", 14, "bold"),
            bg=ACCENT_RED,
            fg="white",
            activebackground="#dc2626",
            activeforeground="white",
            cursor="hand2",
            bd=0,
            relief=tk.FLAT,
            height=2,
            state=tk.DISABLED,
            command=self._on_stop,
        )
        self.stop_btn.pack(fill=tk.X, pady=(0, 10))
        self._hover_effect(self.stop_btn, ACCENT_RED, "#dc2626")

        # 快捷操作按钮（小按钮网格）
        actions = tk.Frame(left, bg=BG_COLOR)
        actions.pack(fill=tk.X, pady=(0, 10))

        small_btns = [
            ("📸 截图", self._screenshot),
            ("📋 状态", self._status),
            ("🧹 清理", self._clean),
            ("❓ 帮助", self._help),
        ]
        for i, (text, cmd) in enumerate(small_btns):
            btn = tk.Button(
                actions,
                text=text,
                font=("Microsoft YaHei", 10),
                bg=PANEL_COLOR,
                fg=TEXT_WHITE,
                activebackground=ACCENT_BLUE,
                activeforeground="white",
                cursor="hand2",
                bd=0,
                relief=tk.FLAT,
                command=cmd,
            )
            btn.grid(row=i // 2, column=i % 2, sticky="nsew", padx=3, pady=3)
            self._hover_effect(btn, PANEL_COLOR, ACCENT_BLUE)

        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        # 退出按钮
        quit_btn = tk.Button(
            left,
            text="❌ 关 闭 窗 口",
            font=("Microsoft YaHei", 12),
            bg="#374151",
            fg=TEXT_WHITE,
            activebackground="#4b5563",
            cursor="hand2",
            bd=0,
            relief=tk.FLAT,
            height=1,
            command=self._on_quit,
        )
        quit_btn.pack(fill=tk.X, side=tk.BOTTOM)
        self._hover_effect(quit_btn, "#374151", "#4b5563")

        # ═══════ 右侧：日志输出区 ═══════
        right = tk.Frame(main, bg=PANEL_COLOR, bd=1, relief=tk.RIDGE)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        tk.Label(
            right,
            text="🖥  运 行 日 志",
            font=("Microsoft YaHei", 11, "bold"),
            bg=PANEL_COLOR,
            fg=ACCENT_BLUE,
        ).pack(pady=(8, 4), padx=10, anchor=tk.W)

        # 日志文本框
        self.log_box = scrolledtext.ScrolledText(
            right,
            bg="#0f172a",
            fg=TEXT_WHITE,
            insertbackground=ACCENT_CYAN,
            font=("Consolas", 10),
            bd=0,
            relief=tk.FLAT,
            state=tk.DISABLED,
            wrap=tk.WORD,
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 底部进度条
        self.progress = ttk.Progressbar(
            right, mode="indeterminate", length=100
        )
        self.progress.pack(fill=tk.X, padx=8, pady=(0, 8))
        # ttk 样式调整（Windows 下效果有限）
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Horizontal.TProgressbar", background=ACCENT_CYAN, troughcolor=BG_COLOR)

        # 初始日志
        self._log("☯ 灵枢启动台已就绪")
        self._log("☯ 点击左侧【🚀 启动灵枢】按钮开始运行")
        self._log(f"☯ 项目目录: {ROOT}")

    def _hover_effect(self, widget, normal_bg, hover_bg):
        """鼠标悬停变色效果"""
        widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
        widget.bind("<Leave>", lambda e: widget.config(bg=normal_bg))

    def _log(self, msg: str):
        """追加日志到文本框"""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        with self.queue_lock:
            self.log_queue.append(line)

    def _flush_log(self):
        """将队列日志写入文本框（必须在主线程）"""
        with self.queue_lock:
            lines = self.log_queue[:]
            self.log_queue.clear()
        if lines:
            self.log_box.config(state=tk.NORMAL)
            for line in lines:
                self.log_box.insert(tk.END, line)
            self.log_box.see(tk.END)
            self.log_box.config(state=tk.DISABLED)

    def _start_log_poller(self):
        """启动日志轮询"""
        def poll():
            while True:
                time.sleep(0.2)
                self.master.after(0, self._flush_log)
        threading.Thread(target=poll, daemon=True).start()

    def _on_start(self):
        """启动灵枢 Agent"""
        if self.running:
            return

        self._log("🚀 正在启动灵枢 Agent...")
        self.start_btn.config(state=tk.DISABLED, text="⏳ 启动中...")
        self.progress.start(10)

        # 在后台线程启动子进程
        threading.Thread(target=self._run_agent, daemon=True).start()

    def _run_agent(self):
        """后台运行 Agent 进程"""
        cmd = [
            sys.executable,
            "-u",
            str(ROOT / "core" / "launcher.py"),
            "--no-gui",
            "--skip-auth",
            "--dry-run",
        ]
        env = {**os.environ, "PYTHONPATH": str(ROOT) + os.pathsep + os.environ.get("PYTHONPATH", "")}

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                cwd=str(ROOT),
            )
            self.running = True

            # 更新 UI
            self.master.after(0, lambda: (
                self.status_label.config(text="🟢 运行中", fg=ACCENT_GREEN),
                self.stop_btn.config(state=tk.NORMAL),
                self.start_btn.config(text="🚀 已启动"),
            ))

            self._log("✅ 灵枢 Agent 已启动")
            self._log("☯ 提示：当前为文本模式，可输入 help 查看命令")

            # 读取输出
            for line in self.process.stdout:
                if line:
                    self._log(line.rstrip())

            self.process.wait()
            self._log(f"🏁 灵枢 Agent 已退出（返回码: {self.process.returncode}）")

        except Exception as e:
            self._log(f"❌ 启动失败: {e}")

        finally:
            self.running = False
            self.process = None
            self.master.after(0, self._reset_ui)

    def _reset_ui(self):
        """重置 UI 状态"""
        self.progress.stop()
        self.start_btn.config(state=tk.NORMAL, text="🚀 启 动 灵 枢")
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="🟡 未启动", fg=ACCENT_RED)

    def _on_stop(self):
        """停止灵枢 Agent"""
        if self.process and self.process.poll() is None:
            self._log("🛑 正在停止灵枢 Agent...")
            try:
                self.process.stdin.write("quit\n")
                self.process.stdin.flush()
            except Exception:
                pass
            # 给 3 秒优雅退出
            def kill_after():
                if self.process and self.process.poll() is None:
                    self._log("⚠️ 强制终止进程")
                    self.process.terminate()
            self.master.after(3000, kill_after)

    def _on_quit(self):
        """关闭窗口"""
        if self.running:
            if not messagebox.askyesno(
                "确认退出", "灵枢正在运行中，确定要关闭吗？", icon="warning"
            ):
                return
            self._on_stop()
        self._log("👋 再见！灵枢启动台已关闭")
        self.master.after(500, self.master.destroy)

    def _screenshot(self):
        """发送截图命令"""
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write("screenshot\n")
                self.process.stdin.flush()
                self._log("📸 已发送截图命令")
            except Exception as e:
                self._log(f"❌ 发送命令失败: {e}")
        else:
            self._log("⚠️ 灵枢未启动，无法截图")

    def _status(self):
        """发送状态命令"""
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write("modules\n")
                self.process.stdin.flush()
                self._log("📋 已发送模块状态查询")
            except Exception as e:
                self._log(f"❌ 发送命令失败: {e}")
        else:
            self._log("⚠️ 灵枢未启动")

    def _clean(self):
        """清理日志"""
        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete(1.0, tk.END)
        self.log_box.config(state=tk.DISABLED)
        self._log("🧹 日志已清空")

    def _help(self):
        """显示帮助"""
        help_text = (
            "☯ 灵枢启动台 使用帮助\n\n"
            "【🚀 启动灵枢】 开始运行灵枢 Agent\n"
            "【🛑 停止灵枢】 停止正在运行的 Agent\n"
            "【📸 截图】 截取当前屏幕保存到 logs/\n"
            "【📋 状态】 查看各模块加载状态\n"
            "【🧹 清理】 清空日志窗口\n"
            "【❌ 关闭窗口】 退出启动台\n\n"
            "提示：灵枢启动后，可以在日志中输入命令\n"
            "（当前版本为只读展示，命令输入需通过其他方式）"
        )
        messagebox.showinfo("使用帮助", help_text)


def main():
    root = tk.Tk()
    app = LingshuLauncherGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
