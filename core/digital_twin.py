#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数字孪生沙箱预演引擎（Digital Twin Sandbox Rehearsal Engine）
进化卷 Phase 8: 沙箱预演与行为自举

功能：
  1. 捕获系统快照（屏幕、鼠标、活动窗口、进程状态）
  2. 模拟操作执行，预测风险与影响
  3. 多模式预演：strict / advisory / off
  4. 生成可执行报告，供用户决策
"""

import dataclasses
import enum
import time
import json
import pathlib
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime


class RehearsalMode(enum.Enum):
    """预演模式"""
    STRICT = "strict"      # 严格模式：任何风险都禁止执行
    ADVISORY = "advisory"  # 建议模式：提示风险，由用户确认
    OFF = "off"            # 关闭模式：直接执行，不预演


@dataclasses.dataclass
class SystemSnapshot:
    """系统快照"""
    timestamp: float
    screen_size: Tuple[int, int]
    mouse_position: Optional[Tuple[int, int]]
    active_window: Optional[str]
    top_processes: List[Dict[str, Any]]
    cpu_percent: float
    memory_percent: float


@dataclasses.dataclass
class RiskAssessment:
    """风险评估"""
    risk_score: int          # 0-100
    risk_level: enum.Enum    # LOW / MEDIUM / HIGH / CRITICAL
    description: str
    mitigations: List[str]


@dataclasses.dataclass
class RehearsalReport:
    """预演报告"""
    action: Dict[str, Any]
    snapshot_before: SystemSnapshot
    predicted_changes: List[str]
    risk_assessment: RiskAssessment
    overall_risk_score: int
    overall_risk_level: RehearsalMode
    recommendation: str    # "PROCEED" / "CAUTION" / "BLOCK"
    execution_time_ms: int


class DigitalTwin:
    """数字孪生沙箱预演引擎"""

    def __init__(self, config: Dict, root: pathlib.Path, vision_module=None):
        self.root = root
        self.config = config
        self.mode = RehearsalMode(config.get("mode", "advisory"))
        self.high_risk_threshold = config.get("high_risk_threshold", 70)
        self.sandbox_enabled = config.get("sandbox_enabled", False)
        self.vision = vision_module
        self._snapshots: List[SystemSnapshot] = []
        self._risk_history: List[Dict] = []

    def is_enabled(self) -> bool:
        return self.mode != RehearsalMode.OFF

    def capture_snapshot(self) -> SystemSnapshot:
        """捕获当前系统快照"""
        import psutil
        try:
            import pyautogui
            screen = pyautogui.size()
            mouse = pyautogui.position()
        except ImportError:
            screen = (1920, 1080)
            mouse = None

        # 获取活动窗口
        active_window = None
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if active:
                active_window = active.title
        except Exception:
            pass

        # 获取 top 进程
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)

        snap = SystemSnapshot(
            timestamp=time.time(),
            screen_size=(screen.width, screen.height) if hasattr(screen, 'width') else screen,
            mouse_position=(mouse.x, mouse.y) if mouse and hasattr(mouse, 'x') else mouse,
            active_window=active_window,
            top_processes=procs[:10],
            cpu_percent=psutil.cpu_percent(interval=0.1),
            memory_percent=psutil.virtual_memory().percent,
        )
        self._snapshots.append(snap)
        return snap

    def simulate(self, action: Dict[str, Any]) -> RehearsalReport:
        """模拟执行操作并生成报告"""
        t0 = time.time()
        snap = self.capture_snapshot()

        # 预测变更
        predicted = self._predict_changes(action, snap)

        # 风险评估
        risk = self._assess_risk(action, snap, predicted)

        # 综合风险评分
        overall_score = risk.risk_score
        if overall_score >= self.high_risk_threshold:
            level = RehearsalMode.STRICT
            recommendation = "BLOCK"
        elif overall_score >= 40:
            level = RehearsalMode.ADVISORY
            recommendation = "CAUTION"
        else:
            level = RehearsalMode.OFF
            recommendation = "PROCEED"

        report = RehearsalReport(
            action=action,
            snapshot_before=snap,
            predicted_changes=predicted,
            risk_assessment=risk,
            overall_risk_score=overall_score,
            overall_risk_level=level,
            recommendation=recommendation,
            execution_time_ms=int((time.time() - t0) * 1000),
        )
        self._risk_history.append({
            "timestamp": time.time(),
            "action_type": action.get("action_type"),
            "risk_score": overall_score,
            "recommendation": recommendation,
        })
        return report

    def _predict_changes(self, action: Dict, snap: SystemSnapshot) -> List[str]:
        """预测操作带来的系统变更"""
        atype = action.get("action_type", "")
        changes = []
        if "MOUSE" in atype:
            x = action.get("params", {}).get("x", 0)
            y = action.get("params", {}).get("y", 0)
            changes.append(f"鼠标将移动至 ({x}, {y})")
            if "CLICK" in atype:
                changes.append("将触发鼠标点击事件")
        elif "KEYBOARD" in atype:
            if "TYPE" in atype:
                text = action.get("params", {}).get("text", "")
                changes.append(f"将输入文本: {text[:20]}...")
            elif "HOTKEY" in atype:
                keys = action.get("params", {}).get("keys", [])
                changes.append(f"将按下组合键: {'+'.join(keys)}")
        elif "SHELL" in atype:
            cmd = action.get("params", {}).get("command", "")
            changes.append(f"将执行 Shell 命令: {cmd[:40]}")
        return changes

    def _assess_risk(self, action: Dict, snap: SystemSnapshot, changes: List[str]) -> RiskAssessment:
        """评估操作风险"""
        atype = action.get("action_type", "")
        score = 0
        level = enum.Enum("RiskLevel", "LOW MEDIUM HIGH CRITICAL")
        desc = "常规操作"
        mitigations = []

        if "SHELL" in atype:
            cmd = action.get("params", {}).get("command", "")
            dangerous = ["rm", "del", "format", "mkfs", "dd", "shutdown", "reboot", "reg delete"]
            if any(d in cmd.lower() for d in dangerous):
                score = 90
                desc = "检测到高危 Shell 命令"
                mitigations = ["请人工确认命令安全性", "建议使用 sandbox 环境测试"]
            else:
                score = 50
                desc = "Shell 命令执行存在系统风险"
                mitigations = ["确认命令来源可信", "检查命令参数"]
        elif "HOTKEY" in atype:
            keys = action.get("params", {}).get("keys", [])
            dangerous_keys = [["ctrl", "alt", "delete"], ["command", "option", "esc"]]
            if any(all(k in keys for k in dk) for dk in dangerous_keys):
                score = 80
                desc = "检测到系统级热键组合"
                mitigations = ["确认不会中断系统服务"]
            else:
                score = 20
        elif "CLICK" in atype:
            x = action.get("params", {}).get("x", 0)
            y = action.get("params", {}).get("y", 0)
            # 检查是否点击屏幕边缘/关闭按钮区域
            if snap.screen_size:
                sw, sh = snap.screen_size
                if x < 50 or x > sw - 50 or y < 50 or y > sh - 50:
                    score = 30
                    desc = "点击位置靠近屏幕边缘，可能触发系统UI"
                    mitigations = ["确认目标窗口位置"]
                else:
                    score = 10
            else:
                score = 10
        else:
            score = 15

        if score >= 80:
            risk_level = level.CRITICAL
        elif score >= 60:
            risk_level = level.HIGH
        elif score >= 30:
            risk_level = level.MEDIUM
        else:
            risk_level = level.LOW

        return RiskAssessment(
            risk_score=score,
            risk_level=risk_level,
            description=desc,
            mitigations=mitigations,
        )

    def format_report(self, report: RehearsalReport) -> str:
        """格式化预演报告为可读文本"""
        lines = [
            "=" * 50,
            "  🔄 数字孪生沙箱预演报告",
            "=" * 50,
            f"操作类型: {report.action.get('action_type', 'UNKNOWN')}",
            f"操作描述: {report.action.get('description', 'N/A')}",
            "",
            "📸 系统快照 (执行前):",
            f"  屏幕分辨率: {report.snapshot_before.screen_size}",
            f"  鼠标位置: {report.snapshot_before.mouse_position}",
            f"  活动窗口: {report.snapshot_before.active_window}",
            f"  CPU: {report.snapshot_before.cpu_percent}% | 内存: {report.snapshot_before.memory_percent}%",
            "",
            "🔮 预测变更:",
        ]
        for c in report.predicted_changes:
            lines.append(f"  • {c}")
        lines.extend([
            "",
            "⚠️ 风险评估:",
            f"  风险评分: {report.overall_risk_score}/100",
            f"  风险等级: {report.risk_assessment.risk_level.name}",
            f"  描述: {report.risk_assessment.description}",
            "  缓解措施:",
        ])
        for m in report.risk_assessment.mitigations:
            lines.append(f"    - {m}")
        lines.extend([
            "",
            f"📋 建议: {report.recommendation}",
            f"⏱️  预演耗时: {report.execution_time_ms}ms",
            "=" * 50,
        ])
        return "\n".join(lines)
