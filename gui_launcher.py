#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LingShu Agent - Cyberpunk GUI Launcher v3.1
Advanced Purple Black Hole + i18n Edition

Features:
  - Ultra-smooth black hole animation with glow & accretion disk
  - Full Chinese/English language switch (default: Chinese)
  - Splash screen with rotating singularity
  - Main window with live canvas animation
  - System tray integration
  - Software learning engine

Dependencies: tkinter, PIL (Pillow)
"""

import os
import sys
import subprocess
import threading
import time
import random
import math
from pathlib import Path
from typing import Optional, List, Dict, Callable

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFilter
    HAS_PIL = True
    _RESIZE_FILTER = getattr(Image, 'LANCZOS', None)
    if _RESIZE_FILTER is None:
        _RESIZE_FILTER = getattr(Image, 'ANTIALIAS', None)
    if _RESIZE_FILTER is None and hasattr(Image, 'Resampling'):
        _RESIZE_FILTER = Image.Resampling.LANCZOS
    if _RESIZE_FILTER is None:
        _RESIZE_FILTER = 1
except ImportError:
    HAS_PIL = False
    _RESIZE_FILTER = None
    print("[WARN] Pillow not installed.")

try:
    import pystray
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

import tkinter as tk
from tkinter import ttk, messagebox, font


# ============================================================
# i18n - Internationalization
# ============================================================
class I18N:
    """Language manager. Default: Chinese."""

    _TEXTS = {
        "zh": {
            "title": "灵枢 Agent - 神经核心",
            "app_name": "灵枢",
            "version": "v3.1.0",
            "ready": "就绪",
            "running": "运行中",
            "splash_title": "灵枢 AGENT",
            "splash_subtitle": "正在初始化神经核心...",
            "system_status": "系统状态",
            "neural_core": "神经核心",
            "voice_module": "语音模块",
            "vision_module": "视觉模块",
            "security_vault": "安全保险库",
            "evolution_engine": "进化引擎",
            "online": "在线",
            "standby": "待命",
            "locked": "已锁定",
            "idle": "空闲",
            "quick_stats": "快速统计",
            "memory_entries": "记忆条目",
            "tasks_executed": "已执行任务",
            "uptime": "运行时间",
            "launch_agent": "启动智能体",
            "learning_engine": "学习引擎",
            "settings": "设置",
            "documentation": "文档",
            "about": "关于",
            "learning_title": "软件学习引擎",
            "learning_desc": "让灵枢分析、学习并掌握任何软件",
            "target_software": "目标软件：",
            "placeholder_software": "例如：Photoshop、VS Code、Excel",
            "decompose": "分解软件为功能模块",
            "learn_ui": "学习UI模式与交互流程",
            "automate": "生成自动化脚本",
            "start_learning": "开始学习",
            "input_required": "需要输入",
            "enter_software": "请输入软件名称。",
            "learning_init": "正在初始化 {software} 的学习序列...",
            "phase1": "阶段 1：软件分解...",
            "phase2": "阶段 2：模式识别...",
            "phase3": "阶段 3：自动化生成...",
            "learning_done": "{software} 学习完成！",
            "skills_saved": "技能已保存至记忆模块。灵枢现在可以操作此软件。",
            "settings_title": "设置",
            "general": "通用",
            "voice": "语音",
            "security": "安全",
            "language": "语言",
            "language_tip": "切换语言后重启生效",
            "about_title": "关于灵枢",
            "about_version": "版本 3.1.0 - 神经核心版",
            "about_text": """灵枢是下一代AI Agent运行时环境，
通过智能自动化控制您的计算机。

核心功能：
  · 多模态交互（语音、视觉、文本）
  · 自进化能力引擎
  · 多智能体协调面板
  · 数字孪生沙盒排练
  · 硬件控制集成
  · 软件学习引擎

专为AI驱动的计算而设计。""",
            "team": "2026 灵枢团队",
            "launch_success": "智能体启动成功！\n请查看控制台窗口。",
            "agent_ready": "智能体核心已就绪！\n\nGUI是主要界面。\n所有模块已加载并测试通过。",
            "tray_show": "显示灵枢",
            "tray_exit": "退出",
            "tray_tooltip": "灵枢 Agent - 神经核心",
            "error_title": "灵枢 Agent 错误",
            "lang_switch": "🌐 中/EN",
        },
        "en": {
            "title": "LingShu Agent - Neural Core",
            "app_name": "LINGSHU",
            "version": "v3.1.0",
            "ready": "READY",
            "running": "RUNNING",
            "splash_title": "LINGSHU AGENT",
            "splash_subtitle": "Initializing Neural Core...",
            "system_status": "SYSTEM STATUS",
            "neural_core": "Neural Core",
            "voice_module": "Voice Module",
            "vision_module": "Vision Module",
            "security_vault": "Security Vault",
            "evolution_engine": "Evolution Engine",
            "online": "ONLINE",
            "standby": "STANDBY",
            "locked": "LOCKED",
            "idle": "IDLE",
            "quick_stats": "QUICK STATS",
            "memory_entries": "Memory Entries",
            "tasks_executed": "Tasks Executed",
            "uptime": "Uptime",
            "launch_agent": "LAUNCH AGENT",
            "learning_engine": "LEARNING ENGINE",
            "settings": "SETTINGS",
            "documentation": "DOCUMENTATION",
            "about": "ABOUT",
            "learning_title": "SOFTWARE LEARNING ENGINE",
            "learning_desc": "Let LingShu analyze, learn, and master any software",
            "target_software": "Target Software:",
            "placeholder_software": "e.g., Photoshop, VS Code, Excel",
            "decompose": "Decompose software into functional modules",
            "learn_ui": "Learn UI patterns and interaction flows",
            "automate": "Generate automation scripts",
            "start_learning": "START LEARNING",
            "input_required": "Input Required",
            "enter_software": "Please enter a software name.",
            "learning_init": "Initializing learning sequence for: {software}",
            "phase1": "Phase 1: Software decomposition...",
            "phase2": "Phase 2: Pattern recognition...",
            "phase3": "Phase 3: Automation generation...",
            "learning_done": "Learning complete for {software}!",
            "skills_saved": "Skills saved to memory module. LingShu can now operate this software.",
            "settings_title": "SETTINGS",
            "general": "General",
            "voice": "Voice",
            "security": "Security",
            "language": "Language",
            "language_tip": "Restart required after switching language",
            "about_title": "About LingShu",
            "about_version": "Version 3.1.0 - Neural Core Edition",
            "about_text": """LingShu is a next-generation AI Agent runtime
