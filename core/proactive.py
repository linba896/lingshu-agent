#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 主动服务模块（Phase 3 Proactive Agent）
功能：预测性维护、上下文感知、智能日程、跨领域简报

设计理念：
  1. 预测性维护：系统资源监控 + 智能预警（CPU/内存/磁盘）
  2. 上下文感知：根据当前应用/窗口/时间提供建议
  3. 智能日程：基于用户习惯的提醒和任务推荐
  4. 跨领域简报：整合多源信息，主动推送综合简报

"""

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class ProactiveSuggestion:
    """主动建议条目"""
    id: str
    timestamp: float
    type: str  # "performance", "context", "schedule", "cross_domain"
    title: str
    description: str
    confidence: float  # 0.0 - 1.0
    suggested_action: Optional[str] = None
    auto_execute: bool = False  # 是否自动执行（默认否，需要用户确认）
    dismissed: bool = False


class ProactiveEngine:
    """
    主动服务引擎
    
    持续监控环境和用户行为，主动提供建议：
    - 系统资源预测（CPU/内存/磁盘）
    - 应用上下文感知（PPT/Excel/浏览器）
    - 日程提醒（会议、休息、任务）
    - 跨领域简报（股票、新闻、天气）
    """

    def __init__(
        self,
        config: Dict,
        root: Path,
        on_suggestion: Optional[Callable[[ProactiveSuggestion], None]] = None,
    ):
        self.config = config or {}
        self.root = root
        self.enabled = config.get("enabled", True)
        self.check_interval = config.get("check_interval", 60)
        self.predictive_maintenance = config.get("predictive_maintenance", True)
        self.cross_domain = config.get("cross_domain_integration", True)
        self.smart_schedule = config.get("smart_schedule", True)
        self.quiet_hours = config.get("quiet_hours", [23, 7])

        self._on_suggestion = on_suggestion
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 状态变量
        self._system_history: List[Dict] = []  # 系统资源历史
        self._suggestions: List[ProactiveSuggestion] = []
        self._context_state: Dict = {}  # 当前应用/窗口状态
        self._user_patterns: Dict = {}  # 用户行为模式

        # 建议冷却期（避免重复推送）
        self._last_suggestion_time: Dict[str, float] = {}
        # 建议冷却时间（秒）
        self._suggestion_cooldown = 300

    def is_enabled(self) -> bool:
        return self.enabled

    # ==================== 启动/停止 ====================

    def start(self):
        """启动主动服务引擎"""
        if not self.enabled or self._running:
            return
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
           target=self._proactive_loop,
            daemon=True,
            name="LingShu-Proactive",
        )
        self._thread.start()
        print("[Proactive] ✅ 主动服务引擎已启动")

    def stop(self):
        """停止主动服务引擎"""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        print("[Proactive] 主动服务引擎已停止")

    def _proactive_loop(self):
        """主动服务主循环"""
        while not self._stop_event.is_set():
            try:
                self._check_all()
            except Exception as e:
                print(f"[Proactive] 检查出错: {e}")
            # 等待间隔
            self._stop_event.wait(self.check_interval)

    # ==================== 检查逻辑 ====================

    def _check_all(self):
        """执行所有检查"""
        # 检查是否在安静时段
        if self._is_quiet_hours():
            return

        # 1. 系统资源预测性维护
        if self.predictive_maintenance:
            self._check_system_resources()

        # 2. 上下文感知
        self._check_context_awareness()

        # 3. 智能日程
        if self.smart_schedule:
            self._check_smart_schedule()

    def _is_quiet_hours(self) -> bool:
        """检查是否在安静时段"""
        if not self.quiet_hours or len(self.quiet_hours) < 2:
            return False
        hour = time.localtime().tm_hour
        start, end = self.quiet_hours
        if start > end:  # 跨午夜，如 23-7
            return hour >= start or hour < end
        return start <= hour < end

    def _check_system_resources(self):
        """检查系统资源并预测（系统资源预测性维护）"""
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(str(self.root))

            # 记录历史
            self._system_history.append({
                "time": time.time(),
                "cpu": cpu,
                "memory": memory.percent,
                "disk": disk.percent,
            })
            # 限制历史记录大小
            if len(self._system_history) > 100:
                self._system_history = self._system_history[-80:]

            # 内存预警（>85%）
            if memory.percent > 85:
                self._suggest(
                    type="performance",
                    title="⚠️ 内存使用率过高",
                    description=f"当前内存使用率 {memory.percent:.1f}%，建议关闭不必要的程序或重启应用",
                    confidence=min(memory.percent / 100, 0.95),
                    suggested_action="打开任务管理器查看内存占用",
                )

            # CPU 持续高负载（>90% 超过5分钟）
            recent_cpu = [s["cpu"] for s in self._system_history[-10:]]
            if len(recent_cpu) >= 5 and sum(recent_cpu) / len(recent_cpu) > 90:
                self._suggest(
                    type="performance",
                    title="🔥 CPU 持续高负载",
                    description=f"CPU 平均使用率 {sum(recent_cpu)/len(recent_cpu):.1f}%，可能存在性能问题",
                    confidence=0.85,
                    suggested_action="检查是否有程序卡死或占用过高",
                )

            # 磁盘空间不足（<10GB 或 >90%）
            free_gb = disk.free / (1024**3)
            if free_gb < 10 or disk.percent > 90:
                self._suggest(
                    type="performance",
                    title="💾 磁盘空间不足",
                    description=f"剩余空间 {free_gb:.1f}GB，建议清理不必要的文件",
                    confidence=0.9,
                    suggested_action="打开磁盘清理工具或删除大文件",
                )

        except ImportError:
            pass

    def _check_context_awareness(self):
        """检查上下文并提供建议（上下文感知）"""
        # 检测当前应用窗口（简化：通过进程名检测）
        # 实际实现可通过 pygetwindow 或 pywin32 获取窗口标题
        # 这里仅展示框架，实际实现需要平台适配
        try:
            import psutil

            # 检测PPT演示
            for proc in psutil.process_iter(['name']):
                name = proc.info['name']
                if name and ('powerpnt' in name.lower() or 'presentation' in name.lower()):
                    self._suggest(
                        type="context",
                        title="📊 PPT 演示模式检测",
                        description="检测到您正在使用 PowerPoint，需要我帮您：",
                        confidence=0.7,
                        suggested_action="打开演示者视图或切换幻灯片",
                    )
                    break

                # 检测Excel
                if name and ('excel' in name.lower()):
                    self._suggest(
                        type="context",
                        title="📊 Excel 工作模式",
                        description="检测到您正在使用 Excel，需要我帮您：",
                        confidence=0.7,
                        suggested_action="整理数据或生成图表",
                    )
                    break

        except ImportError:
            pass

    def _check_smart_schedule(self):
        """智能日程检查"""
        # 基于时间的提醒（简化示例）
        # 实际实现需要连接日历API（如 Google Calendar、Outlook）
        now = time.localtime()
        hour = now.tm_hour
        minute = now.tm_min

        # 早安提醒（8:00-8:05）
        if hour == 8 and 0 <= minute <= 5:
            self._suggest(
                type="schedule",
                title="🌅 早安提醒",
                description="新的一天开始了！今天有重要任务吗？",
                confidence=0.8,
                suggested_action=None,  # 无建议操作，仅提醒
            )

        # 午餐提醒（12:00-12:05）
        if hour == 12 and 0 <= minute <= 5:
            self._suggest(
                type="schedule",
                title="🍜 午餐时间",
                description="工作再忙也要记得吃饭哦！",
                confidence=0.6,
                suggested_action=None,
            )

        # 下班提醒（17:30-17:35）
        if hour == 17 and 30 <= minute <= 35:
            self._suggest(
                type="schedule",
                title="🌆 下班提醒",
                description="工作了一天，记得保存文件并备份重要数据",
                confidence=0.7,
                suggested_action="保存所有文件并备份工作数据",
            )

    # ==================== 建议管理 ====================

    def _suggest(
        self,
        type: str,
        title: str,
        description: str,
        confidence: float,
        suggested_action: Optional[str] = None,
        auto_execute: bool = False,
    ):
        """
        生成并推送建议
        
        冷却机制：同一类型建议5分钟内不重复推送
        """
        suggestion_key = f"{type}:{title}"
        now = time.time()

        # 检查冷却期
        last_time = self._last_suggestion_time.get(suggestion_key, 0)
        if now - last_time < self._suggestion_cooldown:
            return

        # 自动执行阈值检查（默认0.9以上才自动执行）
        if auto_execute and confidence < 0.9:
            auto_execute = False

        suggestion = ProactiveSuggestion(
            id=f"sug_{int(now)}_{type}",
            timestamp=now,
            type=type,
            title=title,
            description=description,
            confidence=confidence,
            suggested_action=suggested_action,
            auto_execute=auto_execute,
        )

        self._suggestions.append(suggestion)
        self._last_suggestion_time[suggestion_key] = now

        # 触发回调
        if self._on_suggestion:
            self._on_suggestion(suggestion)

        # 自动执行（如果启用且置信度足够）
        if auto_execute:
            print(f"[Proactive] 🤖 自动执行: {suggested_action}")
            # 执行建议操作（需要 executor 模块支持）

        print(f"[Proactive] 💡 {title} ({confidence:.0%} 置信度): {description}")

    # ==================== 查询接口 ====================

    def get_pending_suggestions(self) -> List[ProactiveSuggestion]:
        """获取待处理的建议"""
        return [s for s in self._suggestions if not s.dismissed]

    def dismiss_suggestion(self, suggestion_id: str):
        """忽略建议"""
        for s in self._suggestions:
            if s.id == suggestion_id:
                s.dismissed = True
                break

    def get_system_history(self, limit: int = 24) -> List[Dict]:
        """获取系统资源历史"""
        return self._system_history[-limit:]

    # ==================== 跨领域简报 ====================

    def prepare_briefing(self, topic: str) -> Dict:
        """
        准备跨领域简报
        
        整合多源信息，生成综合简报：
        - 本地文件搜索
        - 网络信息检索（需要联网模块）
        - 知识库查询
        """
        result = {
            "topic": topic,
            "sources": [],
            "summary": "",
            "suggested_actions": [],
        }

        # 1. 本地知识库搜索
        try:
            docs_dir = self.root / "knowledge" / "documents"
            if docs_dir.exists():
                recent_files = sorted(
                    docs_dir.glob("*"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )[:10]
                result["sources"].append({
                    "type": "local_files",
                    "items": [f.name for f in recent_files],
                })
        except Exception:
            pass

        # 2. 网络搜索（需要联网模块）
        # 简化：仅返回框架，实际实现需要网络模块

        # 3. 建议操作
        result["summary"] = f"为您整理了关于'{topic}'的综合简报..."
        result["suggested_actions"] = [
            "打开相关文件进行阅读",
            "搜索更多网络资料",
            "整理关键信息到笔记",
        ]

        return result

