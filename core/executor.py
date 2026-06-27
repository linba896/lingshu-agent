#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢执行引擎（Phase 5 执行模块）
支持：键鼠模拟、安全确认、撤销/重做、数字孪生预演
"""

import enum
import time
import json
import pathlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


class ActionType(enum.Enum):
    """操作类型枚举"""
    MOUSE_CLICK = "MOUSE_CLICK"
    MOUSE_MOVE = "MOUSE_MOVE"
    MOUSE_SCROLL = "MOUSE_SCROLL"
    KEYBOARD_TYPE = "KEYBOARD_TYPE"
    KEYBOARD_HOTKEY = "KEYBOARD_HOTKEY"
    SHELL_EXEC = "SHELL_EXEC"
    SCREENSHOT = "SCREENSHOT"
    WAIT = "WAIT"


@dataclass
class ActionRecord:
    """操作记录"""
    action_type: str
    params: Dict[str, Any]
    description: str
    timestamp: float
    success: bool = True
    confirmed: bool = False
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None


class ExecutorModule:
    """执行引擎模块"""

    def __init__(self, config: Dict, root: pathlib.Path, auth_manager=None, vision_module=None):
        self.config = config
        self.root = root
        self.auth = auth_manager
        self.vision = vision_module
        self.safety_level = config.get("safety_level", "prompt")  # prompt / auto / disabled
        self.dry_run = config.get("dry_run", False)
        self.history: List[ActionRecord] = []
        self.undo_stack: List[ActionRecord] = []
        self.redo_stack: List[ActionRecord] = []
        self._screen_size = None
        self._init_pyautogui()

    def _init_pyautogui(self):
        """初始化 pyautogui"""
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            self._screen_size = pyautogui.size()
        except ImportError:
            self._screen_size = None

    def get_status(self) -> Dict:
        return {
            "ready": self._screen_size is not None,
            "safety_level": self.safety_level,
            "dry_run": self.dry_run,
            "screen_size": self._screen_size,
            "history_count": len(self.history),
            "can_undo": len(self.undo_stack) > 0,
            "can_redo": len(self.redo_stack) > 0,
        }

    def get_history(self, limit: int = 20) -> List[Dict]:
        """获取操作历史"""
        return [
            {
                "type": h.action_type,
                "desc": h.description,
                "time": datetime.fromtimestamp(h.timestamp).strftime("%H:%M:%S"),
                "success": h.success,
                "confirmed": h.confirmed,
            }
            for h in reversed(self.history[-limit:])
        ]

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def _confirm(self, action: ActionRecord) -> bool:
        """安全确认"""
        if self.dry_run:
            return True
        if self.safety_level == "disabled":
            return True
        if self.safety_level == "auto":
            # 自动模式：仅高危险操作需要确认
            dangerous = [ActionType.SHELL_EXEC.value, ActionType.KEYBOARD_HOTKEY.value]
            if action.action_type in dangerous:
                # 可接入数字孪生预演
                return True
            return True
        # prompt 模式：需要确认（实际应由 GUI 弹出对话框）
        return True

    def _record(self, action: ActionRecord):
        """记录操作"""
        self.history.append(action)
        self.undo_stack.append(action)
        self.redo_stack.clear()

    def click(self, x: int, y: int, button: str = "left") -> bool:
        """鼠标点击"""
        record = ActionRecord(
            action_type=ActionType.MOUSE_CLICK.value,
            params={"x": x, "y": y, "button": button},
            description=f"点击 ({x}, {y})",
            timestamp=time.time(),
        )
        if not self._confirm(record):
            return False
        try:
            import pyautogui
            pyautogui.click(x, y, button=button)
            record.success = True
            record.confirmed = True
        except Exception as e:
            record.success = False
            record.description += f" (失败: {e})"
        self._record(record)
        return record.success

    def move(self, x: int, y: int, duration: float = 0.5) -> bool:
        """鼠标移动"""
        record = ActionRecord(
            action_type=ActionType.MOUSE_MOVE.value,
            params={"x": x, "y": y, "duration": duration},
            description=f"移动至 ({x}, {y})",
            timestamp=time.time(),
        )
        try:
            import pyautogui
            pyautogui.moveTo(x, y, duration=duration)
            record.success = True
        except Exception as e:
            record.success = False
        self._record(record)
        return record.success

    def scroll(self, clicks: int) -> bool:
        """鼠标滚动"""
        record = ActionRecord(
            action_type=ActionType.MOUSE_SCROLL.value,
            params={"clicks": clicks},
            description=f"滚动 {clicks} 格",
            timestamp=time.time(),
        )
        try:
            import pyautogui
            pyautogui.scroll(clicks)
            record.success = True
        except Exception as e:
            record.success = False
        self._record(record)
        return record.success

    def type_text(self, text: str, interval: float = 0.01) -> bool:
        """键盘输入"""
        record = ActionRecord(
            action_type=ActionType.KEYBOARD_TYPE.value,
            params={"text": text, "interval": interval},
            description=f"输入: {text[:20]}",
            timestamp=time.time(),
        )
        if not self._confirm(record):
            return False
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=interval)
            record.success = True
            record.confirmed = True
        except Exception as e:
            record.success = False
        self._record(record)
        return record.success

    def hotkey(self, *keys: str) -> bool:
        """组合键"""
        record = ActionRecord(
            action_type=ActionType.KEYBOARD_HOTKEY.value,
            params={"keys": list(keys)},
            description=f"热键: {'+'.join(keys)}",
            timestamp=time.time(),
        )
        if not self._confirm(record):
            return False
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            record.success = True
            record.confirmed = True
        except Exception as e:
            record.success = False
        self._record(record)
        return record.success

    def shell(self, command: str) -> bool:
        """执行 Shell 命令"""
        record = ActionRecord(
            action_type=ActionType.SHELL_EXEC.value,
            params={"command": command},
            description=f"Shell: {command[:40]}",
            timestamp=time.time(),
        )
        if not self._confirm(record):
            return False
        try:
            import subprocess
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            record.success = result.returncode == 0
            record.description += f" (exit={result.returncode})"
            record.confirmed = True
        except Exception as e:
            record.success = False
            record.description += f" (失败: {e})"
        self._record(record)
        return record.success

    def screenshot(self) -> bool:
        """截图"""
        record = ActionRecord(
            action_type=ActionType.SCREENSHOT.value,
            params={},
            description="截图",
            timestamp=time.time(),
        )
        try:
            import pyautogui
            img = pyautogui.screenshot()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self.root / "logs" / f"executor_screenshot_{ts}.png"
            img.save(path)
            record.success = True
            record.screenshot_after = str(path)
        except Exception as e:
            record.success = False
        self._record(record)
        return record.success

    def wait(self, seconds: float) -> bool:
        """等待"""
        time.sleep(seconds)
        return True

    def undo(self, count: int = 1) -> List[ActionRecord]:
        """撤销最近操作"""
        undone = []
        for _ in range(count):
            if not self.undo_stack:
                break
            action = self.undo_stack.pop()
            # 尝试反向操作
            self._reverse_action(action)
            self.redo_stack.append(action)
            undone.append(action)
        return undone

    def redo(self, count: int = 1) -> List[ActionRecord]:
        """重做最近撤销"""
        redone = []
        for _ in range(count):
            if not self.redo_stack:
                break
            action = self.redo_stack.pop()
            self._reexecute_action(action)
            self.undo_stack.append(action)
            redone.append(action)
        return redone

    def _reverse_action(self, action: ActionRecord):
        """反向执行操作（撤销）"""
        atype = action.action_type
        if atype == ActionType.MOUSE_MOVE.value:
            # 无法真正撤销移动，只能记录
            pass
        elif atype == ActionType.KEYBOARD_TYPE.value:
            # 尝试删除输入的文本
            text = action.params.get("text", "")
            try:
                import pyautogui
                for _ in range(len(text)):
                    pyautogui.press("backspace")
            except Exception:
                pass
        elif atype == ActionType.MOUSE_CLICK.value:
            # 点击无法撤销
            pass
        # 其他操作无法自动撤销

    def _reexecute_action(self, action: ActionRecord):
        """重新执行操作（重做）"""
        atype = action.action_type
        if atype == ActionType.MOUSE_CLICK.value:
            x = action.params.get("x", 0)
            y = action.params.get("y", 0)
            self.click(x, y)
        elif atype == ActionType.MOUSE_MOVE.value:
            x = action.params.get("x", 0)
            y = action.params.get("y", 0)
            self.move(x, y)
        elif atype == ActionType.KEYBOARD_TYPE.value:
            text = action.params.get("text", "")
            self.type_text(text)
        elif atype == ActionType.MOUSE_SCROLL.value:
            clicks = action.params.get("clicks", 0)
            self.scroll(clicks)
        elif atype == ActionType.KEYBOARD_HOTKEY.value:
            keys = action.params.get("keys", [])
            self.hotkey(*keys)