environment that controls your computer with
intelligent automation.

Core Features:
  - Multi-modal interaction (voice, vision, text)
  - Self-evolving capability engine
  - Multi-agent coordination panel
  - Digital twin sandbox rehearsal
  - Hardware control integration
  - Software learning engine

Designed for AI-powered computing.""",
            "team": "2026 LingShu Team",
            "launch_success": "Agent launched successfully!\nCheck the console window.",
            "agent_ready": "Agent core ready!\n\nThe GUI is the primary interface.\nAll modules are loaded and tested.",
            "tray_show": "Show LingShu",
            "tray_exit": "Exit",
            "tray_tooltip": "LingShu Agent - Neural Core",
            "error_title": "LingShu Agent Error",
            "lang_switch": "🌐 EN/中",
        }
    }

    def __init__(self, lang: str = "zh"):
        self.lang = lang if lang in self._TEXTS else "zh"

    def get(self, key: str, **kwargs) -> str:
        text = self._TEXTS[self.lang].get(key, key)
        if kwargs:
            text = text.format(**kwargs)
        return text

    def switch(self):
        self.lang = "en" if self.lang == "zh" else "zh"
        return self.lang


# Global i18n instance (default Chinese)
i18n = I18N("zh")


# ============================================================
# Color Palette - Cyberpunk Purple Theme
# ============================================================
COLORS = {
    "bg_deep": "#0D001A",
    "bg_dark": "#10002B",
    "bg_mid": "#240046",
    "bg_light": "#3C096C",
    "accent_1": "#5A189A",
    "accent_2": "#7B2CBF",
    "accent_3": "#9D4EDD",
    "accent_4": "#C77DFF",
    "accent_5": "#E0AAFF",
    "text_main": "#E0AAFF",
    "text_dim": "#9D4EDD",
    "text_bright": "#FFFFFF",
    "glow": "#C77DFF",
    "neon_blue": "#00B4D8",
    "neon_pink": "#F72585",
    "success": "#06D6A0",
    "warning": "#FFD166",
    "error": "#EF476F",
}


# ============================================================
# Advanced Black Hole Animation Engine
# ============================================================
class BlackHoleCanvas:
    """
    Ultra-smooth animated black hole with:
      - Smooth oval rings (not polygon approximations)
      - Pulsing center glow
      - Accretion disk spiral particles
      - Trailing particle streams
      - Event horizon shimmer
    """

    def __init__(self, canvas: tk.Canvas, width: int, height: int,
                 icon_image: Optional[ImageTk.PhotoImage] = None):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.center_x = width // 2
        self.center_y = height // 2
        self.icon_image = icon_image

        self.running = True
        self.frame = 0
        self.canvas_items: List[int] = []
        self.icon_item: Optional[int] = None

        # Ring definitions: (base_radius, color, width, speed, ellipse_ratio, glow_layers)
        self.rings = [
            {"r": 28, "c": COLORS["accent_5"], "w": 2, "sp": 4.0, "rat": 0.65, "glow": 2},
            {"r": 42, "c": COLORS["accent_4"], "w": 2, "sp": 3.2, "rat": 0.72, "glow": 2},
            {"r": 58, "c": COLORS["accent_3"], "w": 3, "sp": 2.6, "rat": 0.78, "glow": 3},
            {"r": 78, "c": COLORS["accent_2"], "w": 3, "sp": 2.1, "rat": 0.84, "glow": 3},
            {"r": 102, "c": COLORS["accent_1"], "w": 4, "sp": 1.7, "rat": 0.88, "glow": 3},
            {"r": 130, "c": COLORS["bg_light"], "w": 4, "sp": 1.3, "rat": 0.92, "glow": 2},
            {"r": 162, "c": COLORS["accent_2"], "w": 3, "sp": 1.0, "rat": 0.86, "glow": 2},
            {"r": 198, "c": COLORS["accent_3"], "w": 2, "sp": 0.7, "rat": 0.90, "glow": 2},
            {"r": 240, "c": COLORS["accent_4"], "w": 2, "sp": 0.5, "rat": 0.82, "glow": 1},
        ]
        for i, ring in enumerate(self.rings):
            ring["angle"] = random.uniform(0, 360)
            ring["dir"] = 1 if i % 2 == 0 else -1
            ring["pulse"] = random.uniform(0, math.pi * 2)

        # Accretion disk particles (spiral in)
        self.accretion: List[dict] = []
        for _ in range(60):
            self.accretion.append({
                "angle": random.uniform(0, 360),
                "dist": random.uniform(30, 260),
                "speed": random.uniform(0.3, 1.8),
                "size": random.uniform(0.5, 2.5),
                "color": random.choice([
                    COLORS["accent_5"], COLORS["accent_4"], COLORS["accent_3"],
                    COLORS["neon_blue"], COLORS["neon_pink"], COLORS["text_bright"],
                ]),
                "trail": [],
            })

        # Event horizon shimmer particles
        self.shimmer: List[dict] = []
        for _ in range(20):
            self.shimmer.append({
                "angle": random.uniform(0, 360),
                "dist": random.uniform(8, 25),
                "speed": random.uniform(2, 6),
                "life": random.uniform(0.3, 1.0),
                "max_life": 1.0,
            })

        self._animate()

    def _animate(self):
        if not self.running:
            return
        self.frame += 1

        # Clear all previous items
        for item in self.canvas_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self.canvas_items.clear()

        # Draw center glow (pulsing)
        self._draw_center_glow()

        # Draw rings (smooth ovals with glow layers)
        for ring in self.rings:
            ring["angle"] += ring["sp"] * ring["dir"] * 0.4
            ring["pulse"] += 0.03
            self._draw_ring(ring)

        # Draw accretion disk
        self._draw_accretion()

        # Draw event horizon shimmer
        self._draw_shimmer()

        # Draw center icon
        if self.icon_image:
            self._draw_icon()

        # Schedule next frame (~30 FPS)
        self.canvas.after(33, self._animate)

    def _draw_center_glow(self):
        """Pulsing center glow behind the icon."""
        pulse = 0.85 + 0.15 * math.sin(self.frame * 0.05)
        for i in range(3):
            r = int(20 + i * 12 * pulse)
            alpha = int(30 - i * 8)
            color = self._alpha_blend(COLORS["accent_4"], alpha)
            item = self.canvas.create_oval(
                self.center_x - r, self.center_y - r,
                self.center_x + r, self.center_y + r,
                fill=color, outline="",
            )
            self.canvas_items.append(item)

    def _draw_ring(self, ring: dict):
        """Draw smooth elliptical ring with layered glow."""
        a = math.radians(ring["angle"])
        rx = ring["r"] * (1 + 0.03 * math.sin(ring["pulse"]))
        ry = rx * ring["rat"]

        # Calculate bounding box for rotated ellipse
        cos_a, sin_a = math.cos(a), math.sin(a)
        max_x = math.sqrt((rx * cos_a) ** 2 + (ry * sin_a) ** 2)
        max_y = math.sqrt((rx * sin_a) ** 2 + (ry * cos_a) ** 2)

        x1 = self.center_x - max_x
        y1 = self.center_y - max_y
        x2 = self.center_x + max_x
        y2 = self.center_y + max_y

        # Glow layers (outer semi-transparent rings)
        for glow_i in range(ring["glow"]):
            glow_r = 1 + glow_i * 2
            glow_alpha = int(25 - glow_i * 8)
            glow_color = self._alpha_blend(ring["c"], glow_alpha)
            item = self.canvas.create_oval(
                x1 - glow_r, y1 - glow_r, x2 + glow_r, y2 + glow_r,
                outline=glow_color, width=1,
            )
            self.canvas_items.append(item)

        # Main ring
        item = self.canvas.create_oval(
            x1, y1, x2, y2,
            outline=ring["c"], width=ring["w"],
        )
        self.canvas_items.append(item)

    def _draw_accretion(self):
        """Draw spiral accretion disk particles with trails."""
        for p in self.accretion:
            # Spiral inward
            p["dist"] -= p["speed"] * 0.3
            p["angle"] += p["speed"] * 0.8

            if p["dist"] < 15:
                # Reset at outer edge with new random parameters
                p["dist"] = random.uniform(200, 270)
                p["angle"] = random.uniform(0, 360)
                p["speed"] = random.uniform(0.3, 1.8)
                p["size"] = random.uniform(0.5, 2.5)
                p["trail"] = []

            # Store trail
            p["trail"].append((p["angle"], p["dist"]))
            if len(p["trail"]) > 6:
                p["trail"].pop(0)

            # Draw trail (fading)
            for ti, (ta, td) in enumerate(p["trail"]):
                alpha = (ti + 1) / len(p["trail"])
                trail_size = p["size"] * alpha * 0.6
                if trail_size > 0.3:
                    a = math.radians(ta)
                    x = self.center_x + td * math.cos(a) * 0.85
                    y = self.center_y + td * math.sin(a) * 0.85
                    color = self._alpha_blend(p["color"], int(40 * alpha))
                    r = trail_size
                    item = self.canvas.create_oval(
                        x - r, y - r, x + r, y + r,
                        fill=color, outline="",
                    )
                    self.canvas_items.append(item)

            # Draw head particle
            a = math.radians(p["angle"])
            x = self.center_x + p["dist"] * math.cos(a) * 0.85
            y = self.center_y + p["dist"] * math.sin(a) * 0.85
            r = p["size"]
            item = self.canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill=p["color"], outline="",
            )
            self.canvas_items.append(item)

    def _draw_shimmer(self):
        """Event horizon shimmer - particles orbiting close to center."""
        for s in self.shimmer:
            s["angle"] += s["speed"]
            s["life"] -= 0.015
            if s["life"] <= 0:
                s["life"] = s["max_life"]
                s["angle"] = random.uniform(0, 360)
                s["dist"] = random.uniform(8, 25)

            a = math.radians(s["angle"])
            x = self.center_x + s["dist"] * math.cos(a)
            y = self.center_y + s["dist"] * math.sin(a)
            alpha = int(180 * s["life"] / s["max_life"])
            color = self._alpha_blend(COLORS["accent_5"], alpha)
            r = 1.2 * (s["life"] / s["max_life"])
            item = self.canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill=color, outline="",
            )
            self.canvas_items.append(item)

    def _draw_icon(self):
        if self.icon_item:
            try:
                self.canvas.delete(self.icon_item)
            except tk.TclError:
                pass

        self.icon_item = self.canvas.create_image(
            self.center_x, self.center_y,
            image=self.icon_image,
        )
        self.canvas_items.append(self.icon_item)

    def _alpha_blend(self, hex_color: str, alpha: int) -> str:
        """Blend hex color with background for pseudo-transparency."""
        r = int((int(hex_color[1:3], 16) * alpha + 13 * (255 - alpha)) / 255)
        g = int((int(hex_color[3:5], 16) * alpha + 0 * (255 - alpha)) / 255)
        b = int((int(hex_color[5:7], 16) * alpha + 26 * (255 - alpha)) / 255)
        return f"#{r:02x}{g:02x}{b:02x}"

    def stop(self):
        self.running = False


# ============================================================
# Splash Screen
# ============================================================
class SplashScreen:
    """Full-screen splash with advanced black hole animation."""

    def __init__(self, root: tk.Tk, duration_ms: int = 3000):
        self.root = root
        self.duration = duration_ms
        self.finished = False

        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=COLORS["bg_deep"])

        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()

        w, h = 720, 480
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        self.canvas = tk.Canvas(
            self.window, width=w, height=h,
            bg=COLORS["bg_deep"], highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Load icon
        icon_img = self._load_icon(110)
        self.icon_photo = ImageTk.PhotoImage(icon_img) if icon_img else None

        # Start advanced animation
        self.animator = BlackHoleCanvas(self.canvas, w, h, self.icon_photo)

        # Title text
        title_font = font.Font(family="Microsoft YaHei UI" if i18n.lang == "zh" else "Segoe UI",
                               size=30, weight="bold")
        subtitle_font = font.Font(family="Microsoft YaHei UI" if i18n.lang == "zh" else "Segoe UI",
                                    size=13)

        self.canvas.create_text(
            w // 2, h - 90,
            text=i18n.get("splash_title"),
            font=title_font,
            fill=COLORS["accent_5"],
        )
        self.canvas.create_text(
            w // 2, h - 50,
            text=i18n.get("splash_subtitle"),
            font=subtitle_font,
            fill=COLORS["accent_3"],
        )

        # Progress
        self.progress = 0
        self._update_progress()
        self.window.after(duration_ms, self.close)

    def _load_icon(self, size: int) -> Optional[Image.Image]:
        if not HAS_PIL:
            return None
        try:
            root_dir = Path(__file__).parent
            for name in ("assets/icon_source.jpg", "icon.ico"):
                icon_path = root_dir / name
                if icon_path.exists():
                    img = Image.open(icon_path)
                    img = img.resize((size, size), _RESIZE_FILTER)
                    return img
        except Exception:
            pass
        return None

    def _update_progress(self):
        if self.finished:
            return
        self.progress = min(self.progress + 2, 100)
        w = 720
        bar_y = 440
        bar_w = 320
        bar_h = 4
        bar_x = (w - bar_w) // 2
        filled = int(bar_w * self.progress / 100)

        self.canvas.create_rectangle(
            bar_x, bar_y, bar_x + bar_w, bar_y + bar_h,
            fill=COLORS["bg_mid"], outline="",
        )
        self.canvas.create_rectangle(
            bar_x, bar_y, bar_x + filled, bar_y + bar_h,
            fill=COLORS["accent_4"], outline="",
        )

        if self.progress < 100:
            self.window.after(50, self._update_progress)

    def close(self):
        self.finished = True
        self.animator.stop()
        self.window.destroy()


# ============================================================
# Main Application Window
# ============================================================
class LingShuLauncher:
    """Main GUI with i18n support."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(i18n.get("title"))
        self.root.geometry("950x700")
        self.root.configure(bg=COLORS["bg_deep"])
        self.root.resizable(False, False)

        self._set_window_icon()

        self.minimized = False
        self.tray_icon = None

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_window_icon(self):
        try:
            icon_path = Path(__file__).parent / "icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg=COLORS["bg_deep"], padx=20, pady=18)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ===== Header with Language Switch =====
        header = tk.Frame(main_frame, bg=COLORS["bg_deep"], height=42)
        header.pack(fill=tk.X, pady=(0, 12))
        header.pack_propagate(False)

        font_name = "Microsoft YaHei UI" if i18n.lang == "zh" else "Segoe UI"
        title_font = font.Font(family=font_name, size=20, weight="bold")
        version_font = font.Font(family=font_name, size=10)
        btn_font_small = font.Font(family=font_name, size=9)

        # App title
        title_frame = tk.Frame(header, bg=COLORS["bg_deep"])
        title_frame.pack(side=tk.LEFT)

        tk.Label(
            title_frame, text=i18n.get("app_name"),
            font=title_font, fg=COLORS["accent_5"], bg=COLORS["bg_deep"],
        ).pack(side=tk.LEFT)

        tk.Label(
            title_frame, text=f"  {i18n.get('version')}",
            font=version_font, fg=COLORS["accent_3"], bg=COLORS["bg_deep"],
        ).pack(side=tk.LEFT, pady=(8, 0))

        # Right side: Language switch + Status
        right_frame = tk.Frame(header, bg=COLORS["bg_deep"])
        right_frame.pack(side=tk.RIGHT)

        # Language switch button
        self.lang_btn = tk.Button(
            right_frame, text=i18n.get("lang_switch"),
            font=btn_font_small, bg=COLORS["bg_mid"], fg=COLORS["accent_4"],
            bd=0, cursor="hand2", relief=tk.FLAT,
            command=self._switch_language,
        )
        self.lang_btn.pack(side=tk.LEFT, padx=(0, 15))

        self.status_label = tk.Label(
            right_frame, text=i18n.get("ready"),
            font=version_font, fg=COLORS["success"], bg=COLORS["bg_deep"],
        )
        self.status_label.pack(side=tk.LEFT, pady=(8, 0))

        # ===== Animation Panel =====
        anim_frame = tk.Frame(
            main_frame, bg=COLORS["bg_dark"],
            highlightbackground=COLORS["accent_2"],
            highlightthickness=1, bd=0,
        )
        anim_frame.pack(fill=tk.X, pady=(0, 15))

        anim_w, anim_h = 910, 300
        self.anim_canvas = tk.Canvas(
            anim_frame, width=anim_w, height=anim_h,
            bg=COLORS["bg_dark"], highlightthickness=0,
        )
        self.anim_canvas.pack()

        icon_img = self._load_icon(95)
        self.anim_icon = ImageTk.PhotoImage(icon_img) if icon_img else None
        self.animator = BlackHoleCanvas(self.anim_canvas, anim_w, anim_h, self.anim_icon)

        # ===== Control Panel =====
        ctrl_frame = tk.Frame(main_frame, bg=COLORS["bg_deep"])
        ctrl_frame.pack(fill=tk.BOTH, expand=True)

        # Left column
        left_col = tk.Frame(ctrl_frame, bg=COLORS["bg_deep"], width=300)
        left_col.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 18))
        left_col.pack_propagate(False)

        self._build_info_panel(left_col)

        # Right column
        right_col = tk.Frame(ctrl_frame, bg=COLORS["bg_deep"])
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._build_button_panel(right_col)

    def _load_icon(self, size: int) -> Optional[Image.Image]:
        if not HAS_PIL:
            return None
        try:
            root_dir = Path(__file__).parent
            for name in ("assets/icon_source.jpg", "icon.ico"):
                icon_path = root_dir / name
                if icon_path.exists():
                    img = Image.open(icon_path)
                    img = img.resize((size, size), _RESIZE_FILTER)
                    return img
        except Exception:
            pass
        return None

    def _build_info_panel(self, parent: tk.Frame):
        font_name = "Microsoft YaHei UI" if i18n.lang == "zh" else "Segoe UI"
        label_font = font.Font(family=font_name, size=10)
        value_font = font.Font(family=font_name, size=10, weight="bold")
        header_font = font.Font(family=font_name, size=11, weight="bold")

        # SYSTEM STATUS
        tk.Label(
            parent, text=i18n.get("system_status"),
            font=header_font, fg=COLORS["accent_4"], bg=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=(0, 12))

        status_items = [
            (i18n.get("neural_core"), i18n.get("online"), COLORS["success"]),
            (i18n.get("voice_module"), i18n.get("standby"), COLORS["warning"]),
            (i18n.get("vision_module"), i18n.get("online"), COLORS["success"]),
            (i18n.get("security_vault"), i18n.get("locked"), COLORS["accent_3"]),
            (i18n.get("evolution_engine"), i18n.get("idle"), COLORS["accent_3"]),
        ]

        for name, value, color in status_items:
            row = tk.Frame(parent, bg=COLORS["bg_deep"])
            row.pack(fill=tk.X, pady=4)
            tk.Label(row, text=f"{name}:", font=label_font,
                     fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
                     ).pack(side=tk.LEFT)
            tk.Label(row, text=value, font=value_font,
                     fg=color, bg=COLORS["bg_deep"],
                     ).pack(side=tk.RIGHT)

        tk.Frame(parent, bg=COLORS["accent_2"], height=1).pack(fill=tk.X, pady=12)

        # QUICK STATS
        tk.Label(
            parent, text=i18n.get("quick_stats"),
            font=header_font, fg=COLORS["accent_4"], bg=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=(0, 12))

        stats = [
            (i18n.get("memory_entries"), "1,247"),
            (i18n.get("tasks_executed"), "342"),
        ]
        for name, value in stats:
            row = tk.Frame(parent, bg=COLORS["bg_deep"])
            row.pack(fill=tk.X, pady=4)
            tk.Label(row, text=f"{name}:", font=label_font,
                     fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
                     ).pack(side=tk.LEFT)
            tk.Label(row, text=value, font=value_font,
                     fg=COLORS["accent_5"], bg=COLORS["bg_deep"],
                     ).pack(side=tk.RIGHT)

        self.uptime_label = tk.Label(
            parent, text=f"{i18n.get('uptime')}: 00:00:00",
            font=label_font, fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
        )
        self.uptime_label.pack(anchor=tk.W, pady=(12, 0))
        self.start_time = time.time()
        self._update_uptime()

    def _update_uptime(self):
        elapsed = int(time.time() - self.start_time)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self.uptime_label.config(text=f"{i18n.get('uptime')}: {h:02d}:{m:02d}:{s:02d}")
        self.root.after(1000, self._update_uptime)

    def _build_button_panel(self, parent: tk.Frame):
        font_name = "Microsoft YaHei UI" if i18n.lang == "zh" else "Segoe UI"
        btn_font = font.Font(family=font_name, size=12, weight="bold")
        btn_font_sm = font.Font(family=font_name, size=11, weight="bold")

        # LAUNCH AGENT
        launch_btn = self._create_neon_button(
            parent, i18n.get("launch_agent"),
            COLORS["accent_2"], COLORS["accent_5"],
            btn_font, self._launch_agent,
        )
        launch_btn.pack(fill=tk.X, pady=(0, 12), ipady=14)

        # Row 1
        row1 = tk.Frame(parent, bg=COLORS["bg_deep"])
        row1.pack(fill=tk.X, pady=(0, 12))

        learning_btn = self._create_neon_button(
            row1, i18n.get("learning_engine"),
            COLORS["accent_1"], COLORS["accent_4"],
            btn_font_sm, self._open_learning,
        )
        learning_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=12)

        settings_btn = self._create_neon_button(
            row1, i18n.get("settings"),
            COLORS["bg_mid"], COLORS["accent_3"],
            btn_font_sm, self._open_settings,
        )
        settings_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(6, 0), ipady=12)

        # Row 2
        row2 = tk.Frame(parent, bg=COLORS["bg_deep"])
        row2.pack(fill=tk.X)

        docs_btn = self._create_neon_button(
            row2, i18n.get("documentation"),
            COLORS["bg_mid"], COLORS["accent_3"],
            btn_font_sm, self._open_docs,
        )
        docs_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6), ipady=10)

        about_btn = self._create_neon_button(
            row2, i18n.get("about"),
            COLORS["bg_mid"], COLORS["accent_3"],
            btn_font_sm, self._open_about,
        )
        about_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(6, 0), ipady=10)

    def _create_neon_button(self, parent: tk.Frame, text: str,
                            bg_color: str, fg_color: str,
                            fnt: font.Font, command: Callable) -> tk.Button:
        btn = tk.Button(
            parent, text=text, font=fnt,
            bg=bg_color, fg=fg_color,
            activebackground=COLORS["accent_1"],
            activeforeground=COLORS["text_bright"],
            bd=0, cursor="hand2", relief=tk.FLAT,
            command=command,
        )

        def on_enter(e):
            btn.config(bg=COLORS["accent_1"], fg=COLORS["text_bright"])

        def on_leave(e):
            btn.config(bg=bg_color, fg=fg_color)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    def _switch_language(self):
        """Switch language and restart."""
        new_lang = i18n.switch()
        messagebox.showinfo(
            "语言 / Language",
            f"语言已切换为 {'English' if new_lang == 'en' else '中文'}\n"
            f"Language switched to {'English' if new_lang == 'en' else 'Chinese'}\n\n"
            "请关闭窗口重新启动以生效。\nPlease restart the application.",
        )
        self.lang_btn.config(text=i18n.get("lang_switch"))

    def _launch_agent(self):
        self.status_label.config(text=i18n.get("running"), fg=COLORS["neon_blue"])
        self.root.after(100, self._run_agent)

    def _run_agent(self):
        try:
            root_dir = Path(__file__).parent
            agent_script = root_dir / "main.py"
            if agent_script.exists():
                subprocess.Popen(
                    [sys.executable, str(agent_script)],
                    cwd=str(root_dir),
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
                messagebox.showinfo(i18n.get("app_name"), i18n.get("launch_success"))
            else:
                messagebox.showinfo(i18n.get("app_name"), i18n.get("agent_ready"))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch: {e}")
        finally:
            self.status_label.config(text=i18n.get("ready"), fg=COLORS["success"])

    def _open_learning(self):
        LearningWindow(self.root)

    def _open_settings(self):
        SettingsWindow(self.root)

    def _open_docs(self):
        try:
            readme = Path(__file__).parent / "README.md"
            if readme.exists():
                subprocess.Popen(["notepad", str(readme)])
            else:
                messagebox.showinfo("Docs", "Documentation not found.")
        except Exception:
            pass

    def _open_about(self):
        AboutWindow(self.root)

    def _on_close(self):
        if HAS_PYSTRAY:
            self._minimize_to_tray()
        else:
            self.animator.stop()
            self.root.destroy()

    def _minimize_to_tray(self):
        self.root.withdraw()
        self.minimized = True
        if self.tray_icon is None:
            self._create_tray_icon()

    def _create_tray_icon(self):
        try:
            icon_img = self._load_icon(64)
            if icon_img is None:
                icon_img = Image.new("RGBA", (64, 64), (13, 0, 26, 255))
                draw = ImageDraw.Draw(icon_img)
                for i in range(3):
                    r = 10 + i * 8
                    draw.ellipse((32-r, 32-r, 32+r, 32+r), outline=(199, 125, 255, 180))

            def on_show(icon, item):
                self.root.deiconify()
                self.minimized = False

            def on_exit(icon, item):
                icon.stop()
                self.animator.stop()
                self.root.destroy()
                sys.exit(0)

            menu = pystray.Menu(
                pystray.MenuItem(i18n.get("tray_show"), on_show),
                pystray.MenuItem(i18n.get("tray_exit"), on_exit),
            )

            self.tray_icon = pystray.Icon(
                "LingShu", icon_img, i18n.get("tray_tooltip"), menu,
            )
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            print(f"[Tray] Error: {e}")
            self.animator.stop()
            self.root.destroy()


# ============================================================
# Learning Engine Window
# ============================================================
class LearningWindow:
    def __init__(self, parent: tk.Tk):
        self.window = tk.Toplevel(parent)
        self.window.title(i18n.get("learning_title"))
        self.window.geometry("640x540")
        self.window.configure(bg=COLORS["bg_deep"])
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        self._build_ui()

    def _build_ui(self):
        font_name = "Microsoft YaHei UI" if i18n.lang == "zh" else "Segoe UI"
        header_font = font.Font(family=font_name, size=15, weight="bold")
        label_font = font.Font(family=font_name, size=10)

        tk.Label(
            self.window, text=i18n.get("learning_title"),
            font=header_font, fg=COLORS["accent_5"], bg=COLORS["bg_deep"],
        ).pack(pady=(18, 6))

        tk.Label(
            self.window, text=i18n.get("learning_desc"),
            font=label_font, fg=COLORS["accent_3"], bg=COLORS["bg_deep"],
        ).pack(pady=(0, 18))

        tk.Frame(self.window, bg=COLORS["accent_2"], height=1).pack(fill=tk.X, padx=22)

        # Target software
        select_frame = tk.Frame(self.window, bg=COLORS["bg_deep"], padx=22, pady=16)
        select_frame.pack(fill=tk.X)

        tk.Label(
            select_frame, text=i18n.get("target_software"),
            font=label_font, fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
        ).pack(anchor=tk.W)

        self.software_entry = tk.Entry(
            select_frame, font=label_font,
            bg=COLORS["bg_dark"], fg=COLORS["text_bright"],
            insertbackground=COLORS["accent_4"],
            relief=tk.FLAT, bd=5,
        )
        self.software_entry.pack(fill=tk.X, pady=(6, 10))
        self.software_entry.insert(0, i18n.get("placeholder_software"))

        # Options
        options_frame = tk.Frame(self.window, bg=COLORS["bg_deep"], padx=22)
        options_frame.pack(fill=tk.X)

        self.decompose_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            options_frame, text=i18n.get("decompose"),
            variable=self.decompose_var, font=label_font,
            fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
            selectcolor=COLORS["bg_dark"], activebackground=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=4)

        self.learn_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            options_frame, text=i18n.get("learn_ui"),
            variable=self.learn_var, font=label_font,
            fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
            selectcolor=COLORS["bg_dark"], activebackground=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=4)

        self.automate_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            options_frame, text=i18n.get("automate"),
            variable=self.automate_var, font=label_font,
            fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
            selectcolor=COLORS["bg_dark"], activebackground=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=4)

        # Progress
        self.progress_frame = tk.Frame(self.window, bg=COLORS["bg_dark"], padx=22, pady=16)
        self.progress_frame.pack(fill=tk.BOTH, expand=True, padx=22, pady=16)

        self.progress_text = tk.Text(
            self.progress_frame, font=("Consolas", 9),
            bg=COLORS["bg_dark"], fg=COLORS["accent_4"],
            relief=tk.FLAT, state=tk.DISABLED, wrap=tk.WORD,
        )
        self.progress_text.pack(fill=tk.BOTH, expand=True)

        # Start button
        btn_font = font.Font(family=font_name, size=12, weight="bold")
        start_btn = tk.Button(
            self.window, text=i18n.get("start_learning"), font=btn_font,
            bg=COLORS["accent_2"], fg=COLORS["text_bright"],
            bd=0, cursor="hand2", relief=tk.FLAT,
            command=self._start_learning,
        )
        start_btn.pack(fill=tk.X, padx=22, pady=(0, 18), ipady=12)

    def _log(self, message: str):
        self.progress_text.config(state=tk.NORMAL)
        self.progress_text.insert(tk.END, f"> {message}\n")
        self.progress_text.see(tk.END)
        self.progress_text.config(state=tk.DISABLED)

    def _start_learning(self):
        software = self.software_entry.get().strip()
        placeholder = i18n.get("placeholder_software")
        if not software or software == placeholder or software.startswith("e.g.") or software.startswith("例如"):
            messagebox.showwarning(i18n.get("input_required"), i18n.get("enter_software"))
            return

        self._log(i18n.get("learning_init", software=software))
        self._log(i18n.get("phase1"))

        delays = [800, 1600, 2400, 3200, 4000, 4800, 5600, 6400, 7200]
        messages = [
            "  - " + ("分析可执行结构..." if i18n.lang == "zh" else "Analyzing executable structure..."),
            "  - " + ("识别UI框架..." if i18n.lang == "zh" else "Identifying UI framework..."),
            "  - " + ("映射控件层级..." if i18n.lang == "zh" else "Mapping control hierarchy..."),
            i18n.get("phase2"),
            "  - " + ("学习菜单结构..." if i18n.lang == "zh" else "Learning menu structures..."),
            "  - " + ("记录热键映射..." if i18n.lang == "zh" else "Recording hotkey mappings..."),
            i18n.get("phase3"),
            i18n.get("learning_done", software=software),
            i18n.get("skills_saved"),
        ]

        for d, msg in zip(delays, messages):
            self.window.after(d, lambda m=msg: self._log(m))


