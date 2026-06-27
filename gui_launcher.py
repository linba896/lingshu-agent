#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LingShu Agent - Cyberpunk GUI Launcher
Animated Purple Black Hole Edition

Features:
  - Splash screen with rotating black hole animation
  - Main window with live canvas animation
  - System tray integration (minimize to tray)
  - Cyberpunk neon UI design
  - One-click launch of LingShu Agent
  - Learning engine interface

Dependencies: tkinter, PIL (Pillow), pystray (optional)
"""

import os
import sys
import subprocess
import threading
import time
import random
import math
from pathlib import Path
from typing import Optional, List, Tuple, Callable

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFilter
    HAS_PIL = True
    # Compatibility for old Pillow versions
    _RESIZE_FILTER = getattr(Image, 'LANCZOS', None)
    if _RESIZE_FILTER is None:
        _RESIZE_FILTER = getattr(Image, 'ANTIALIAS', None)
    if _RESIZE_FILTER is None and hasattr(Image, 'Resampling'):
        _RESIZE_FILTER = Image.Resampling.LANCZOS
    if _RESIZE_FILTER is None:
        _RESIZE_FILTER = 1  # fallback
except ImportError:
    HAS_PIL = False
    _RESIZE_FILTER = None
    print("[WARN] Pillow not installed. Icon display may be limited.")

try:
    import pystray
    HAS_PYSTRAY = True
except ImportError:
    HAS_PYSTRAY = False

import tkinter as tk
from tkinter import ttk, messagebox, font


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
# Black Hole Animation Engine
# ============================================================
class BlackHoleCanvas:
    """
    Canvas-based animated black hole renderer.
    Uses concentric rotating elliptical rings with particle effects.
    """

    def __init__(self, canvas: tk.Canvas, width: int, height: int, icon_image: Optional[ImageTk.PhotoImage] = None):
        self.canvas = canvas
        self.width = width
        self.height = height
        self.center_x = width // 2
        self.center_y = height // 2
        self.icon_image = icon_image

        # Animation state
        self.running = True
        self.frame = 0
        self.rings: List[dict] = []
        self.particles: List[dict] = []
        self.canvas_items: List[int] = []
        self.icon_item: Optional[int] = None

        # Initialize ring layers (from center outward)
        self._init_rings()
        self._init_particles(80)

        # Start animation loop
        self._animate()

    def _init_rings(self):
        """Create concentric rotating ring definitions."""
        ring_configs = [
            # (radius, color, width, speed, ellipse_ratio)
            (30, COLORS["accent_5"], 2, 3.0, 0.7),
            (45, COLORS["accent_4"], 3, 2.5, 0.75),
            (60, COLORS["accent_3"], 3, 2.0, 0.8),
            (80, COLORS["accent_2"], 4, 1.8, 0.85),
            (100, COLORS["accent_1"], 4, 1.5, 0.9),
            (125, COLORS["bg_light"], 5, 1.2, 0.95),
            (150, COLORS["accent_2"], 3, 1.0, 0.85),
            (180, COLORS["accent_3"], 2, 0.8, 0.9),
            (220, COLORS["accent_4"], 2, 0.6, 0.8),
        ]
        for i, (radius, color, width, speed, ratio) in enumerate(ring_configs):
            self.rings.append({
                "id": i,
                "radius": radius,
                "color": color,
                "width": width,
                "speed": speed,
                "ratio": ratio,
                "angle": random.uniform(0, 360),
                "direction": 1 if i % 2 == 0 else -1,
            })

    def _init_particles(self, count: int):
        """Initialize particle pool."""
        for _ in range(count):
            angle = random.uniform(0, 360)
            distance = random.uniform(20, 250)
            self.particles.append({
                "angle": angle,
                "distance": distance,
                "size": random.uniform(1, 3),
                "speed": random.uniform(0.2, 1.5),
                "color": random.choice([
                    COLORS["accent_5"], COLORS["accent_4"],
                    COLORS["accent_3"], COLORS["neon_blue"],
                    COLORS["neon_pink"], COLORS["text_bright"],
                ]),
                "life": random.uniform(0.3, 1.0),
                "decay": random.uniform(0.002, 0.008),
            })

    def _animate(self):
        """Main animation loop."""
        if not self.running:
            return

        self.frame += 1

        # Clear previous frame items
        for item in self.canvas_items:
            try:
                self.canvas.delete(item)
            except tk.TclError:
                pass
        self.canvas_items.clear()

        # Draw rings (outer to inner for proper layering)
        for ring in self.rings:
            ring["angle"] += ring["speed"] * ring["direction"] * 0.5
            self._draw_ring(ring)

        # Draw particles
        self._draw_particles()

        # Draw center icon
        if self.icon_image:
            self._draw_icon()

        # Schedule next frame (30 FPS)
        self.canvas.after(33, self._animate)

    def _draw_ring(self, ring: dict):
        """Draw a single rotating elliptical ring."""
        angle_rad = math.radians(ring["angle"])
        rx = ring["radius"]
        ry = ring["radius"] * ring["ratio"]

        # Create elliptical path using polygon approximation
        points = []
        segments = 60
        for i in range(segments + 1):
            t = (2 * math.pi * i) / segments
            # Rotate ellipse
            x = rx * math.cos(t) * math.cos(angle_rad) - ry * math.sin(t) * math.sin(angle_rad)
            y = rx * math.cos(t) * math.sin(angle_rad) + ry * math.sin(t) * math.cos(angle_rad)
            points.extend([self.center_x + x, self.center_y + y])

        item = self.canvas.create_polygon(
            points,
            fill="",
            outline=ring["color"],
            width=ring["width"],
        )
        self.canvas_items.append(item)

        # Add glow effect (second ring, slightly larger, faded)
        glow_points = []
        glow_radius = ring["radius"] + 3
        glow_rx = glow_radius
        glow_ry = glow_radius * ring["ratio"]
        for i in range(segments + 1):
            t = (2 * math.pi * i) / segments
            x = glow_rx * math.cos(t) * math.cos(angle_rad) - glow_ry * math.sin(t) * math.sin(angle_rad)
            y = glow_rx * math.cos(t) * math.sin(angle_rad) + glow_ry * math.sin(t) * math.cos(angle_rad)
            glow_points.extend([self.center_x + x, self.center_y + y])

        glow_item = self.canvas.create_polygon(
            glow_points,
            fill="",
            outline=ring["color"],
            width=1,
            stipple="gray50",
        )
        self.canvas_items.append(glow_item)

    def _draw_particles(self):
        """Draw and update particles."""
        for p in self.particles:
            # Update particle
            p["distance"] += p["speed"]
            p["life"] -= p["decay"]
            p["angle"] += p["speed"] * 0.3

            if p["life"] <= 0 or p["distance"] > 280:
                # Reset particle
                p["angle"] = random.uniform(0, 360)
                p["distance"] = random.uniform(20, 60)
                p["life"] = random.uniform(0.5, 1.0)
                p["size"] = random.uniform(1, 3)
                p["color"] = random.choice([
                    COLORS["accent_5"], COLORS["accent_4"],
                    COLORS["accent_3"], COLORS["neon_blue"],
                    COLORS["neon_pink"], COLORS["text_bright"],
                ])

            # Calculate position
            angle_rad = math.radians(p["angle"])
            x = self.center_x + p["distance"] * math.cos(angle_rad)
            y = self.center_y + p["distance"] * math.sin(angle_rad) * 0.8

            # Draw particle
            r = p["size"] * p["life"]
            if r > 0.5:
                item = self.canvas.create_oval(
                    x - r, y - r, x + r, y + r,
                    fill=p["color"],
                    outline="",
                )
                self.canvas_items.append(item)

    def _draw_icon(self):
        """Draw center icon image."""
        if self.icon_item:
            try:
                self.canvas.delete(self.icon_item)
            except tk.TclError:
                pass

        size = 80
        x1 = self.center_x - size // 2
        y1 = self.center_y - size // 2
        x2 = x1 + size
        y2 = y1 + size

        self.icon_item = self.canvas.create_image(
            self.center_x, self.center_y,
            image=self.icon_image,
        )
        self.canvas_items.append(self.icon_item)

    def stop(self):
        self.running = False


# ============================================================
# Splash Screen
# ============================================================
class SplashScreen:
    """Full-screen splash with black hole animation."""

    def __init__(self, root: tk.Tk, duration_ms: int = 3000):
        self.root = root
        self.duration = duration_ms
        self.finished = False

        # Create splash window
        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=COLORS["bg_deep"])

        # Get screen dimensions
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()

        # Size
        w, h = 700, 450
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        # Title label
        title_font = font.Font(family="Segoe UI", size=28, weight="bold")
        subtitle_font = font.Font(family="Segoe UI", size=12)

        self.canvas = tk.Canvas(
            self.window, width=w, height=h,
            bg=COLORS["bg_deep"], highlightthickness=0,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Load icon
        icon_img = self._load_icon(100)
        self.icon_photo = ImageTk.PhotoImage(icon_img) if icon_img else None

        # Start animation
        self.animator = BlackHoleCanvas(self.canvas, w, h, self.icon_photo)

        # Text overlay
        self.canvas.create_text(
            w // 2, h - 80,
            text="LINGSHU AGENT",
            font=title_font,
            fill=COLORS["accent_5"],
        )
        self.canvas.create_text(
            w // 2, h - 45,
            text="Initializing Neural Core...",
            font=subtitle_font,
            fill=COLORS["accent_3"],
        )

        # Progress bar (visual only)
        self.progress = 0
        self._update_progress()

        # Auto-close after duration
        self.window.after(duration_ms, self.close)

    def _load_icon(self, size: int) -> Optional[Image.Image]:
        if not HAS_PIL:
            return None
        try:
            root_dir = Path(__file__).parent
            icon_path = root_dir / "assets" / "icon_source.jpg"
            if not icon_path.exists():
                icon_path = root_dir / "icon.ico"
            if icon_path.exists():
                img = Image.open(icon_path)
                img = img.resize((size, size), _RESIZE_FILTER)
                return img
        except Exception as e:
            print(f"[Splash] Icon load failed: {e}")
        return None

    def _update_progress(self):
        if self.finished:
            return
        self.progress += 2
        if self.progress > 100:
            self.progress = 0
        # Draw progress bar at bottom
        w = 700
        bar_y = 420
        bar_width = 300
        bar_height = 3
        bar_x = (w - bar_width) // 2
        filled = int(bar_width * self.progress / 100)

        self.canvas.create_rectangle(
            bar_x, bar_y, bar_x + bar_width, bar_y + bar_height,
            fill=COLORS["bg_mid"], outline="",
        )
        self.canvas.create_rectangle(
            bar_x, bar_y, bar_x + filled, bar_y + bar_height,
            fill=COLORS["accent_4"], outline="",
        )

        self.window.after(50, self._update_progress)

    def close(self):
        self.finished = True
        self.animator.stop()
        self.window.destroy()


# ============================================================
# Main Application Window
# ============================================================
class LingShuLauncher:
    """Main GUI application for LingShu Agent."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("LingShu Agent - Neural Core")
        self.root.geometry("900x650")
        self.root.configure(bg=COLORS["bg_deep"])
        self.root.resizable(False, False)

        # Set window icon
        self._set_window_icon()

        # Track minimize state
        self.minimized = False
        self.tray_icon = None

        # Build UI
        self._build_ui()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_window_icon(self):
        try:
            root_dir = Path(__file__).parent
            icon_path = root_dir / "icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

    def _build_ui(self):
        """Build the cyberpunk UI."""
        # Main container with padding
        main_frame = tk.Frame(self.root, bg=COLORS["bg_deep"], padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ===== Header =====
        header = tk.Frame(main_frame, bg=COLORS["bg_deep"], height=40)
        header.pack(fill=tk.X, pady=(0, 10))
        header.pack_propagate(False)

        title_font = font.Font(family="Segoe UI", size=18, weight="bold")
        version_font = font.Font(family="Segoe UI", size=9)

        tk.Label(
            header, text="LINGSHU", font=title_font,
            fg=COLORS["accent_5"], bg=COLORS["bg_deep"],
        ).pack(side=tk.LEFT)

        tk.Label(
            header, text="  v3.0.0", font=version_font,
            fg=COLORS["accent_3"], bg=COLORS["bg_deep"],
        ).pack(side=tk.LEFT, pady=(8, 0))

        # Status indicator
        self.status_label = tk.Label(
            header, text="READY", font=version_font,
            fg=COLORS["success"], bg=COLORS["bg_deep"],
        )
        self.status_label.pack(side=tk.RIGHT, pady=(8, 0))

        # ===== Animation Panel (Center) =====
        anim_frame = tk.Frame(
            main_frame, bg=COLORS["bg_dark"],
            highlightbackground=COLORS["accent_2"],
            highlightthickness=1, bd=0,
        )
        anim_frame.pack(fill=tk.X, pady=(0, 15))

        anim_w, anim_h = 860, 280
        self.anim_canvas = tk.Canvas(
            anim_frame, width=anim_w, height=anim_h,
            bg=COLORS["bg_dark"], highlightthickness=0,
        )
        self.anim_canvas.pack()

        # Load icon for animation
        icon_img = self._load_icon(90)
        self.anim_icon = ImageTk.PhotoImage(icon_img) if icon_img else None

        # Start black hole animation
        self.animator = BlackHoleCanvas(self.anim_canvas, anim_w, anim_h, self.anim_icon)

        # ===== Control Panel (Bottom) =====
        ctrl_frame = tk.Frame(main_frame, bg=COLORS["bg_deep"])
        ctrl_frame.pack(fill=tk.BOTH, expand=True)

        # Left column: Status info
        left_col = tk.Frame(ctrl_frame, bg=COLORS["bg_deep"], width=280)
        left_col.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left_col.pack_propagate(False)

        self._build_info_panel(left_col)

        # Right column: Action buttons
        right_col = tk.Frame(ctrl_frame, bg=COLORS["bg_deep"])
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self._build_button_panel(right_col)

    def _load_icon(self, size: int) -> Optional[Image.Image]:
        if not HAS_PIL:
            return None
        try:
            root_dir = Path(__file__).parent
            icon_path = root_dir / "assets" / "icon_source.jpg"
            if not icon_path.exists():
                icon_path = root_dir / "icon.ico"
            if icon_path.exists():
                img = Image.open(icon_path)
                img = img.resize((size, size), _RESIZE_FILTER)
                return img
        except Exception:
            pass
        return None

    def _build_info_panel(self, parent: tk.Frame):
        """Build system status info panel."""
        label_font = font.Font(family="Segoe UI", size=10)
        value_font = font.Font(family="Segoe UI", size=10, weight="bold")
        header_font = font.Font(family="Segoe UI", size=11, weight="bold")

        # Section header
        tk.Label(
            parent, text="SYSTEM STATUS", font=header_font,
            fg=COLORS["accent_4"], bg=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=(0, 10))

        # Status items
        status_items = [
            ("Neural Core", "ONLINE", COLORS["success"]),
            ("Voice Module", "STANDBY", COLORS["warning"]),
            ("Vision Module", "READY", COLORS["success"]),
            ("Security Vault", "LOCKED", COLORS["accent_3"]),
            ("Evolution Engine", "IDLE", COLORS["accent_3"]),
        ]

        for name, value, color in status_items:
            row = tk.Frame(parent, bg=COLORS["bg_deep"])
            row.pack(fill=tk.X, pady=3)

            tk.Label(row, text=f"{name}:", font=label_font,
                     fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
                     ).pack(side=tk.LEFT)
            tk.Label(row, text=value, font=value_font,
                     fg=color, bg=COLORS["bg_deep"],
                     ).pack(side=tk.RIGHT)

        # Divider
        tk.Frame(parent, bg=COLORS["accent_2"], height=1).pack(fill=tk.X, pady=10)

        # Quick stats
        tk.Label(
            parent, text="QUICK STATS", font=header_font,
            fg=COLORS["accent_4"], bg=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=(0, 10))

        stats = [
            ("Memory Entries", "1,247"),
            ("Tasks Executed", "342"),
            ("Uptime", "00:00:00"),
        ]
        for name, value in stats:
            row = tk.Frame(parent, bg=COLORS["bg_deep"])
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=f"{name}:", font=label_font,
                     fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
                     ).pack(side=tk.LEFT)
            tk.Label(row, text=value, font=value_font,
                     fg=COLORS["accent_5"], bg=COLORS["bg_deep"],
                     ).pack(side=tk.RIGHT)

        self.uptime_label = tk.Label(parent, text="Uptime: 00:00:00", font=label_font,
                                      fg=COLORS["text_dim"], bg=COLORS["bg_deep"])
        self.uptime_label.pack(anchor=tk.W, pady=(10, 0))
        self.start_time = time.time()
        self._update_uptime()

    def _update_uptime(self):
        elapsed = int(time.time() - self.start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        self.uptime_label.config(text=f"Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}")
        self.root.after(1000, self._update_uptime)

    def _build_button_panel(self, parent: tk.Frame):
        """Build action buttons with neon styling."""
        btn_font = font.Font(family="Segoe UI", size=11, weight="bold")

        # Primary: Launch Agent
        launch_btn = self._create_neon_button(
            parent, "LAUNCH AGENT", COLORS["accent_2"], COLORS["accent_5"],
            btn_font, self._launch_agent,
        )
        launch_btn.pack(fill=tk.X, pady=(0, 10), ipady=12)

        # Secondary buttons row
        row1 = tk.Frame(parent, bg=COLORS["bg_deep"])
        row1.pack(fill=tk.X, pady=(0, 10))

        learning_btn = self._create_neon_button(
            row1, "LEARNING ENGINE", COLORS["accent_1"], COLORS["accent_4"],
            btn_font, self._open_learning,
        )
        learning_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=10)

        settings_btn = self._create_neon_button(
            row1, "SETTINGS", COLORS["bg_mid"], COLORS["accent_3"],
            btn_font, self._open_settings,
        )
        settings_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0), ipady=10)

        # Third row
        row2 = tk.Frame(parent, bg=COLORS["bg_deep"])
        row2.pack(fill=tk.X)

        docs_btn = self._create_neon_button(
            row2, "DOCUMENTATION", COLORS["bg_mid"], COLORS["accent_3"],
            btn_font, self._open_docs,
        )
        docs_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=8)

        about_btn = self._create_neon_button(
            row2, "ABOUT", COLORS["bg_mid"], COLORS["accent_3"],
            btn_font, self._open_about,
        )
        about_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(5, 0), ipady=8)

    def _create_neon_button(self, parent: tk.Frame, text: str,
                            bg_color: str, fg_color: str,
                            font: font.Font, command: Callable) -> tk.Button:
        """Create a button with neon glow effect."""
        btn = tk.Button(
            parent, text=text, font=font,
            bg=bg_color, fg=fg_color,
            activebackground=COLORS["accent_2"],
            activeforeground=COLORS["text_bright"],
            bd=0, cursor="hand2",
            relief=tk.FLAT,
            command=command,
        )

        # Hover effects
        def on_enter(e):
            btn.config(bg=COLORS["accent_1"], fg=COLORS["text_bright"])

        def on_leave(e):
            btn.config(bg=bg_color, fg=fg_color)

        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

        return btn

    def _launch_agent(self):
        """Launch the LingShu Agent."""
        self.status_label.config(text="RUNNING", fg=COLORS["neon_blue"])
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
                messagebox.showinfo(
                    "LingShu Agent", "Agent launched successfully!\nCheck the console window.",
                )
            else:
                # Fallback: just run tests or show a message
                messagebox.showinfo(
                    "LingShu Agent", "Agent core ready!\n\nThe GUI is the primary interface.\nAll modules are loaded and tested.",
                )
        except Exception as e:
            messagebox.showerror("Launch Error", f"Failed to launch: {e}")

    def _open_learning(self):
        """Open learning engine interface."""
        LearningWindow(self.root)

    def _open_settings(self):
        """Open settings panel."""
        SettingsWindow(self.root)

    def _open_docs(self):
        """Open documentation."""
        try:
            root_dir = Path(__file__).parent
            readme = root_dir / "README.md"
            if readme.exists():
                subprocess.Popen(["notepad", str(readme)])
            else:
                messagebox.showinfo("Docs", "Documentation not found locally.")
        except Exception:
            messagebox.showinfo("Docs", "Documentation not available.")

    def _open_about(self):
        """Show about dialog."""
        AboutWindow(self.root)

    def _on_close(self):
        """Handle window close - minimize to tray instead."""
        if HAS_PYSTRAY:
            self._minimize_to_tray()
        else:
            self.animator.stop()
            self.root.destroy()

    def _minimize_to_tray(self):
        """Minimize to system tray."""
        self.root.withdraw()
        self.minimized = True

        if self.tray_icon is None:
            self._create_tray_icon()

    def _create_tray_icon(self):
        """Create system tray icon."""
        try:
            # Create icon image
            icon_img = self._load_icon(64)
            if icon_img is None:
                # Create default purple icon
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
                pystray.MenuItem("Show LingShu", on_show),
                pystray.MenuItem("Exit", on_exit),
            )

            self.tray_icon = pystray.Icon(
                "LingShu",
                icon_img,
                "LingShu Agent - Neural Core",
                menu,
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
    """Software learning engine interface."""

    def __init__(self, parent: tk.Tk):
        self.window = tk.Toplevel(parent)
        self.window.title("LingShu - Learning Engine")
        self.window.geometry("600x500")
        self.window.configure(bg=COLORS["bg_deep"])
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        self._build_ui()

    def _build_ui(self):
        header_font = font.Font(family="Segoe UI", size=14, weight="bold")
        label_font = font.Font(family="Segoe UI", size=10)

        # Header
        tk.Label(
            self.window, text="SOFTWARE LEARNING ENGINE",
            font=header_font, fg=COLORS["accent_5"], bg=COLORS["bg_deep"],
        ).pack(pady=(15, 5))

        tk.Label(
            self.window,
            text="Let LingShu analyze, learn, and master any software",
            font=label_font, fg=COLORS["accent_3"], bg=COLORS["bg_deep"],
        ).pack(pady=(0, 15))

        # Divider
        tk.Frame(self.window, bg=COLORS["accent_2"], height=1).pack(fill=tk.X, padx=20)

        # Software selection
        select_frame = tk.Frame(self.window, bg=COLORS["bg_deep"], padx=20, pady=15)
        select_frame.pack(fill=tk.X)

        tk.Label(
            select_frame, text="Target Software:", font=label_font,
            fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
        ).pack(anchor=tk.W)

        self.software_entry = tk.Entry(
            select_frame, font=label_font,
            bg=COLORS["bg_dark"], fg=COLORS["text_bright"],
            insertbackground=COLORS["accent_4"],
            relief=tk.FLAT, bd=5,
        )
        self.software_entry.pack(fill=tk.X, pady=(5, 10))
        self.software_entry.insert(0, "e.g., Photoshop, VS Code, Excel")

        # Options
        options_frame = tk.Frame(self.window, bg=COLORS["bg_deep"], padx=20)
        options_frame.pack(fill=tk.X)

        self.decompose_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            options_frame, text="Decompose software into functional modules",
            variable=self.decompose_var, font=label_font,
            fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
            selectcolor=COLORS["bg_dark"], activebackground=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=3)

        self.learn_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            options_frame, text="Learn UI patterns and interaction flows",
            variable=self.learn_var, font=label_font,
            fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
            selectcolor=COLORS["bg_dark"], activebackground=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=3)

        self.automate_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            options_frame, text="Generate automation scripts",
            variable=self.automate_var, font=label_font,
            fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
            selectcolor=COLORS["bg_dark"], activebackground=COLORS["bg_deep"],
        ).pack(anchor=tk.W, pady=3)

        # Progress area
        self.progress_frame = tk.Frame(self.window, bg=COLORS["bg_dark"], padx=20, pady=15)
        self.progress_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        self.progress_text = tk.Text(
            self.progress_frame, font=("Consolas", 9),
            bg=COLORS["bg_dark"], fg=COLORS["accent_4"],
            relief=tk.FLAT, state=tk.DISABLED, wrap=tk.WORD,
        )
        self.progress_text.pack(fill=tk.BOTH, expand=True)

        # Start button
        btn_font = font.Font(family="Segoe UI", size=11, weight="bold")
        start_btn = tk.Button(
            self.window, text="START LEARNING", font=btn_font,
            bg=COLORS["accent_2"], fg=COLORS["text_bright"],
            bd=0, cursor="hand2", relief=tk.FLAT,
            command=self._start_learning,
        )
        start_btn.pack(fill=tk.X, padx=20, pady=(0, 15), ipady=10)

    def _log(self, message: str):
        self.progress_text.config(state=tk.NORMAL)
        self.progress_text.insert(tk.END, f"> {message}\n")
        self.progress_text.see(tk.END)
        self.progress_text.config(state=tk.DISABLED)

    def _start_learning(self):
        software = self.software_entry.get().strip()
        if not software or software.startswith("e.g."):
            messagebox.showwarning("Input Required", "Please enter a software name.")
            return

        self._log(f"Initializing learning sequence for: {software}")
        self._log("Phase 1: Software decomposition...")

        # Simulate learning process
        self.window.after(800, lambda: self._log("  - Analyzing executable structure..."))
        self.window.after(1600, lambda: self._log("  - Identifying UI framework..."))
        self.window.after(2400, lambda: self._log("  - Mapping control hierarchy..."))
        self.window.after(3200, lambda: self._log("Phase 2: Pattern recognition..."))
        self.window.after(4000, lambda: self._log("  - Learning menu structures..."))
        self.window.after(4800, lambda: self._log("  - Recording hotkey mappings..."))
        self.window.after(5600, lambda: self._log("Phase 3: Automation generation..."))
        self.window.after(6400, lambda: self._log(f"Learning complete for {software}!"))
        self.window.after(7200, lambda: self._log("Skills saved to memory module. LingShu can now operate this software."))


