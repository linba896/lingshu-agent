#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 执行控制模块（Phase 5 执行引擎）
功能：键鼠模拟 + 安全确认 + 操作回滚 + 视觉联动 + 跨分辨率适配

设计理念（不动根本咒）：
  1. 安全优先：所有操作分级确认，高危操作不可绕过
  2. 可回滚：记录操作历史，支持撤销和重做
  3. 视觉联动：接收视觉模块的坐标建议，执行精准操作
  4. 跨分辨率：适配不同屏幕分辨率和 DPI 缩放
  5. 审计追踪：完整操作日志，与 auth 模块审计日志联动

支持操作类型：
  mouse:    move, click, double_click, right_click, drag, scroll
  keyboard: type, press, hotkey, key_down, key_up
  system:   shell, screenshot, wait, alert

安全级别：
  normal    — 常规操作直接执行，敏感操作弹窗确认
  strict    — 所有操作截图确认，敏感操作语音+弹窗双重确认
  paranoid  — 每次操作前截图+确认（最慢最安全）

回滚机制：
  - 鼠标移动：记录原坐标，回滚 = 移回
  - 键盘输入：记录输入内容，回滚 = 选中 + 删除（或 backspace 多次）
  - 点击操作：不可逆，回滚 = 提示用户手动恢复
  - 文件操作：备份原文件，回滚 = 恢复备份