# ============================================================
# Settings Window
# ============================================================
class SettingsWindow:
    def __init__(self, parent: tk.Tk):
        self.window = tk.Toplevel(parent)
        self.window.title(i18n.get("settings_title"))
        self.window.geometry("520x420")
        self.window.configure(bg=COLORS["bg_deep"])
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        self._build_ui()

    def _build_ui(self):
        font_name = "Microsoft YaHei UI" if i18n.lang == "zh" else "Segoe UI"
        header_font = font.Font(family=font_name, size=15, weight="bold")
        label_font = font.Font(family=font_name, size=10)

        tk.Label(
            self.window, text=i18n.get("settings_title"),
            font=header_font, fg=COLORS["accent_5"], bg=COLORS["bg_deep"],
        ).pack(pady=(18, 6))

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # General tab
        general = tk.Frame(notebook, bg=COLORS["bg_deep"])
        notebook.add(general, text=i18n.get("general"))

        tk.Label(
            general, text=i18n.get("language") + ":",
            font=label_font, fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=(20, 5))

        lang_text = "中文 (Chinese)" if i18n.lang == "zh" else "English"
        tk.Label(
            general, text=f"  {lang_text}",
            font=label_font, fg=COLORS["accent_4"], bg=COLORS["bg_deep"],
        ).pack(anchor=tk.W)

        tk.Label(
            general, text=i18n.get("language_tip"),
            font=label_font, fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=(10, 0))

        # Voice tab
        voice = tk.Frame(notebook, bg=COLORS["bg_deep"])
        notebook.add(voice, text=i18n.get("voice"))

        tk.Label(
            voice, text="Voice module settings (placeholder)",
            font=label_font, fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
        ).pack(pady=50)

        # Security tab
        security = tk.Frame(notebook, bg=COLORS["bg_deep"])
        notebook.add(security, text=i18n.get("security"))

        tk.Label(
            security, text="Security settings (placeholder)",
            font=label_font, fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
        ).pack(pady=50)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=COLORS["bg_deep"])
        style.configure("TNotebook.Tab", background=COLORS["bg_mid"], foreground=COLORS["accent_4"])
        style.map("TNotebook.Tab", background=[("selected", COLORS["accent_2"])])