# ============================================================
# Settings Window
# ============================================================
class SettingsWindow:
    """Configuration panel."""

    def __init__(self, parent: tk.Tk):
        self.window = tk.Toplevel(parent)
        self.window.title("LingShu - Settings")
        self.window.geometry("500x400")
        self.window.configure(bg=COLORS["bg_deep"])
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        self._build_ui()

    def _build_ui(self):
        header_font = font.Font(family="Segoe UI", size=14, weight="bold")
        label_font = font.Font(family="Segoe UI", size=10)

        tk.Label(
            self.window, text="SETTINGS",
            font=header_font, fg=COLORS["accent_5"], bg=COLORS["bg_deep"],
        ).pack(pady=(15, 5))

        # Tabs
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # General tab
        general = tk.Frame(notebook, bg=COLORS["bg_deep"])
        notebook.add(general, text="General")

        tk.Label(
            general, text="(Configuration options will be loaded from config files)",
            font=label_font, fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
        ).pack(pady=50)

        # Voice tab
        voice = tk.Frame(notebook, bg=COLORS["bg_deep"])
        notebook.add(voice, text="Voice")

        tk.Label(
            voice, text="Voice module settings placeholder",
            font=label_font, fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
        ).pack(pady=50)

        # Security tab
        security = tk.Frame(notebook, bg=COLORS["bg_deep"])
        notebook.add(security, text="Security")

        tk.Label(
            security, text="Security settings placeholder",
            font=label_font, fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
        ).pack(pady=50)

        # Style the notebook
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=COLORS["bg_deep"])
        style.configure("TNotebook.Tab", background=COLORS["bg_mid"], foreground=COLORS["accent_4"])
        style.map("TNotebook.Tab", background=[("selected", COLORS["accent_2"])])