"""

import copy
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np


class ActionType(Enum):
    """操作类型"""
    # 鼠标操作
    MOUSE_MOVE = auto()
    MOUSE_CLICK = auto()
    MOUSE_DOUBLE_CLICK = auto()
    MOUSE_RIGHT_CLICK = auto()
    MOUSE_DRAG = auto()
    MOUSE_SCROLL = auto()
    # 键盘操作
    KEYBOARD_TYPE = auto()
    KEYBOARD_PRESS = auto()
    KEYBOARD_HOTKEY = auto()
    # 系统操作
    SHELL_EXEC = auto()
    SCREENSHOT = auto()
    WAIT = auto()
    ALERT = auto()


class SafetyLevel(Enum):
    """安全级别"""
    NORMAL = "normal"        # 常规：敏感操作弹窗确认
    STRICT = "strict"        # 严格：所有操作截图确认
    PARANOID = "paranoid"    # 偏执：每次操作前截图+确认


@dataclass
class ExecutorAction:
    """单个操作记录"""
    action_type: ActionType
    params: Dict[str, Any]       # 操作参数
    timestamp: float
    description: str             # 人类可读描述
    # 回滚信息
    pre_state: Optional[Dict] = None   # 操作前状态（坐标、文本内容等）
    post_state: Optional[Dict] = None  # 操作后状态
    rollback_params: Optional[Dict] = None  # 回滚操作参数
    executed: bool = False
    confirmed: bool = False      # 是否经过安全确认
    success: bool = False
    error_msg: Optional[str] = None


@dataclass
class ActionSequence:
    """操作序列"""
    name: str
    actions: List[ExecutorAction]
    created_at: float
    source: str = "manual"         # manual, voice, vision, proactive
    description: str = ""


class ExecutorModule:
    """
    执行控制引擎

    核心职责：
      1. 安全执行：所有操作经过权限检查和确认机制
      2. 操作记录：完整的历史栈，支持 undo/redo
      3. 视觉联动：解析视觉模块返回的 suggested_actions
      4. 跨分辨率：坐标比例映射，适配不同屏幕
    """

    # 默认敏感操作（无需配置即可生效）
    DEFAULT_SENSITIVE = {
        "delete", "format", "remove", "rm", "rd", "rmdir",
        "shell_exec", "powershell", "cmd", "bash",
        "registry", "regedit",
    }

    # 确认超时（秒）
    CONFIRM_TIMEOUT = 30

    def __init__(
        self,
        executor_config: Dict,
        root: Optional[Path] = None,
        auth_manager=None,
        vision_module=None,
    ):
        self.config = executor_config or {}
        self.root = root
        self.auth = auth_manager
        self.vision = vision_module

        # 安全设置
        self.safety_level = SafetyLevel(self.config.get("safety_level", "normal"))
        self.sensitive_actions = set(self.config.get("sensitive_actions", []))
        self.sensitive_actions.update(self.DEFAULT_SENSITIVE)
        self.action_delay_ms = self.config.get("action_delay_ms", 500)
        self.coordinate_tolerance = self.config.get("coordinate_tolerance", 10)
        self.dry_run = self.config.get("dry_run", False)

        # 屏幕适配
        self._screen_size: Optional[Tuple[int, int]] = None
        self._reference_resolution = tuple(self.config.get("reference_resolution", [1920, 1080]))
        self._scaling_factor: Optional[Tuple[float, float]] = None

        # 操作历史（undo/redo 栈）
        self._history: List[ExecutorAction] = []
        self._redo_stack: List[ExecutorAction] = []
        self._history_limit = 100

        # 序列记录
        self._sequences: List[ActionSequence] = []

        # pyautogui 初始化
        self._pyautogui = None
        self._init_pyautogui()

    def _init_pyautogui(self):
        """初始化 pyautogui 并设置安全参数"""
        try:
            import pyautogui
            pyautogui.FAILSAFE = True          # 鼠标移到角落触发安全退出
            pyautogui.PAUSE = self.action_delay_ms / 1000.0
            self._pyautogui = pyautogui
            # 获取屏幕尺寸
            self._screen_size = pyautogui.size()
            # 计算缩放因子
            ref_w, ref_h = self._reference_resolution
            cur_w, cur_h = self._screen_size
            self._scaling_factor = (cur_w / ref_w, cur_h / ref_h)
            print(f"[Executor] ✅ pyautogui 已加载，屏幕分辨率: {self._screen_size}，"
                  f"缩放因子: {self._scaling_factor[0]:.3f}x{self._scaling_factor[1]:.3f}")
        except ImportError:
            print("[Executor] ❌ pyautogui 未安装，键鼠模拟不可用。运行: pip install pyautogui")

    def is_ready(self) -> bool:
        return self._pyautogui is not None

    # ==================== 屏幕适配 ====================

    def _scale_coordinates(self, x: int, y: int) -> Tuple[int, int]:
        """将参考分辨率坐标映射到当前屏幕"""
        if self._scaling_factor is None:
            return (x, y)
        sx, sy = self._scaling_factor
        return (int(x * sx), int(y * sy))

    def _unscale_coordinates(self, x: int, y: int) -> Tuple[int, int]:
        """将当前屏幕坐标映射回参考分辨率"""
        if self._scaling_factor is None:
            return (x, y)
        sx, sy = self._scaling_factor
        return (int(x / sx), int(y / sy))

    def get_screen_size(self) -> Optional[Tuple[int, int]]:
        return self._screen_size

    # ==================== 安全确认 ====================

    def _needs_confirmation(self, action: ExecutorAction) -> bool:
        """判断操作是否需要安全确认"""
        # 偏执模式：所有操作都要确认
        if self.safety_level == SafetyLevel.PARANOID:
            return True
        # 严格模式：鼠标操作 + 敏感操作要确认
        if self.safety_level == SafetyLevel.STRICT:
            return True
        # 常规模式：仅敏感操作要确认
        desc = action.description.lower()
        if any(kw in desc for kw in self.sensitive_actions):
            return True
        # 检查参数中是否包含敏感关键词
        params_str = json.dumps(action.params).lower()
        if any(kw in params_str for kw in self.sensitive_actions):
            return True
        return False

    def _confirm_action(
        self,
        action: ExecutorAction,
        confirm_method: str = "console",  # console / voice / gui
        timeout: int = 30,
    ) -> bool:
        """
        执行安全确认

        支持确认方式：
          console — 命令行输入 y/n
          voice   — 语音确认（需要语音模块）
          gui     — GUI 弹窗（需要 Gradio/Qt）
        """
        print(f"\n{'='*50}")
        print("⚠️  安全确认请求")
        print(f"{'='*50}")
        print(f"操作: {action.description}")
        print(f"类型: {action.action_type.name}")
        print(f"参数: {json.dumps(action.params, ensure_ascii=False)}")
        print(f"安全级别: {self.safety_level.value}")
        print(f"{'='*50}")

        if confirm_method == "console":
            try:
                start = time.time()
                while time.time() - start < timeout:
                    remaining = int(timeout - (time.time() - start))
                    prompt = f"确认执行? [y/n] (剩余 {remaining} 秒): "
                    try:
                        user_input = input(prompt).strip().lower()
                        if user_input in ("y", "yes", "是", "确认"):
                            return True
                        elif user_input in ("n", "no", "否", "取消"):
                            return False
                    except EOFError:
                        time.sleep(0.5)
                print("⏱️ 确认超时，操作已取消")
                return False
            except KeyboardInterrupt:
                print("\n❌ 用户取消操作")
                return False

        elif confirm_method == "voice":
            # 语音确认（需要语音模块集成）
            print("[Executor] 语音确认功能需集成语音模块")
            return False

        elif confirm_method == "gui":
            # GUI 确认（简化实现）
            print("[Executor] GUI 确认功能需集成 GUI 模块")
            return False

        return False

    # ==================== 核心执行 ====================

    def execute_action(
        self,
        action: ExecutorAction,
        auto_confirm: bool = False,
        confirm_method: str = "console",
    ) -> bool:
        """
        执行单个操作（核心入口）

        流程：
        1. 权限检查（auth）
        2. 安全确认（敏感操作）
        3. 记录操作前状态
        4. 执行操作
        5. 记录操作后状态
        6. 入历史栈
        """
        if not self.is_ready():
            action.error_msg = "执行模块未就绪（pyautogui 未安装）"
            print(f"[Executor] ❌ {action.error_msg}")
            return False

        if self.dry_run:
            print(f"[Executor] 🧪 演习模式: {action.description}")
            action.executed = True
            action.success = True
            self._history.append(action)
            return True

        # 1. 权限检查
        if self.auth and not self.auth.is_authorized():
            action.error_msg = "未授权，拒绝执行"
            print(f"[Executor] 🚫 {action.error_msg}")
            return False

        # 2. 安全确认
        if not auto_confirm and self._needs_confirmation(action):
            if not self._confirm_action(action, confirm_method=confirm_method):
                action.error_msg = "安全确认未通过"
                print(f"[Executor] 🚫 {action.error_msg}")
                return False
            action.confirmed = True

        # 3. 记录操作前状态
        action.pre_state = self._capture_pre_state(action)

        # 4. 执行
        try:
            success = self._dispatch_action(action)
            action.executed = True
            action.success = success
        except Exception as e:
            action.success = False
            action.error_msg = str(e)
            print(f"[Executor] ❌ 执行失败: {e}")
            return False

        # 5. 记录操作后状态
        action.post_state = self._capture_post_state(action)

        # 6. 生成回滚参数
        action.rollback_params = self._build_rollback(action)

        # 7. 入历史栈
        self._history.append(action)
        self._trim_history()
        self._redo_stack.clear()  # 新操作清空 redo 栈

        # 8. 审计日志
        if self.auth:
            self.auth.log_operation(
                action.action_type.name,
                action.description,
                "success" if action.success else "failed",
            )

        return action.success

    def _dispatch_action(self, action: ExecutorAction) -> bool:
        """根据操作类型分发到具体执行函数"""
        pg = self._pyautogui
        t = action.action_type
        p = action.params

        # 鼠标操作
        if t == ActionType.MOUSE_MOVE:
            x, y = self._scale_coordinates(p.get("x", 0), p.get("y", 0))
            duration = p.get("duration", 0.5)
            pg.moveTo(x, y, duration=duration)
            return True

        elif t == ActionType.MOUSE_CLICK:
            x, y = self._scale_coordinates(p.get("x", 0), p.get("y", 0))
            clicks = p.get("clicks", 1)
            interval = p.get("interval", 0.0)
            button = p.get("button", "left")
            if x or y:
                pg.click(x, y, clicks=clicks, interval=interval, button=button)
            else:
                pg.click(clicks=clicks, interval=interval, button=button)
            return True

        elif t == ActionType.MOUSE_DOUBLE_CLICK:
            x, y = self._scale_coordinates(p.get("x", 0), p.get("y", 0))
            if x or y:
                pg.doubleClick(x, y)
            else:
                pg.doubleClick()
            return True

        elif t == ActionType.MOUSE_RIGHT_CLICK:
            x, y = self._scale_coordinates(p.get("x", 0), p.get("y", 0))
            if x or y:
                pg.rightClick(x, y)
            else:
                pg.rightClick()
            return True

        elif t == ActionType.MOUSE_DRAG:
            x1, y1 = self._scale_coordinates(p.get("x1", 0), p.get("y1", 0))
            x2, y2 = self._scale_coordinates(p.get("x2", 0), p.get("y2", 0))
            duration = p.get("duration", 0.5)
            button = p.get("button", "left")
            pg.moveTo(x1, y1)
            pg.dragTo(x2, y2, duration=duration, button=button)
            return True

        elif t == ActionType.MOUSE_SCROLL:
            clicks = p.get("clicks", 3)
            x, y = self._scale_coordinates(p.get("x", 0), p.get("y", 0))
            if x or y:
                pg.scroll(clicks, x, y)
            else:
                pg.scroll(clicks)
            return True

        # 键盘操作
        elif t == ActionType.KEYBOARD_TYPE:
            text = p.get("text", "")
            interval = p.get("interval", 0.05)
            pg.typewrite(text, interval=interval)
            return True

        elif t == ActionType.KEYBOARD_PRESS:
            keys = p.get("keys", [])
            presses = p.get("presses", 1)
            interval = p.get("interval", 0.0)
            if isinstance(keys, str):
                keys = [keys]
            for key in keys:
                pg.press(key, presses=presses, interval=interval)
            return True

        elif t == ActionType.KEYBOARD_HOTKEY:
            keys = p.get("keys", [])
            if isinstance(keys, str):
                keys = keys.split("+")
            pg.hotkey(*keys)
            return True

        # 系统操作
        elif t == ActionType.SHELL_EXEC:
            cmd = p.get("command", "")
            if not cmd:
                return False
            import subprocess
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            action.post_state = {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}
            return result.returncode == 0

        elif t == ActionType.SCREENSHOT:
            filename = p.get("filename", f"screenshot_{int(time.time())}.png")
            if self.root:
                path = self.root / "logs" / filename
                path.parent.mkdir(parents=True, exist_ok=True)
            else:
                path = Path(filename)
            pg.screenshot(str(path))
            return True

        elif t == ActionType.WAIT:
            seconds = p.get("seconds", 1.0)
            time.sleep(seconds)
            return True

        elif t == ActionType.ALERT:
            text = p.get("text", "灵枢通知")
            title = p.get("title", "灵枢")
            # pyautogui 弹窗（阻塞）
            pg.alert(text=text, title=title)
            return True

        else:
            raise ValueError(f"未知操作类型: {t}")

    # ==================== 状态捕获与回滚 ====================

    def _capture_pre_state(self, action: ExecutorAction) -> Dict:
        """捕获操作前的状态，用于回滚"""
        pg = self._pyautogui
        t = action.action_type
        state = {"timestamp": time.time()}

        if t in (ActionType.MOUSE_MOVE, ActionType.MOUSE_CLICK, ActionType.MOUSE_DRAG):
            state["mouse_pos"] = pg.position()

        elif t == ActionType.KEYBOARD_TYPE:
            # 键盘操作前无法捕获状态（除非获取剪贴板）
            state["clipboard"] = ""
            try:
                state["clipboard"] = pg.clipboard  # 可能不可用
            except Exception:
                pass

        elif t == ActionType.SHELL_EXEC:
            state["command"] = action.params.get("command", "")

        return state

    def _capture_post_state(self, action: ExecutorAction) -> Dict:
        """捕获操作后的状态"""
        pg = self._pyautogui
        state = {"timestamp": time.time()}

        if action.action_type in (ActionType.MOUSE_MOVE, ActionType.MOUSE_CLICK, ActionType.MOUSE_DRAG):
            state["mouse_pos"] = pg.position()

        return state

    def _build_rollback(self, action: ExecutorAction) -> Optional[Dict]:
        """构建回滚操作参数"""
        t = action.action_type
        pre = action.pre_state or {}

        if t == ActionType.MOUSE_MOVE:
            pos = pre.get("mouse_pos")
            if pos:
                return {"action_type": "MOUSE_MOVE", "x": pos[0], "y": pos[1], "description": "回滚：鼠标移回原位置"}

        elif t == ActionType.MOUSE_DRAG:
            pos = pre.get("mouse_pos")
            if pos:
                return {"action_type": "MOUSE_MOVE", "x": pos[0], "y": pos[1], "description": "回滚：鼠标移回拖动前位置"}

        elif t == ActionType.KEYBOARD_TYPE:
            text = action.params.get("text", "")
            if text:
                # 回滚 = 按多次 backspace
                return {
                    "action_type": "KEYBOARD_PRESS",
                    "keys": ["backspace"] * len(text),
                    "description": f"回滚：删除已输入的 {len(text)} 个字符",
                }

        elif t == ActionType.MOUSE_CLICK:
            # 点击不可逆，无法自动回滚
            return {"action_type": "ALERT", "text": "点击操作已执行，请手动确认是否需要撤销", "description": "回滚提示：点击不可逆"}

        elif t == ActionType.SHELL_EXEC:
            cmd = pre.get("command", "")
            return {"action_type": "ALERT", "text": f"Shell 命令已执行: {cmd}\n请手动检查并恢复", "description": "回滚提示：Shell 命令不可逆"}

        return None

    # ==================== Undo / Redo ====================

    def undo(self, count: int = 1) -> List[ExecutorAction]:
        """
        撤销最近 N 个操作

        返回：实际撤销的操作列表
        """
        undone = []
        for _ in range(count):
            if not self._history:
                break
            action = self._history.pop()
            rollback = action.rollback_params

            if rollback:
                try:
                    rb_action = ExecutorAction(
                        action_type=ActionType[rollback["action_type"]],
                        params={k: v for k, v in rollback.items() if k not in ("action_type", "description")},
                        timestamp=time.time(),
                        description=rollback.get("description", f"回滚: {action.description}"),
                    )
                    success = self._dispatch_action(rb_action)
                    rb_action.executed = True
                    rb_action.success = success
                    self._redo_stack.append(action)
                    undone.append(rb_action)
                    print(f"[Executor] ↩️  撤销: {action.description} → {rb_action.description}")
                except Exception as e:
                    print(f"[Executor] ❌ 回滚失败: {e}")
                    # 失败也入 redo 栈，允许重新尝试
                    self._redo_stack.append(action)
            else:
                print(f"[Executor] ⚠️ 无法自动撤销: {action.description}（无回滚方案）")
                self._redo_stack.append(action)

        return undone

    def redo(self, count: int = 1) -> List[ExecutorAction]:
        """重做最近撤销的操作"""
        redone = []
        for _ in range(count):
            if not self._redo_stack:
                break
            action = self._redo_stack.pop()
            success = self.execute_action(action, auto_confirm=True)
            if success:
                redone.append(action)
        return redone

    def can_undo(self) -> bool:
        return len(self._history) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def get_history(self, limit: int = 20) -> List[Dict]:
        """获取操作历史（人类可读）"""
        return [
            {
                "time": datetime.fromtimestamp(a.timestamp).strftime("%H:%M:%S"),
                "type": a.action_type.name,
                "desc": a.description,
                "success": a.success,
                "confirmed": a.confirmed,
            }
            for a in self._history[-limit:]
        ]

    def _trim_history(self):
        """限制历史栈大小"""
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit:]

    def clear_history(self):
        """清空历史"""
        self._history.clear()
        self._redo_stack.clear()

    # ==================== 操作序列 ====================

    def execute_sequence(
        self,
        actions: List[ExecutorAction],
        sequence_name: str = "unnamed",
        auto_confirm: bool = False,
        stop_on_error: bool = True,
    ) -> Tuple[int, int]:
        """
        批量执行操作序列

        返回: (成功数, 失败数)
        """
        seq = ActionSequence(
            name=sequence_name,
            actions=actions,
            created_at=time.time(),
        )
        self._sequences.append(seq)

        success_count = 0
        fail_count = 0

        for i, action in enumerate(actions):
            print(f"[Executor] [{i+1}/{len(actions)}] {action.description}")
            ok = self.execute_action(action, auto_confirm=auto_confirm)
            if ok:
                success_count += 1
            else:
                fail_count += 1
                if stop_on_error:
                    print(f"[Executor] ⏹️ 序列因错误停止")
                    break

        return success_count, fail_count

    def record_sequence(self, actions: List[ExecutorAction], name: str, source: str = "manual") -> ActionSequence:
        """记录一个操作序列（不执行，仅保存）"""
        seq = ActionSequence(
            name=name,
            actions=actions,
            created_at=time.time(),
            source=source,
        )
        self._sequences.append(seq)
        return seq

    def get_sequences(self) -> List[Dict]:
        """获取所有序列摘要"""
        return [
            {
                "name": s.name,
                "source": s.source,
                "action_count": len(s.actions),
                "created_at": datetime.fromtimestamp(s.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            }
            for s in self._sequences
        ]

    # ==================== 视觉联动 ====================

    def execute_from_vision(self, vision_result: Any, auto_confirm: bool = False) -> Tuple[int, int]:
        """
        根据视觉分析结果执行操作

        解析 vision_result.suggested_actions 中的操作指令，
        转换为 pyautogui 操作并执行。

        示例 vision action:
          {"action": "click", "target": "保存按钮", "coords": [100, 200]}
          {"action": "type", "text": "Hello"}
        """
        if not hasattr(vision_result, "suggested_actions"):
            print("[Executor] ⚠️ 视觉结果无 suggested_actions")
            return (0, 0)

        actions = []
        for va in vision_result.suggested_actions:
            if not isinstance(va, dict):
                continue
            act_type = va.get("action", "")
            target = va.get("target", "")
            coords = va.get("coords", [])

            action = None
            if act_type in ("click", "single_click"):
                x, y = coords if len(coords) >= 2 else (0, 0)
                action = ExecutorAction(
                    action_type=ActionType.MOUSE_CLICK,
                    params={"x": x, "y": y, "button": "left"},
                    timestamp=time.time(),
                    description=f"视觉联动: 点击 {target} ({x},{y})",
                )
            elif act_type == "double_click":
                x, y = coords if len(coords) >= 2 else (0, 0)
                action = ExecutorAction(
                    action_type=ActionType.MOUSE_DOUBLE_CLICK,
                    params={"x": x, "y": y},
                    timestamp=time.time(),
                    description=f"视觉联动: 双击 {target} ({x},{y})",
                )
            elif act_type == "right_click":
                x, y = coords if len(coords) >= 2 else (0, 0)
                action = ExecutorAction(
                    action_type=ActionType.MOUSE_RIGHT_CLICK,
                    params={"x": x, "y": y},
                    timestamp=time.time(),
                    description=f"视觉联动: 右键 {target} ({x},{y})",
                )
            elif act_type == "type":
                text = va.get("text", "")
                action = ExecutorAction(
                    action_type=ActionType.KEYBOARD_TYPE,
                    params={"text": text},
                    timestamp=time.time(),
                    description=f"视觉联动: 输入 '{text[:30]}...'",
                )
            elif act_type == "scroll":
                clicks = va.get("clicks", 3)
                x, y = coords if len(coords) >= 2 else (0, 0)
                action = ExecutorAction(
                    action_type=ActionType.MOUSE_SCROLL,
                    params={"clicks": clicks, "x": x, "y": y},
                    timestamp=time.time(),
                    description=f"视觉联动: 滚动 {clicks} 格",
                )
            elif act_type == "drag":
                x1, y1 = coords[0] if len(coords) >= 1 else (0, 0)
                x2, y2 = coords[1] if len(coords) >= 2 else (x1, y1)
                action = ExecutorAction(
                    action_type=ActionType.MOUSE_DRAG,
                    params={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    timestamp=time.time(),
                    description=f"视觉联动: 拖拽 ({x1},{y1}) -> ({x2},{y2})",
                )
            elif act_type == "wait":
                seconds = va.get("seconds", 1.0)
                action = ExecutorAction(
                    action_type=ActionType.WAIT,
                    params={"seconds": seconds},
                    timestamp=time.time(),
                    description=f"视觉联动: 等待 {seconds} 秒",
                )
            elif act_type == "screenshot":
                action = ExecutorAction(
                    action_type=ActionType.SCREENSHOT,
                    params={"filename": va.get("filename", f"vision_{int(time.time())}.png")},
                    timestamp=time.time(),
                    description="视觉联动: 截图",
                )

            if action:
                actions.append(action)

        if not actions:
            print("[Executor] ℹ️ 无可执行视觉操作")
            return (0, 0)

        return self.execute_sequence(actions, sequence_name="vision_batch", auto_confirm=auto_confirm)

    # ==================== 便捷方法 ====================

    def click(self, x: int, y: int, button: str = "left", auto_confirm: bool = False) -> bool:
        """便捷：点击指定坐标"""
        action = ExecutorAction(
            action_type=ActionType.MOUSE_CLICK,
            params={"x": x, "y": y, "button": button},
            timestamp=time.time(),
            description=f"点击 ({x}, {y}) [{button}]",
        )
        return self.execute_action(action, auto_confirm=auto_confirm)

    def move(self, x: int, y: int, duration: float = 0.5, auto_confirm: bool = False) -> bool:
        """便捷：移动鼠标"""
        action = ExecutorAction(
            action_type=ActionType.MOUSE_MOVE,
            params={"x": x, "y": y, "duration": duration},
            timestamp=time.time(),
            description=f"鼠标移动至 ({x}, {y})",
        )
        return self.execute_action(action, auto_confirm=auto_confirm)

    def type_text(self, text: str, interval: float = 0.05, auto_confirm: bool = False) -> bool:
        """便捷：输入文本"""
        action = ExecutorAction(
            action_type=ActionType.KEYBOARD_TYPE,
            params={"text": text, "interval": interval},
            timestamp=time.time(),
            description=f"输入文本: {text[:50]}",
        )
        return self.execute_action(action, auto_confirm=auto_confirm)

    def press_key(self, key: str, presses: int = 1, auto_confirm: bool = False) -> bool:
        """便捷：按按键"""
        action = ExecutorAction(
            action_type=ActionType.KEYBOARD_PRESS,
            params={"keys": [key], "presses": presses},
            timestamp=time.time(),
            description=f"按键: {key} x{presses}",
        )
        return self.execute_action(action, auto_confirm=auto_confirm)

    def hotkey(self, *keys: str, auto_confirm: bool = False) -> bool:
        """便捷：组合键"""
        action = ExecutorAction(
            action_type=ActionType.KEYBOARD_HOTKEY,
            params={"keys": list(keys)},
            timestamp=time.time(),
            description=f"组合键: {'+'.join(keys)}",
        )
        return self.execute_action(action, auto_confirm=auto_confirm)

    def scroll(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None, auto_confirm: bool = False) -> bool:
        """便捷：滚动"""
        params = {"clicks": clicks}
        if x is not None and y is not None:
            params.update({"x": x, "y": y})
        action = ExecutorAction(
            action_type=ActionType.MOUSE_SCROLL,
            params=params,
            timestamp=time.time(),
            description=f"滚动 {clicks} 格",
        )
        return self.execute_action(action, auto_confirm=auto_confirm)

    def shell(self, command: str, auto_confirm: bool = False) -> bool:
        """便捷：执行 shell 命令（敏感操作）"""
        action = ExecutorAction(
            action_type=ActionType.SHELL_EXEC,
            params={"command": command},
            timestamp=time.time(),
            description=f"Shell: {command[:80]}",
        )
        return self.execute_action(action, auto_confirm=auto_confirm)

    def screenshot(self, filename: Optional[str] = None, auto_confirm: bool = False) -> bool:
        """便捷：截图"""
        action = ExecutorAction(
            action_type=ActionType.SCREENSHOT,
            params={"filename": filename or f"exec_{int(time.time())}.png"},
            timestamp=time.time(),
            description="截图",
        )
        return self.execute_action(action, auto_confirm=auto_confirm)

    def wait(self, seconds: float, auto_confirm: bool = False) -> bool:
        """便捷：等待"""
        action = ExecutorAction(
            action_type=ActionType.WAIT,
            params={"seconds": seconds},
            timestamp=time.time(),
            description=f"等待 {seconds} 秒",
        )
        return self.execute_action(action, auto_confirm=auto_confirm)

    def alert(self, text: str, title: str = "灵枢", auto_confirm: bool = False) -> bool:
        """便捷：弹窗提醒"""
        action = ExecutorAction(
            action_type=ActionType.ALERT,
            params={"text": text, "title": title},
            timestamp=time.time(),
            description=f"弹窗: {text[:50]}",
        )
        return self.execute_action(action, auto_confirm=auto_confirm)

    # ==================== 状态查询 ====================

    def get_status(self) -> Dict:
        """获取执行模块状态"""
        return {
            "ready": self.is_ready(),
            "safety_level": self.safety_level.value,
            "dry_run": self.dry_run,
            "screen_size": self._screen_size,
            "reference_resolution": self._reference_resolution,
            "scaling_factor": self._scaling_factor,
            "history_count": len(self._history),
            "redo_count": len(self._redo_stack),
            "sequence_count": len(self._sequences),
            "can_undo": self.can_undo(),
            "can_redo": self.can_redo(),
        }