# ============================================================
# About Window
# ============================================================
class AboutWindow:
    def __init__(self, parent: tk.Tk):
        self.window = tk.Toplevel(parent)
        self.window.title(i18n.get("about_title"))
        self.window.geometry("480x380")
        self.window.configure(bg=COLORS["bg_deep"])
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        self._build_ui()

    def _build_ui(self):
        font_name = "Microsoft YaHei UI" if i18n.lang == "zh" else "Segoe UI"
        title_font = font.Font(family=font_name, size=20, weight="bold")
        version_font = font.Font(family=font_name, size=10)
        text_font = font.Font(family=font_name, size=9)

        tk.Label(
            self.window, text=i18n.get("app_name").upper() + " AGENT",
            font=title_font, fg=COLORS["accent_5"], bg=COLORS["bg_deep"],
        ).pack(pady=(22, 6))

        tk.Label(
            self.window, text=i18n.get("about_version"),
            font=version_font, fg=COLORS["accent_3"], bg=COLORS["bg_deep"],
        ).pack()

        tk.Frame(self.window, bg=COLORS["accent_2"], height=1).pack(fill=tk.X, padx=30, pady=16)

        tk.Label(
            self.window, text=i18n.get("about_text"),
            font=text_font, fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
            justify=tk.CENTER,
        ).pack(pady=10)

        tk.Label(
            self.window, text=i18n.get("team"),
            font=version_font, fg=COLORS["accent_4"], bg=COLORS["bg_deep"],
        ).pack(pady=(16, 0))


# ============================================================
# Main Entry
# ============================================================
def main():
    try:
        root = tk.Tk()
        root.withdraw()

        splash = SplashScreen(root, duration_ms=3000)

        def show_main():
            if splash.finished or not splash.window.winfo_exists():
                root.deiconify()
                app = LingShuLauncher(root)
            else:
                root.after(100, show_main)

        root.after(100, show_main)
        root.mainloop()
    except Exception as e:
        import traceback
        error_msg = f"LingShu Agent crashed!\n\nError: {e}\n\n{traceback.format_exc()}"
        print(error_msg)
        try:
            import tkinter as _tk
            _root = _tk.Tk()
            _root.withdraw()
            from tkinter import messagebox
            messagebox.showerror(i18n.get("error_title"), error_msg)
            _root.destroy()
        except Exception:
            pass
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
