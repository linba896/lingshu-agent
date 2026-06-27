#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════
  软件学习引擎 — Software Learner Module (v1.0)
  功能：
    1. 分析软件目录结构，分解文件组成
    2. 录制用户操作（鼠标/键盘）生成操作序列
    3. 自主学习软件界面状态
    4. 权限管理（授予/撤销自动操作权限）
═══════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import time
import pathlib
import hashlib
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class SoftwareLearner:
    """软件自主学习引擎"""

    LEARN_DIR = "learned_software"
    STATE_FILE = "learned_software.json"

    def __init__(self, root_dir: pathlib.Path):
        self.root = root_dir
        self.learn_dir = root_dir / self.LEARN_DIR
        self.learn_dir.mkdir(exist_ok=True)
        self.state_file = self.learn_dir / self.STATE_FILE
        self.state = self._load_state()
        self.recording = False
        self.recorded_events: List[Dict] = []
        self._record_thread: Optional[threading.Thread] = None

    # ── 状态管理 ──
    def _load_state(self) -> Dict[str, Any]:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"software": []}

    def _save_state(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    # ── 软件目录分析 ──
    def add_software(self, path: str) -> str:
        """添加一个软件（目录或 .exe）到学习引擎"""
        p = pathlib.Path(path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"路径不存在: {path}")

        software_id = hashlib.md5(str(p).encode("utf-8")).hexdigest()[:12]
        name = p.stem if p.is_file() else p.name

        # 1. 分析目录结构
        structure = self._analyze_structure(p)

        # 2. 识别文件类型
        file_types = self._identify_file_types(p)

        entry = {
            "id": software_id,
            "name": name,
            "path": str(p),
            "added_at": datetime.now().isoformat(),
            "structure": structure,
            "file_types": file_types,
            "operations": [],
            "authorized": False,
            "learned": False,
            "icon_path": None,
        }

        # 检查是否已存在
        for i, sw in enumerate(self.state["software"]):
            if sw["id"] == software_id:
                self.state["software"][i] = entry
                break
        else:
            self.state["software"].append(entry)

        self._save_state()
        return name

    def _analyze_structure(self, path: pathlib.Path, max_depth: int = 4) -> Dict:
        """递归分析目录结构"""
        result = {
            "type": "file" if path.is_file() else "directory",
            "name": path.name,
            "size": path.stat().st_size if path.is_file() else None,
        }
        if path.is_dir() and max_depth > 0:
            children = []
            try:
                for item in sorted(path.iterdir(), key=lambda x: x.name)[:50]:
                    children.append(self._analyze_structure(item, max_depth - 1))
            except PermissionError:
                pass
            result["children"] = children
        return result

    def _identify_file_types(self, path: pathlib.Path) -> Dict[str, int]:
        """统计文件类型分布"""
        ext_counts = {}
        if path.is_file():
            ext = path.suffix.lower()
            ext_counts[ext or "(no_ext)"] = 1
            return ext_counts

        for root, _, files in os.walk(path):
            for f in files:
                ext = pathlib.Path(f).suffix.lower()
                ext_counts[ext or "(no_ext)"] = ext_counts.get(ext or "(no_ext)", 0) + 1
            if len(ext_counts) > 100:
                break  # 防止过大
        return dict(sorted(ext_counts.items(), key=lambda x: -x[1])[:20])

    # ── 操作录制 ──
    def start_recording(self):
        """开始录制用户操作"""
        self.recording = True
        self.recorded_events = []
        self._record_thread = threading.Thread(target=self._record_loop, daemon=True)
        self._record_thread.start()

    def stop_recording(self) -> List[Dict]:
        """停止录制并返回操作序列"""
        self.recording = False
        if self._record_thread:
            self._record_thread.join(timeout=5)
        return self.recorded_events

    def _record_loop(self):
        """后台录制循环（基于 pyautogui + pynput 模拟）"""
        try:
            import pyautogui
            from pynput import mouse, keyboard

            last_pos = pyautogui.position()
            last_time = time.time()

            def on_click(x, y, button, pressed):
                if not self.recording:
                    return False
                self.recorded_events.append({
                    "type": "mouse_click",
                    "x": x, "y": y,
                    "button": str(button),
                    "pressed": pressed,
                    "timestamp": time.time(),
                })
                return True

            def on_press(key):
                if not self.recording:
                    return False
                try:
                    char = key.char
                except AttributeError:
                    char = str(key)
                self.recorded_events.append({
                    "type": "key_press",
                    "key": char,
                    "timestamp": time.time(),
                })
                return True

            # 启动监听器
            mouse_listener = mouse.Listener(on_click=on_click)
            keyboard_listener = keyboard.Listener(on_press=on_press)
            mouse_listener.start()
            keyboard_listener.start()

            while self.recording:
                time.sleep(0.1)

            mouse_listener.stop()
            keyboard_listener.stop()

        except ImportError:
            # 如果没有 pynput，用轮询方式模拟
            self._record_fallback_loop()

    def _record_fallback_loop(self):
        """降级录制方式（纯轮询）"""
        try:
            import pyautogui
        except ImportError:
            return

        last_pos = pyautogui.position()
        while self.recording:
            time.sleep(0.5)
            pos = pyautogui.position()
            if pos != last_pos:
                self.recorded_events.append({
                    "type": "mouse_move",
                    "x": pos.x, "y": pos.y,
                    "timestamp": time.time(),
                })
                last_pos = pos

    # ── 自主学习（模拟）──
    def learn_from_events(self, software_id: str, events: List[Dict]):
        """从录制的操作中学习，生成操作脚本"""
        # 简化：将事件序列保存为操作脚本
        script_path = self.learn_dir / f"{software_id}_script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)

        for sw in self.state["software"]:
            if sw["id"] == software_id:
                sw["learned"] = True
                sw["operations_count"] = len(events)
                sw["learned_at"] = datetime.now().isoformat()
                break
        self._save_state()

    # ── 权限管理 ──
    def grant_permission(self, software_id: Optional[str] = None):
        """授予自动操作权限"""
        if software_id:
            for sw in self.state["software"]:
                if sw["id"] == software_id:
                    sw["authorized"] = True
                    break
        else:
            # 授予最后一个未授权的
            for sw in reversed(self.state["software"]):
                if not sw["authorized"]:
                    sw["authorized"] = True
                    break
        self._save_state()

    def revoke_permission(self, software_id: str):
        """撤销自动操作权限"""
        for sw in self.state["software"]:
            if sw["id"] == software_id:
                sw["authorized"] = False
                break
        self._save_state()

    def list_learned_software(self) -> List[Dict]:
        """列出已学习的软件"""
        return self.state.get("software", [])

    def get_software(self, software_id: str) -> Optional[Dict]:
        """获取单个软件详情"""
        for sw in self.state["software"]:
            if sw["id"] == software_id:
                return sw
        return None

    # ── 执行已学习的操作（需要权限）──
    def execute_operations(self, software_id: str):
        """执行已学习的操作序列（需已授权）"""
        sw = self.get_software(software_id)
        if not sw:
            raise ValueError(f"未找到软件: {software_id}")
        if not sw["authorized"]:
            raise PermissionError(f"软件未授权自动操作: {sw['name']}")

        script_path = self.learn_dir / f"{software_id}_script.json"
        if not script_path.exists():
            raise FileNotFoundError("尚未学习该软件的操作")

        with open(script_path, "r", encoding="utf-8") as f:
            events = json.load(f)

        # 执行操作序列
        import pyautogui
        for event in events:
            if event["type"] == "mouse_click":
                pyautogui.click(event["x"], event["y"])
            elif event["type"] == "mouse_move":
                pyautogui.moveTo(event["x"], event["y"])
            elif event["type"] == "key_press":
                pyautogui.press(event["key"])
            time.sleep(0.3)

        return True


# ── CLI 测试 ──
if __name__ == "__main__":
    learner = SoftwareLearner(pathlib.Path("."))
    print("软件学习引擎 v1.0")
    print("用法：")
    print("  from software_learner import SoftwareLearner")
    print("  learner = SoftwareLearner(root_path)")
    print("  learner.add_software('/path/to/software')")
    print("  learner.start_recording()")
    print("  # ...用户操作...")
    print("  events = learner.stop_recording()")
    print("  learner.learn_from_events('id', events)")
    print("  learner.grant_permission('id')")