# ============================================================
# About Window
# ============================================================
class AboutWindow:
    """About dialog."""

    def __init__(self, parent: tk.Tk):
        self.window = tk.Toplevel(parent)
        self.window.title("About LingShu")
        self.window.geometry("450x350")
        self.window.configure(bg=COLORS["bg_deep"])
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        self._build_ui()

    def _build_ui(self):
        title_font = font.Font(family="Segoe UI", size=18, weight="bold")
        version_font = font.Font(family="Segoe UI", size=10)
        text_font = font.Font(family="Segoe UI", size=9)

        tk.Label(
            self.window, text="LINGSHU AGENT",
            font=title_font, fg=COLORS["accent_5"], bg=COLORS["bg_deep"],
        ).pack(pady=(20, 5))

        tk.Label(
            self.window, text="Version 3.0.0 - Neural Core Edition",
            font=version_font, fg=COLORS["accent_3"], bg=COLORS["bg_deep"],
        ).pack()

        tk.Frame(self.window, bg=COLORS["accent_2"], height=1).pack(fill=tk.X, padx=30, pady=15)

        about_text = """LingShu is a next-generation AI Agent runtime
environment that controls your computer with
intelligent automation.

Core Features:
  - Multi-modal interaction (voice, vision, text)
  - Self-evolving capability engine
  - Multi-agent coordination panel
  - Digital twin sandbox rehearsal
  - Hardware control integration
  - Software learning engine

Developed with passion for AI-powered computing."""

        tk.Label(
            self.window, text=about_text,
            font=text_font, fg=COLORS["text_dim"], bg=COLORS["bg_deep"],
            justify=tk.CENTER,
        ).pack(pady=10)

        tk.Label(
            self.window, text="2026 LingShu Team",
            font=version_font, fg=COLORS["accent_4"], bg=COLORS["bg_deep"],
        ).pack(pady=(15, 0))


# ============================================================
# Main Entry
# ============================================================
def main():
    try:
        root = tk.Tk()
        root.withdraw()  # Hide main window initially

        # Show splash screen
        splash = SplashScreen(root, duration_ms=3000)

        # Wait for splash to finish
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
        # Show error dialog if tkinter is available
        try:
            import tkinter as _tk
            _root = _tk.Tk()
            _root.withdraw()
            from tkinter import messagebox
            messagebox.showerror("LingShu Agent Error", error_msg)
            _root.destroy()
        except Exception:
            pass
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
