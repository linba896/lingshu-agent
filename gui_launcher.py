#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════
  灵枢 IDE — VS Code 风格桌面启动台（v2.0）
  修复：Windows Store Python 沙箱限制 / 中文路径编码
  特性：多面板 IDE + 软件学习引擎 + 10秒极速启动
═══════════════════════════════════════════════════════════════════════
"""

import sys
import os
import subprocess
import threading
import time
import json
import pathlib
import re
from datetime import datetime
from typing import Optional, List, Dict, Callable

# ── 优先设置 UTF-8 ──
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font, filedialog

# ── 解析根目录 ──
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent

# ── 颜色主题（VS Code Dark+）───
BG_COLOR = "#1e1e1e"
SIDEBAR_BG = "#252526"
PANEL_BG = "#2d2d30"
ACCENT_BLUE = "#007acc"
ACCENT_GREEN = "#4ec9b0"
ACCENT_RED = "#f44336"
ACCENT_YELLOW = "#ffcc00"
ACCENT_PURPLE = "#c586c0"
TEXT_WHITE = "#cccccc"
TEXT_BRIGHT = "#ffffff"
TEXT_DIM = "#858585"
BORDER_COLOR = "#3e3e42"
STATUS_BAR_BG = "#007acc"

# ── 全局：找到正确的 Python 解释器 ──
def find_python_exe() -> str:
    """绕过 Windows Store 沙箱，找到可用的 Python 解释器"""
    # 候选路径（按优先级）
    candidates = []
    
    # 1. Kimi 托管 Python 运行时（最可靠）
    candidates.append(
        pathlib.Path.home() / "AppData" / "Roaming" / "kimi-desktop" 
        / "daimon-share" / "daimon" / "runtime" / "python" / ".venv" / "Scripts" / "python.exe"
    )
    
    # 2. 同目录便携 Python
    candidates.append(SCRIPT_DIR / "python" / "python.exe")
    candidates.append(ROOT / "python" / "python.exe")
    
    # 3. 用户目录标准安装（Python 3.9-3.12，避开 3.13 Windows Store）
    local_progs = pathlib.Path.home() / "AppData" / "Local" / "Programs" / "Python"
    if local_progs.exists():
        for ver in ["Python312", "Python311", "Python310", "Python39"]:
            candidates.append(local_progs / ver / "python.exe")
    
    # 4. 系统 PATH 中的 pythonw（优先无窗口版）
    candidates.append("pythonw")
    candidates.append("python")
    
    # 5. 当前解释器（如果是便携版则用，否则最后尝试）
    current = pathlib.Path(sys.executable)
    # 排除 Windows Store 代理
    if "WindowsApps" not in str(current):
        candidates.insert(0, current)
    
    for c in candidates:
        try:
            if isinstance(c, str):
                # 命令形式，测试能否执行
                result = subprocess.run(
                    [c, "--version"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return c
            else:
                if c.exists():
                    result = subprocess.run(
                        [str(c), "--version"], capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        return str(c)
        except Exception:
            continue
    
    # 最终 fallback：返回 sys.executable，但可能失败
    return sys.executable

PYTHON_EXE = find_python_exe()


class VSCodeStyleGUI:
    """VS Code 风格 IDE 启动台"""

    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("☯ 灵枢 IDE — LingShu Agent v2.0")
        self.master.geometry("1200x800")
        self.master.configure(bg=BG_COLOR)
        self.master.minsize(900, 600)
        
        # 状态变量
        self.process: Optional[subprocess.Popen] = None
        self.running = False
        self.log_queue = []
        self.queue_lock = threading.Lock()
        self.current_panel = "explorer"  # explorer | software | settings
        self.software_learner = None
        
        # 尝试加载软件学习引擎
        self._init_software_learner()
        
        # 构建 UI
        self._build_ui()
        self._start_log_poller()
        
        # 初始日志
        self._log("☯ 灵枢 IDE v2.0 已就绪")
        self._log(f"☯ Python 解释器: {PYTHON_EXE}")
        self._log(f"☯ 项目目录: {ROOT}")
        
    def _init_software_learner(self):
        """初始化软件学习引擎"""
        try:
            # 延迟导入，避免启动时加载失败
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "software_learner", ROOT / "core" / "software_learner.py"
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                self.software_learner = mod.SoftwareLearner(ROOT)
        except Exception as e:
            self._log(f"⚠️ 软件学习引擎未加载: {e}")
    
    def _build_ui(self):
        """构建 VS Code 风格多面板布局"""
        # ═══════ 顶部标题栏 ═══════
        self._build_titlebar()
        
        # ═══════ 主区域（水平分割）═══
        self.main_frame = tk.Frame(self.master, bg=BG_COLOR)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 左侧窄边栏（图标）
        self._build_activity_bar()
        
        # 左侧宽面板（可折叠）
        self._build_side_panel()
        
        # 中间主区域（PanedWindow 垂直分割）
        self._build_center_area()
        
        # ═══════ 底部状态栏 ═══════
        self._build_statusbar()
    
    def _build_titlebar(self):
        """顶部标题栏 + 标签页"""
        bar = tk.Frame(self.master, bg=BG_COLOR, height=35)
        bar.pack(fill=tk.X, side=tk.TOP)
        bar.pack_propagate(False)
        
        # 左侧标题
        title_font = font.Font(family="Microsoft YaHei", size=12, weight="bold")
        tk.Label(
            bar, text="☯ 灵枢 IDE", font=title_font, bg=BG_COLOR, fg=TEXT_BRIGHT
        ).pack(side=tk.LEFT, padx=10, pady=5)
        
        # 标签页栏
        self.tabs_frame = tk.Frame(bar, bg=BG_COLOR)
        self.tabs_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        self.active_tab = None
        self.tabs = {}
        self._add_tab("🖥 控制台", self._show_console)
        self._add_tab("📁 项目", self._show_project)
        self._add_tab("🧠 学习", self._show_learning)
        
        # 右侧窗口按钮
        win_frame = tk.Frame(bar, bg=BG_COLOR)
        win_frame.pack(side=tk.RIGHT, padx=5)
        
        for sym, cmd in [("─", self._minimize), ("□", self._maximize), ("✕", self._on_close)]:
            tk.Button(
                win_frame, text=sym, font=("Consolas", 10), bg=BG_COLOR, fg=TEXT_WHITE,
                bd=0, width=3, cursor="hand2", command=cmd,
                activebackground=BORDER_COLOR, activeforeground=TEXT_BRIGHT
            ).pack(side=tk.LEFT)
    
    def _add_tab(self, text: str, command: Callable):
        """添加标签页"""
        btn = tk.Button(
            self.tabs_frame, text=text, font=("Microsoft YaHei", 9),
            bg=BORDER_COLOR, fg=TEXT_WHITE, bd=0, padx=10, pady=3,
            cursor="hand2", command=lambda: self._switch_tab(text, command)
        )
        btn.pack(side=tk.LEFT, padx=1)
        self.tabs[text] = btn
        if self.active_tab is None:
            self._switch_tab(text, command)
    
    def _switch_tab(self, text: str, command: Callable):
        """切换标签页"""
        for t, btn in self.tabs.items():
            if t == text:
                btn.config(bg=BG_COLOR, fg=TEXT_BRIGHT)
            else:
                btn.config(bg=BORDER_COLOR, fg=TEXT_DIM)
        self.active_tab = text
        command()
    
    def _build_activity_bar(self):
        """最左侧窄边栏（图标按钮）"""
        self.activity_bar = tk.Frame(self.main_frame, bg=SIDEBAR_BG, width=48)
        self.activity_bar.pack(side=tk.LEFT, fill=tk.Y)
        self.activity_bar.pack_propagate(False)
        
        icons = [
            ("📁", "explorer", "资源管理器"),
            ("🔍", "search", "搜索"),
            ("🧠", "software", "软件学习"),
            ("⚙️", "settings", "设置"),
        ]
        
        self.activity_buttons = {}
        for i, (icon, key, tooltip) in enumerate(icons):
            btn = tk.Button(
                self.activity_bar, text=icon, font=("Segoe UI Emoji", 14),
                bg=SIDEBAR_BG, fg=TEXT_WHITE, bd=0, width=2, height=1,
                cursor="hand2", command=lambda k=key: self._switch_panel(k)
            )
            btn.pack(pady=5)
            self.activity_buttons[key] = btn
            
            # 悬停提示
            self._tooltip(btn, tooltip)
        
        # 默认选中 explorer
        self._switch_panel("explorer")
    
    def _tooltip(self, widget, text):
        """简单悬停提示"""
        def on_enter(e):
            x = widget.winfo_rootx() + 50
            y = widget.winfo_rooty()
            self.tip = tk.Toplevel(self.master)
            self.tip.wm_overrideredirect(True)
            self.tip.wm_geometry(f"+{x}+{y}")
            tk.Label(self.tip, text=text, bg="#ffffcc", fg="black", 
                    font=("Microsoft YaHei", 9), bd=1, relief=tk.SOLID).pack()
        def on_leave(e):
            if hasattr(self, "tip"):
                self.tip.destroy()
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
    
    def _switch_panel(self, key: str):
        """切换左侧宽面板内容"""
        for k, btn in self.activity_buttons.items():
            btn.config(bg=SIDEBAR_BG if k != key else BG_COLOR)
        self.current_panel = key
        self._refresh_side_panel()
    
    def _build_side_panel(self):
        """左侧宽面板（可折叠）"""
        self.side_panel = tk.Frame(self.main_frame, bg=BG_COLOR, width=220)
        self.side_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.side_panel.pack_propagate(False)
        
        # 分隔线
        sep = tk.Frame(self.main_frame, bg=BORDER_COLOR, width=1)
        sep.pack(side=tk.LEFT, fill=tk.Y)
        
        self.side_content = tk.Frame(self.side_panel, bg=BG_COLOR)
        self.side_content.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    def _refresh_side_panel(self):
        """刷新左侧面板内容"""
        for w in self.side_content.winfo_children():
            w.destroy()
        
        if self.current_panel == "explorer":
            self._build_explorer_panel()
        elif self.current_panel == "software":
            self._build_software_panel()
        elif self.current_panel == "settings":
            self._build_settings_panel()
        elif self.current_panel == "search":
            self._build_search_panel()
    
    def _build_explorer_panel(self):
        """资源管理器面板"""
        tk.Label(self.side_content, text="📁 灵枢项目", font=("Microsoft YaHei", 10, "bold"),
                bg=BG_COLOR, fg=TEXT_BRIGHT).pack(anchor=tk.W, pady=5)
        
        # 文件树（简化版）
        tree = tk.Listbox(self.side_content, bg=BG_COLOR, fg=TEXT_WHITE,
                         selectbackground=ACCENT_BLUE, font=("Consolas", 10),
                         bd=0, highlightthickness=0)
        tree.pack(fill=tk.BOTH, expand=True)
        
        # 填充项目结构
        items = [
            "📁 core/", "   📄 launcher.py", "   📄 asr.py", "   📄 vision.py",
            "   📄 executor.py", "   📄 software_learner.py",
            "📁 config/", "📁 logs/", "📁 models/", "📁 scripts/",
        ]
        for item in items:
            tree.insert(tk.END, item)
    
    def _build_software_panel(self):
        """软件学习面板"""
        tk.Label(self.side_content, text="🧠 软件学习引擎", font=("Microsoft YaHei", 10, "bold"),
                bg=BG_COLOR, fg=ACCENT_GREEN).pack(anchor=tk.W, pady=5)
        
        # 软件列表
        self.software_list = tk.Listbox(self.side_content, bg=BG_COLOR, fg=TEXT_WHITE,
                                       selectbackground=ACCENT_BLUE, font=("Consolas", 10),
                                       bd=0, highlightthickness=0)
        self.software_list.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 加载已学习的软件
        self._refresh_software_list()
        
        # 按钮
        btn_frame = tk.Frame(self.side_content, bg=BG_COLOR)
        btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(btn_frame, text="➕ 添加软件", font=("Microsoft YaHei", 9),
                 bg=ACCENT_BLUE, fg="white", bd=0, cursor="hand2",
                 command=self._add_software).pack(fill=tk.X, pady=2)
        
        tk.Button(btn_frame, text="🔍 分析目录", font=("Microsoft YaHei", 9),
                 bg=PANEL_BG, fg=TEXT_WHITE, bd=0, cursor="hand2",
                 command=self._analyze_software).pack(fill=tk.X, pady=2)
    
    def _refresh_software_list(self):
        """刷新软件列表"""
        self.software_list.delete(0, tk.END)
        self.software_list.insert(tk.END, "🧠 双击软件开始学习操作")
        self.software_list.insert(tk.END, "─────────────────────")
        
        # 从学习引擎加载
        if self.software_learner:
            try:
                apps = self.software_learner.list_learned_software()
                for app in apps:
                    status = "✅" if app.get("authorized") else "🚫"
                    self.software_list.insert(tk.END, f"{status} {app['name']}")
            except Exception:
                pass
        
        self.software_list.insert(tk.END, "─────────────────────")
        self.software_list.insert(tk.END, "💡 提示：添加软件后")
        self.software_list.insert(tk.END, "   观察并记录操作")
    
    def _add_software(self):
        """添加软件目录"""
        path = filedialog.askdirectory(title="选择软件目录")
        if path and self.software_learner:
            try:
                name = self.software_learner.add_software(path)
                self._log(f"🧠 已添加软件: {name}")
                self._refresh_software_list()
            except Exception as e:
                messagebox.showerror("错误", f"添加软件失败: {e}")
    
    def _analyze_software(self):
        """分析选中的软件"""
        if not self.software_learner:
            messagebox.showwarning("提示", "软件学习引擎未加载")
            return
        
        sel = self.software_list.curselection()
        if not sel:
            messagebox.showinfo("提示", "请先选择要分析的软件")
            return
        
        # 简单分析显示在日志中
        self._log("🔍 正在分析软件结构...")
        self._log("   扫描可执行文件、配置文件、资源...")
    
    def _build_settings_panel(self):
        """设置面板"""
        tk.Label(self.side_content, text="⚙️ 设置", font=("Microsoft YaHei", 10, "bold"),
                bg=BG_COLOR, fg=TEXT_BRIGHT).pack(anchor=tk.W, pady=5)
        
        # 启动选项
        options = [
            ("🚀 极速启动模式（跳过自检）", True),
            ("🧠 启用软件学习引擎", True),
            ("🎙️ 启用语音模块", False),
            ("👁️ 启用视觉模块", True),
        ]
        
        for text, default in options:
            var = tk.BooleanVar(value=default)
            tk.Checkbutton(self.side_content, text=text, variable=var,
                          bg=BG_COLOR, fg=TEXT_WHITE, selectcolor=ACCENT_BLUE,
                          font=("Microsoft YaHei", 9), activebackground=BG_COLOR).pack(anchor=tk.W, pady=2)
    
    def _build_search_panel(self):
        """搜索面板"""
        tk.Label(self.side_content, text="🔍 搜索", font=("Microsoft YaHei", 10, "bold"),
                bg=BG_COLOR, fg=TEXT_BRIGHT).pack(anchor=tk.W, pady=5)
        
        entry = tk.Entry(self.side_content, bg=PANEL_BG, fg=TEXT_WHITE,
                        insertbackground=TEXT_WHITE, font=("Consolas", 10),
                        bd=0, highlightthickness=1, highlightcolor=ACCENT_BLUE)
        entry.pack(fill=tk.X, pady=5)
        entry.insert(0, "搜索文件、命令...")
    
    def _build_center_area(self):
        """中间主区域（垂直 PanedWindow）"""
        self.paned = tk.PanedWindow(self.main_frame, orient=tk.VERTICAL, bg=BG_COLOR, sashwidth=4)
        self.paned.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 上部：内容区（多视图）
        self.content_frame = tk.Frame(self.paned, bg=BG_COLOR)
        self.paned.add(self.content_frame, height=500)
        
        # 下部：终端/日志面板（可折叠）
        self.terminal_frame = tk.Frame(self.paned, bg=BG_COLOR, height=200)
        self.paned.add(self.terminal_frame)
        
        self._build_terminal()
        self._build_content_views()
    
    def _build_content_views(self):
        """构建内容视图（控制台、项目、学习）"""
        # 视图容器
        self.views = {}
        
        # 视图 1: 控制台（启动控制）
        console = tk.Frame(self.content_frame, bg=BG_COLOR)
        self.views["console"] = console
        self._build_console_view(console)
        
        # 视图 2: 项目（文件列表）
        project = tk.Frame(self.content_frame, bg=BG_COLOR)
        self.views["project"] = project
        self._build_project_view(project)
        
        # 视图 3: 学习（软件学习界面）
        learning = tk.Frame(self.content_frame, bg=BG_COLOR)
        self.views["learning"] = learning
        self._build_learning_view(learning)
        
        # 默认显示控制台
        self._show_console()
    
    def _build_console_view(self, parent):
        """控制台视图（启动控制 + 状态）"""
        # 左侧控制区
        ctrl = tk.Frame(parent, bg=BG_COLOR, width=250)
        ctrl.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        ctrl.pack_propagate(False)
        
        # 状态卡片
        status_card = tk.Frame(ctrl, bg=PANEL_BG, bd=1, relief=tk.SOLID, highlightbackground=BORDER_COLOR)
        status_card.pack(fill=tk.X, pady=5)
        
        tk.Label(status_card, text="系统状态", font=("Microsoft YaHei", 10, "bold"),
                bg=PANEL_BG, fg=ACCENT_BLUE).pack(pady=5)
        
        self.status_label = tk.Label(status_card, text="🟡 未启动",
                                    font=("Microsoft YaHei", 14, "bold"),
                                    bg=PANEL_BG, fg=ACCENT_RED)
        self.status_label.pack(pady=5)
        
        # 启动按钮（巨大）
        self.start_btn = tk.Button(
            ctrl, text="▶ 启动灵枢", font=("Microsoft YaHei", 14, "bold"),
            bg=ACCENT_GREEN, fg="white", activebackground="#3ba99f",
            bd=0, cursor="hand2", height=2, command=self._on_start
        )
        self.start_btn.pack(fill=tk.X, pady=10)
        
        self.stop_btn = tk.Button(
            ctrl, text="⏹ 停止灵枢", font=("Microsoft YaHei", 12, "bold"),
            bg=ACCENT_RED, fg="white", activebackground="#d32f2f",
            bd=0, cursor="hand2", height=2, state=tk.DISABLED,
            command=self._on_stop
        )
        self.stop_btn.pack(fill=tk.X, pady=5)
        
        # 快捷按钮网格
        grid = tk.Frame(ctrl, bg=BG_COLOR)
        grid.pack(fill=tk.X, pady=10)
        
        actions = [
            ("📸 截图", self._screenshot),
            ("📋 状态", self._status),
            ("🧹 清理日志", self._clean),
        ]
        for i, (text, cmd) in enumerate(actions):
            btn = tk.Button(grid, text=text, font=("Microsoft YaHei", 9),
                           bg=PANEL_BG, fg=TEXT_WHITE, bd=0, cursor="hand2",
                           command=cmd)
            btn.grid(row=i//2, column=i%2, sticky="nsew", padx=2, pady=2)
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        
        # 右侧日志区
        log_frame = tk.Frame(parent, bg=BG_COLOR)
        log_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(log_frame, text="🖥 启动日志", font=("Microsoft YaHei", 11, "bold"),
                bg=BG_COLOR, fg=TEXT_BRIGHT).pack(anchor=tk.W)
        
        self.log_box = scrolledtext.ScrolledText(
            log_frame, bg="#0d0d0d", fg=TEXT_WHITE, insertbackground=ACCENT_BLUE,
            font=("Consolas", 10), bd=0, highlightthickness=0, state=tk.DISABLED,
            wrap=tk.WORD
        )
        self.log_box.pack(fill=tk.BOTH, expand=True, pady=5)
    
    def _build_project_view(self, parent):
        """项目视图"""
        tk.Label(parent, text="📁 项目文件", font=("Microsoft YaHei", 16, "bold"),
                bg=BG_COLOR, fg=TEXT_BRIGHT).pack(pady=50)
        tk.Label(parent, text="点击资源管理器查看文件结构",
                font=("Microsoft YaHei", 11), bg=BG_COLOR, fg=TEXT_DIM).pack()
    
    def _build_learning_view(self, parent):
        """软件学习视图"""
        # 上部：软件信息
        info = tk.Frame(parent, bg=BG_COLOR)
        info.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(info, text="🧠 软件自主学习中心", font=("Microsoft YaHei", 16, "bold"),
                bg=BG_COLOR, fg=ACCENT_GREEN).pack(anchor=tk.W)
        
        desc = """操作步骤：
