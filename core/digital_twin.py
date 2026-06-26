#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 数字孪生模块（Digital Twin / 沙箱预演）
功能：操作模拟、沙箱环境、预演模式、后果预测

设计理念：
  1. 沙箱隔离：所有预演操作在模拟环境中执行，不影响真实系统
  2. 后果预测：预测操作可能带来的影响（文件变动、界面变化、系统状态）
  3. 风险评估：为每个操作计算风险分数（0-100）
  4. 预演模式：strict（严格）/ advisory（建议）/ off（关闭）
  5. 与执行模块联动：执行前自动预演，用户确认后再执行

核心流程：
  1. 捕获当前系统状态（屏幕截图、窗口列表、文件状态）
  2. 在沙箱中模拟操作执行
  3. 对比操作前后的差异
  4. 生成风险报告和建议
  5. 用户确认后执行真实操作

风险等级：
  0-20   绿色：安全操作（点击、移动、输入）
  21-50  黄色：低风险（打开文件、滚动、切换窗口）
  51-80  橙色：中风险（删除文件、修改设置、执行脚本）
  81-100 红色：高风险（格式化、支付、网络配置、系统命令）

"""

import copy
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


class RehearsalMode(Enum):
    """预演模式"""
    STRICT = "strict"      # 严格：所有操作必须预演通过才能执行
    ADVISORY = "advisory"    # 建议：仅高风险操作预演，结果仅供参考
    OFF = "off"              # 关闭：不进行预演


class RiskLevel(Enum):
    """风险等级"""
    SAFE = 0       # 绿色
    LOW = 1        # 黄色
    MEDIUM = 2     # 橙色
    HIGH = 3       # 红色


@dataclass
class SystemSnapshot:
    """系统状态快照"""
    timestamp: float
    screenshot: Optional[np.ndarray] = None  # 屏幕图像
    active_window: Optional[str] = None      # 当前窗口标题
    mouse_position: Optional[Tuple[int, int]] = None  # 鼠标位置
    # 文件状态（简化：仅记录关键文件哈希）
    file_states: Dict[str, str] = field(default_factory=dict)
    # 进程列表
    process_list: List[str] = field(default_factory=list)
    # 网络状态
    network_connections: List[str] = field(default_factory=list)


@dataclass
class SimulatedEffect:
    """模拟操作效果"""
    action_type: str
    description: str
    # 界面变化预测
    predicted_ui_change: str = ""
    # 文件变动预测
    predicted_file_changes: List[str] = field(default_factory=list)
    # 进程变动预测
    predicted_process_changes: List[str] = field(default_factory=list)
    # 风险分数
    risk_score: int = 0
    risk_level: RiskLevel = RiskLevel.SAFE
    # 可撤销性
    reversible: bool = True
    rollback_cost: str = "低"  # 低/中/高/不可撤销


@dataclass
class RehearsalReport:
    """预演报告"""
    rehearsal_id: str
    timestamp: float
    original_action: Dict[str, Any]
    # 预演结果
    effects: List[SimulatedEffect]
    overall_risk_score: int
    overall_risk_level: RiskLevel
    # 建议
    recommendation: str  # "execute" / "confirm" / "cancel" / "modify"
    warning_messages: List[str] = field(default_factory=list)
    # 替代方案
    alternatives: List[str] = field(default_factory=list)


class DigitalTwin:
    """
    数字孪生（沙箱预演引擎）

    为执行模块提供操作预演能力：
      - 捕获系统快照
      - 模拟操作效果
      - 评估风险等级
      - 生成预演报告
    """

    # 风险权重配置
    RISK_WEIGHTS = {
        "MOUSE_MOVE": 5,
        "MOUSE_CLICK": 10,
        "MOUSE_DOUBLE_CLICK": 10,
        "MOUSE_RIGHT_CLICK": 15,
        "MOUSE_DRAG": 10,
        "MOUSE_SCROLL": 5,
        "KEYBOARD_TYPE": 10,
        "KEYBOARD_PRESS": 5,
        "KEYBOARD_HOTKEY": 20,
        "SHELL_EXEC": 80,
        "SCREENSHOT": 0,
        "WAIT": 0,
        "ALERT": 0,
    }

    # 敏感关键词风险加成
    SENSITIVE_KEYWORDS = {
        "delete": 30, "remove": 30, "rm ": 40, "format": 90,
        "payment": 70, "pay": 50, "password": 40, "credential": 50,
        "registry": 50, "regedit": 60, "sudo": 40, "admin": 30,
        "iptables": 50, "firewall": 40, "netsh": 40,
    }

    def __init__(self, config: Dict, root: Optional[Path] = None, vision_module=None):
        self.config = config or {}
        self.root = root
        self.vision = vision_module
        self.mode = RehearsalMode(self.config.get("rehearsal_mode", "advisory"))
        self.high_risk_threshold = self.config.get("high_risk_threshold", 50)
        self.rehearsal_timeout = self.config.get("rehearsal_timeout", 30)
        self.sandbox_enabled = self.config.get("sandbox_enabled", True)

        # 历史快照（用于对比）
        self._snapshots: List[SystemSnapshot] = []
        self._max_snapshots = 10

    def is_enabled(self) -> bool:
        return self.mode != RehearsalMode.OFF

    # ==================== 系统快照 ====================

    def capture_snapshot(self) -> SystemSnapshot:
        """捕获当前系统状态快照"""
        snapshot = SystemSnapshot(timestamp=time.time())

        # 鼠标位置
        try:
            import pyautogui
            snapshot.mouse_position = pyautogui.position()
        except ImportError:
            pass

        # 屏幕截图（如果视觉模块可用）
        if self.vision and self.vision.is_ready():
            try:
                snapshot.screenshot = self.vision.capture_screen()
            except Exception:
                pass

        # 活动窗口（简化）
        try:
            import pyautogui
            # pyautogui 没有直接获取窗口标题的 API，需要其他库
            # 简化：仅标记为"已获取"
            snapshot.active_window = "unknown"
        except ImportError:
            pass

        # 存储快照
        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots = self._snapshots[-self._max_snapshots:]

        return snapshot

    def get_last_snapshot(self) -> Optional[SystemSnapshot]:
        """获取最近一次快照"""
        if self._snapshots:
            return self._snapshots[-1]
        return None

    # ==================== 操作模拟 ====================

    def simulate(self, action: Dict[str, Any]) -> RehearsalReport:
        """
        模拟操作执行并生成预演报告

        action: {"action_type": "MOUSE_CLICK", "params": {"x": 100, "y": 200}, ...}
        """
        action_type = action.get("action_type", "UNKNOWN")
        params = action.get("params", {})
        description = action.get("description", "")

        effects = []
        warning_messages = []
        alternatives = []

        # 基础风险分数
        base_risk = self.RISK_WEIGHTS.get(action_type, 50)
        risk_score = base_risk

        # 检查敏感关键词
        for keyword, bonus in self.SENSITIVE_KEYWORDS.items():
            if keyword.lower() in description.lower() or keyword.lower() in json.dumps(params).lower():
                risk_score += bonus
                warning_messages.append(f"检测到敏感关键词: '{keyword}' (+{bonus} 风险)")

        # 根据操作类型模拟效果
        if action_type in ("MOUSE_CLICK", "MOUSE_DOUBLE_CLICK", "MOUSE_RIGHT_CLICK"):
            effect = self._simulate_mouse_click(action_type, params, description)
            effects.append(effect)

        elif action_type == "MOUSE_MOVE":
            effect = self._simulate_mouse_move(params, description)
            effects.append(effect)

        elif action_type == "MOUSE_DRAG":
            effect = self._simulate_mouse_drag(params, description)
            effects.append(effect)

        elif action_type == "MOUSE_SCROLL":
            effect = self._simulate_mouse_scroll(params, description)
            effects.append(effect)

        elif action_type == "KEYBOARD_TYPE":
            effect = self._simulate_keyboard_type(params, description)
            effects.append(effect)
            # 检测敏感输入
            text = params.get("text", "")
            if any(kw in text.lower() for kw in ["password", "passwd", "pwd", "密钥", "密码"]):
                risk_score += 40
                warning_messages.append("检测到可能输入密码/密钥，请确认目标输入框安全")

        elif action_type == "KEYBOARD_PRESS":
            effect = self._simulate_keyboard_press(params, description)
            effects.append(effect)

        elif action_type == "KEYBOARD_HOTKEY":
            effect = self._simulate_keyboard_hotkey(params, description)
            effects.append(effect)

        elif action_type == "SHELL_EXEC":
            effect = self._simulate_shell_exec(params, description)
            effects.append(effect)
            risk_score = min(100, risk_score + 50)  # Shell 命令基础高风险
            warning_messages.append("⚠️ Shell 命令具有最高风险等级，请仔细确认")
            alternatives.append("建议：使用灵枢内置执行功能替代 Shell 命令")

        elif action_type == "SCREENSHOT":
            effect = SimulatedEffect(
                action_type=action_type,
                description="截图操作",
                predicted_ui_change="屏幕截图保存到文件",
                risk_score=0,
                risk_level=RiskLevel.SAFE,
                reversible=True,
                rollback_cost="低",
            )
            effects.append(effect)

        elif action_type == "WAIT":
            effect = SimulatedEffect(
                action_type=action_type,
                description="等待操作",
                predicted_ui_change="无变化，仅等待",
                risk_score=0,
                risk_level=RiskLevel.SAFE,
                reversible=True,
                rollback_cost="低",
            )
            effects.append(effect)

        else:
            effect = SimulatedEffect(
                action_type=action_type,
                description=f"未知操作类型: {action_type}",
                predicted_ui_change="无法预测",
                risk_score=50,
                risk_level=RiskLevel.MEDIUM,
                reversible=False,
                rollback_cost="未知",
            )
            effects.append(effect)
            warning_messages.append(f"未知操作类型 '{action_type}'，风险无法评估")

        # 计算总体风险
        overall_risk = min(100, risk_score)
        overall_level = self._score_to_level(overall_risk)

        # 生成建议
        if overall_risk <= 20:
            recommendation = "execute"
        elif overall_risk <= 50:
            recommendation = "confirm"
        elif overall_risk <= 80:
            recommendation = "confirm"
            warning_messages.append("⚠️ 中风险操作，建议确认后再执行")
        else:
            recommendation = "cancel"
            warning_messages.append("🛑 高风险操作，建议取消或寻找替代方案")
            alternatives.append("建议：降低操作权限或分步执行")

        # 严格模式下，高风险强制取消
        if self.mode == RehearsalMode.STRICT and overall_risk > 80:
            recommendation = "cancel"
            warning_messages.append("严格模式：风险分数超过阈值，禁止执行")

        return RehearsalReport(
            rehearsal_id=f"rehearsal_{int(time.time())}_{hash(action_type) % 10000}",
            timestamp=time.time(),
            original_action=action,
            effects=effects,
            overall_risk_score=overall_risk,
            overall_risk_level=overall_level,
            recommendation=recommendation,
            warning_messages=warning_messages,
            alternatives=alternatives,
        )

    # ==================== 模拟方法 ====================

    def _simulate_mouse_click(self, action_type: str, params: Dict, description: str) -> SimulatedEffect:
        x = params.get("x", 0)
        y = params.get("y", 0)
        button = params.get("button", "left")

        predicted_ui = f"鼠标在 ({x}, {y}) 处点击 [{button}]"
        if self.vision and self.vision.is_ready():
            predicted_ui += "，可能触发按钮/链接/菜单"

        return SimulatedEffect(
            action_type=action_type,
            description=description,
            predicted_ui_change=predicted_ui,
            risk_score=10,
            risk_level=RiskLevel.SAFE,
            reversible=True,
            rollback_cost="低（鼠标移回原位）",
        )

    def _simulate_mouse_move(self, params: Dict, description: str) -> SimulatedEffect:
        x = params.get("x", 0)
        y = params.get("y", 0)
        return SimulatedEffect(
            action_type="MOUSE_MOVE",
            description=description,
            predicted_ui_change=f"鼠标移动至 ({x}, {y})",
            risk_score=5,
            risk_level=RiskLevel.SAFE,
            reversible=True,
            rollback_cost="低（移回原点）",
        )

    def _simulate_mouse_drag(self, params: Dict, description: str) -> SimulatedEffect:
        x1, y1 = params.get("x1", 0), params.get("y1", 0)
        x2, y2 = params.get("x2", 0), params.get("y2", 0)
        return SimulatedEffect(
            action_type="MOUSE_DRAG",
            description=description,
            predicted_ui_change=f"从 ({x1}, {y1}) 拖拽到 ({x2}, {y2})",
            predicted_file_changes=["可能移动文件/选中内容到新位置"],
            risk_score=15,
            risk_level=RiskLevel.SAFE,
            reversible=True,
            rollback_cost="中（需反向拖拽）",
        )

    def _simulate_mouse_scroll(self, params: Dict, description: str) -> SimulatedEffect:
        clicks = params.get("clicks", 3)
        direction = "向下" if clicks > 0 else "向上"
        return SimulatedEffect(
            action_type="MOUSE_SCROLL",
            description=description,
            predicted_ui_change=f"页面{direction}滚动 {abs(clicks)} 格",
            risk_score=5,
            risk_level=RiskLevel.SAFE,
            reversible=True,
            rollback_cost="低（反向滚动）",
        )

    def _simulate_keyboard_type(self, params: Dict, description: str) -> SimulatedEffect:
        text = params.get("text", "")
        preview = text[:20] + "..." if len(text) > 20 else text
        return SimulatedEffect(
            action_type="KEYBOARD_TYPE",
            description=description,
            predicted_ui_change=f"在聚焦输入框中输入: '{preview}'",
            risk_score=15,
            risk_level=RiskLevel.SAFE,
            reversible=True,
            rollback_cost=f"低（按 {len(text)} 次 backspace）",
        )

    def _simulate_keyboard_press(self, params: Dict, description: str) -> SimulatedEffect:
        keys = params.get("keys", [])
        return SimulatedEffect(
            action_type="KEYBOARD_PRESS",
            description=description,
            predicted_ui_change=f"按键: {keys}",
            risk_score=10,
            risk_level=RiskLevel.SAFE,
            reversible=True,
            rollback_cost="低",
        )

    def _simulate_keyboard_hotkey(self, params: Dict, description: str) -> SimulatedEffect:
        keys = params.get("keys", [])
        hotkey_str = "+".join(keys) if isinstance(keys, list) else str(keys)
        risk = 20
        # 危险快捷键检测
        dangerous = ["ctrl+alt+del", "alt+f4", "ctrl+w", "ctrl+shift+esc"]
        if any(d in hotkey_str.lower() for d in dangerous):
            risk = 50
        return SimulatedEffect(
            action_type="KEYBOARD_HOTKEY",
            description=description,
            predicted_ui_change=f"组合键: {hotkey_str}",
            risk_score=risk,
            risk_level=self._score_to_level(risk),
            reversible=True,
            rollback_cost="低",
        )

    def _simulate_shell_exec(self, params: Dict, description: str) -> SimulatedEffect:
        command = params.get("command", "")
        predicted_changes = ["系统命令执行，可能影响系统文件/进程/网络"]
        if any(kw in command.lower() for kw in ["rm", "del", "rmdir", "format"]):
            predicted_changes.append("⚠️ 可能删除文件或格式化磁盘")
        if any(kw in command.lower() for kw in ["wget", "curl", "invoke-webrequest"]):
            predicted_changes.append("⚠️ 可能下载并执行外部文件")
        return SimulatedEffect(
            action_type="SHELL_EXEC",
            description=description,
            predicted_ui_change=f"执行命令: {command[:80]}",
            predicted_file_changes=predicted_changes,
            risk_score=80,
            risk_level=RiskLevel.HIGH,
            reversible=False,
            rollback_cost="不可撤销（系统命令不可逆）",
        )

    # ==================== 工具方法 ====================

    def _score_to_level(self, score: int) -> RiskLevel:
        """风险分数转等级"""
        if score <= 20:
            return RiskLevel.SAFE
        elif score <= 50:
            return RiskLevel.LOW
        elif score <= 80:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.HIGH

    def format_report(self, report: RehearsalReport) -> str:
        """格式化预演报告为人类可读文本"""
        level_emoji = {
            RiskLevel.SAFE: "🟢",
            RiskLevel.LOW: "🟡",
            RiskLevel.MEDIUM: "🟠",
            RiskLevel.HIGH: "🔴",
        }
        rec_emoji = {
            "execute": "✅",
            "confirm": "⚠️",
            "cancel": "🛑",
            "modify": "🔧",
        }

        lines = [
            "=" * 60,
            "  灵枢数字孪生 — 操作预演报告",
            "=" * 60,
            f"  操作: {report.original_action.get('description', 'Unknown')}",
            f"  类型: {report.original_action.get('action_type', 'Unknown')}",
            "-" * 60,
            f"  总体风险: {level_emoji[report.overall_risk_level]} {report.overall_risk_score}/100 ({report.overall_risk_level.name})",
            f"  建议操作: {rec_emoji.get(report.recommendation, '?')} {report.recommendation.upper()}",
            "-" * 60,
        ]

        # 详细效果
        lines.append("  预测效果:")
        for effect in report.effects:
            lines.append(f"    • {effect.description}")
            if effect.predicted_ui_change:
                lines.append(f"      UI: {effect.predicted_ui_change}")
            if effect.predicted_file_changes:
                lines.append(f"      文件: {', '.join(effect.predicted_file_changes[:2])}")
            lines.append(f"      风险: {effect.risk_score} | 可撤销: {'是' if effect.reversible else '否'} | 回滚成本: {effect.rollback_cost}")

        # 警告
        if report.warning_messages:
            lines.append("-" * 60)
            lines.append("  ⚠️ 警告:")
            for w in report.warning_messages:
                lines.append(f"    • {w}")

        # 替代方案
        if report.alternatives:
            lines.append("-" * 60)
            lines.append("  💡 替代方案:")
            for a in report.alternatives:
                lines.append(f"    • {a}")

        lines.append("=" * 60)
        return "\n".join(lines)

    # ==================== 与执行模块联动 ====================

    def should_block(self, report: RehearsalReport) -> bool:
        """判断是否应该阻止执行"""
        if self.mode == RehearsalMode.STRICT and report.overall_risk_score > 80:
            return True
        if report.recommendation == "cancel":
            return True
        return False

    def should_confirm(self, report: RehearsalReport) -> bool:
        """判断是否需要用户确认"""
        if self.mode == RehearsalMode.OFF:
            return False
        return report.overall_risk_score > 20

    # ==================== 批量预演 ====================

    def rehearse_sequence(self, actions: List[Dict[str, Any]]) -> List[RehearsalReport]:
        """批量预演操作序列"""
        reports = []
        for action in actions:
            report = self.simulate(action)
            reports.append(report)
            # 严格模式下，遇到高风险立即终止
            if self.mode == RehearsalMode.STRICT and report.overall_risk_score > 80:
                break
        return reports

    def get_summary(self, reports: List[RehearsalReport]) -> Dict:
        """批量预演摘要"""
        total_risk = max(r.overall_risk_score for r in reports) if reports else 0
        blocked = [r for r in reports if self.should_block(r)]
        need_confirm = [r for r in reports if self.should_confirm(r)]

        return {
            "total_actions": len(reports),
            "blocked_count": len(blocked),
            "confirm_count": len(need_confirm),
            "max_risk_score": total_risk,
            "max_risk_level": self._score_to_level(total_risk).name,
            "can_proceed": len(blocked) == 0,
            "blocked_reasons": [r.warning_messages for r in blocked],
        }