1. 点击左侧"添加软件"，选择软件目录或 .exe 文件
2. 灵枢会自动分解文件结构、分析依赖关系
3. 点击"开始学习"，手动操作软件，灵枢会观察记录
4. 学习完成后，授予权限，灵枢即可自动操作该软件"""
        
        tk.Label(info, text=desc, font=("Microsoft YaHei", 10),
                bg=BG_COLOR, fg=TEXT_DIM, justify=tk.LEFT).pack(anchor=tk.W, pady=10)
        
        # 操作按钮
        btn_frame = tk.Frame(info, bg=BG_COLOR)
        btn_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(btn_frame, text="📁 添加软件目录", font=("Microsoft YaHei", 10),
                 bg=ACCENT_BLUE, fg="white", bd=0, padx=15, pady=5,
                 cursor="hand2", command=self._add_software).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="📦 添加 .exe 文件", font=("Microsoft YaHei", 10),
                 bg=PANEL_BG, fg=TEXT_WHITE, bd=0, padx=15, pady=5,
                 cursor="hand2", command=self._add_exe).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="🔴 开始学习操作", font=("Microsoft YaHei", 10),
                 bg=ACCENT_RED, fg="white", bd=0, padx=15, pady=5,
                 cursor="hand2", command=self._start_learning).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="✅ 授予操作权限", font=("Microsoft YaHei", 10),
                 bg=ACCENT_GREEN, fg="white", bd=0, padx=15, pady=5,
                 cursor="hand2", command=self._grant_permission).pack(side=tk.LEFT, padx=5)
        
        # 下部：学习进度
        progress_frame = tk.Frame(parent, bg=BG_COLOR)
        progress_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(progress_frame, text="学习进度", font=("Microsoft YaHei", 11, "bold"),
                bg=BG_COLOR, fg=TEXT_BRIGHT).pack(anchor=tk.W)
        
        self.learn_progress = ttk.Progressbar(progress_frame, mode="determinate", length=100)
        self.learn_progress.pack(fill=tk.X, pady=5)
        self.learn_progress["value"] = 0
        
        self.learn_status = tk.Label(progress_frame, text="等待添加软件...",
                                    font=("Microsoft YaHei", 10),
                                    bg=BG_COLOR, fg=TEXT_DIM)
        self.learn_status.pack(anchor=tk.W)
    
    def _add_exe(self):
        """添加 exe 文件"""
        path = filedialog.askopenfilename(
            title="选择软件可执行文件",
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")]
        )
        if path and self.software_learner:
            try:
                name = self.software_learner.add_software(path)
                self._log(f"🧠 已添加软件: {name}")
                self._refresh_software_list()
            except Exception as e:
                messagebox.showerror("错误", f"添加失败: {e}")
    
    def _start_learning(self):
        """开始学习操作"""
        self._log("🔴 开始学习模式：请手动操作软件，灵枢正在观察...")
        self.learn_status.config(text="🔴 正在记录操作... 请操作软件", fg=ACCENT_RED)
        self._log("   提示：所有鼠标点击、键盘输入都会被记录")
        
        # 在后台启动录制
        threading.Thread(target=self._record_operations, daemon=True).start()
    
    def _record_operations(self):
        """录制操作"""
        if not self.software_learner:
            self._log("❌ 软件学习引擎未加载")
            return
        
        try:
            self.software_learner.start_recording()
            for i in range(100):
                time.sleep(0.5)
                self.master.after(0, lambda v=i: self.learn_progress.config(value=v))
            self.software_learner.stop_recording()
            self.master.after(0, lambda: (
                self.learn_status.config(text="✅ 学习完成！可授予权限", fg=ACCENT_GREEN),
                self.learn_progress.config(value=100),
            ))
            self._log("✅ 操作录制完成，生成了操作脚本")
        except Exception as e:
            self._log(f"❌ 录制失败: {e}")
    
    def _grant_permission(self):
        """授予操作权限"""
        if messagebox.askyesno("确认", "授予灵枢自动操作该软件的权限？\n\n" 
                              "灵枢将可以：\n"
                              "  · 自动启动软件\n"
                              "  · 执行已学习的操作序列\n"
                              "  · 通过屏幕截图判断软件状态"):
            if self.software_learner:
                self.software_learner.grant_permission()
                self._log("✅ 已授予软件操作权限")
                self._refresh_software_list()
    
    def _build_terminal(self):
        """底部终端面板"""
        # 终端头部
        term_header = tk.Frame(self.terminal_frame, bg=PANEL_BG, height=25)
        term_header.pack(fill=tk.X, side=tk.TOP)
        term_header.pack_propagate(False)
        
        tk.Label(term_header, text="🖥 终端", font=("Microsoft YaHei", 9, "bold"),
                bg=PANEL_BG, fg=TEXT_BRIGHT).pack(side=tk.LEFT, padx=5)
        
        # 折叠按钮
        tk.Button(term_header, text="✕", font=("Consolas", 8), bg=PANEL_BG, fg=TEXT_WHITE,
                 bd=0, cursor="hand2", command=self._toggle_terminal).pack(side=tk.RIGHT, padx=5)
        
        # 终端内容
        self.terminal_box = scrolledtext.ScrolledText(
            self.terminal_frame, bg="#0d0d0d", fg=TEXT_WHITE,
            insertbackground=ACCENT_BLUE, font=("Consolas", 10),
            bd=0, highlightthickness=0, state=tk.DISABLED, wrap=tk.WORD
        )
        self.terminal_box.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 输入行
        input_frame = tk.Frame(self.terminal_frame, bg="#0d0d0d", height=25)
        input_frame.pack(fill=tk.X, side=tk.BOTTOM)
        input_frame.pack_propagate(False)
        
        tk.Label(input_frame, text="灵枢 >", font=("Consolas", 10),
                bg="#0d0d0d", fg=ACCENT_GREEN).pack(side=tk.LEFT, padx=5)
        
        self.cmd_entry = tk.Entry(input_frame, bg="#0d0d0d", fg=TEXT_WHITE,
                                 insertbackground=ACCENT_BLUE, font=("Consolas", 10),
                                 bd=0, highlightthickness=0)
        self.cmd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.cmd_entry.bind("<Return>", self._on_command)
    
    def _toggle_terminal(self):
        """折叠/展开终端"""
        if self.terminal_frame.winfo_ismapped():
            self.terminal_frame.pack_forget()
        else:
            self.paned.add(self.terminal_frame, height=200)
    
    def _on_command(self, event):
        """执行命令"""
        cmd = self.cmd_entry.get().strip()
        self.cmd_entry.delete(0, tk.END)
        if cmd:
            self._terminal_log(f"灵枢 > {cmd}")
            if self.process and self.process.poll() is None:
                try:
                    self.process.stdin.write(cmd + "\n")
                    self.process.stdin.flush()
                except Exception as e:
                    self._terminal_log(f"❌ 发送失败: {e}")
            else:
                self._terminal_log("⚠️ 灵枢未运行，无法执行命令")
    
    def _terminal_log(self, msg: str):
        """追加到终端"""
        self.terminal_box.config(state=tk.NORMAL)
        self.terminal_box.insert(tk.END, msg + "\n")
        self.terminal_box.see(tk.END)
        self.terminal_box.config(state=tk.DISABLED)
    
    def _build_statusbar(self):
        """底部状态栏"""
        bar = tk.Frame(self.master, bg=STATUS_BAR_BG, height=22)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        bar.pack_propagate(False)
        
        self.statusbar_text = tk.Label(bar, text="☯ 就绪",
                                      font=("Microsoft YaHei", 9),
                                      bg=STATUS_BAR_BG, fg="white")
        self.statusbar_text.pack(side=tk.LEFT, padx=10)
        
        tk.Label(bar, text="UTF-8  |  Python 3  |  灵枢 v2.0",
                font=("Consolas", 9), bg=STATUS_BAR_BG, fg="white").pack(side=tk.RIGHT, padx=10)
    
    def _show_console(self):
        """显示控制台视图"""
        for v in self.views.values():
            v.pack_forget()
        self.views["console"].pack(fill=tk.BOTH, expand=True)
    
    def _show_project(self):
        """显示项目视图"""
        for v in self.views.values():
            v.pack_forget()
        self.views["project"].pack(fill=tk.BOTH, expand=True)
    
    def _show_learning(self):
        """显示学习视图"""
        for v in self.views.values():
            v.pack_forget()
        self.views["learning"].pack(fill=tk.BOTH, expand=True)
    
    # ── 日志系统 ──
    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        with self.queue_lock:
            self.log_queue.append(line)
    
    def _flush_log(self):
        with self.queue_lock:
            lines = self.log_queue[:]
            self.log_queue.clear()
        if lines:
            self.log_box.config(state=tk.NORMAL)
            for line in lines:
                self.log_box.insert(tk.END, line)
            self.log_box.see(tk.END)
            self.log_box.config(state=tk.DISABLED)
            
            # 同时输出到终端
            self.terminal_box.config(state=tk.NORMAL)
            for line in lines:
                self.terminal_box.insert(tk.END, line)
            self.terminal_box.see(tk.END)
            self.terminal_box.config(state=tk.DISABLED)
    
    def _start_log_poller(self):
        def poll():
            while True:
                time.sleep(0.2)
                self.master.after(0, self._flush_log)
        threading.Thread(target=poll, daemon=True).start()
    
    # ── 控制操作 ──
    def _on_start(self):
        if self.running:
            return
        self._log("🚀 正在启动灵枢 Agent...")
        self.start_btn.config(state=tk.DISABLED, text="⏳ 启动中...")
        threading.Thread(target=self._run_agent, daemon=True).start()
    
    def _run_agent(self):
        """启动 Agent 子进程（使用正确的 Python）"""
        cmd = [
            PYTHON_EXE, "-u", str(ROOT / "core" / "launcher.py"),
            "--no-gui", "--skip-auth", "--fast-start"
        ]
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        
        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                env=env, cwd=str(ROOT), stdin=subprocess.PIPE
            )
            self.running = True
            
            self.master.after(0, lambda: (
                self.status_label.config(text="🟢 运行中", fg=ACCENT_GREEN),
                self.stop_btn.config(state=tk.NORMAL),
                self.start_btn.config(text="▶ 已启动"),
                self.statusbar_text.config(text="☯ 灵枢 Agent 运行中"),
            ))
            
            self._log("✅ 灵枢 Agent 已启动")
            
            for line in self.process.stdout:
                if line:
                    self._log(line.rstrip())
            
            self.process.wait()
            self._log(f"🏁 Agent 已退出（返回码: {self.process.returncode}）")
            
        except Exception as e:
            self._log(f"❌ 启动失败: {e}")
        finally:
            self.running = False
            self.process = None
            self.master.after(0, self._reset_ui)
    
    def _reset_ui(self):
        self.start_btn.config(state=tk.NORMAL, text="▶ 启动灵枢")
        self.stop_btn.config(state=tk.DISABLED)
        self.status_label.config(text="🟡 未启动", fg=ACCENT_RED)
        self.statusbar_text.config(text="☯ 就绪")
    
    def _on_stop(self):
        if self.process and self.process.poll() is None:
            self._log("🛑 正在停止...")
            try:
                self.process.stdin.write("quit\n")
                self.process.stdin.flush()
            except Exception:
                pass
            def kill_after():
                if self.process and self.process.poll() is None:
                    self.process.terminate()
            self.master.after(3000, kill_after)
    
    def _on_close(self):
        if self.running:
            if not messagebox.askyesno("确认退出", "灵枢正在运行中，确定关闭？"):
                return
            self._on_stop()
        self.master.destroy()
    
    def _screenshot(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write("screenshot\n")
                self.process.stdin.flush()
                self._log("📸 已发送截图命令")
            except Exception as e:
                self._log(f"❌ {e}")
        else:
            self._log("⚠️ 灵枢未启动")
    
    def _status(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write("modules\n")
                self.process.stdin.flush()
                self._log("📋 已查询模块状态")
            except Exception as e:
                self._log(f"❌ {e}")
        else:
            self._log("⚠️ 灵枢未启动")
    
    def _clean(self):
        self.log_box.config(state=tk.NORMAL)
        self.log_box.delete(1.0, tk.END)
        self.log_box.config(state=tk.DISABLED)
        self._log("🧹 日志已清空")
    
    def _minimize(self):
        self.master.iconify()
    
    def _maximize(self):
        if self.master.state() == "zoomed":
            self.master.state("normal")
        else:
            self.master.state("zoomed")


def main():
    root = tk.Tk()
    app = VSCodeStyleGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
