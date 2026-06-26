#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 主动智能模块（进化卷一：Proactive Agent）
功能：预测性维护、跨域信息整合、智能日程、主动建议

核心能力：
  1. 系统资源预测：内存不足、CPU瓶颈时主动建议
  2. 上下文感知：根据当前应用推断用户意图，主动提供辅助
  3. 智能日程：基于日历、邮件、文件修改时间主动提醒
  4. 跨域整合：模糊指令"帮我准备下周见客户的资料"自动整合多源信息

"""

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class ProactiveSuggestion:
    """主动建议数据结构"""
    id: str
    timestamp: float
    type: str  # "performance", "context", "schedule", "cross_domain"
    title: str
    description: str
    confidence: float  # 0.0 - 1.0
    suggested_action: Optional[str] = None
    auto_execute: bool = False  # 是否自动执行（仅高置信度日常操作）
    dismissed: bool = False


class ProactiveEngine:
    """
    主动智能引擎
    像真人助理一样未雨绸缪，主动提供建议和操作
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

        # 状态数据
        self._system_history: List[Dict] = []  # 系统资源历史
        self._suggestions: List[ProactiveSuggestion] = []
        self._context_state: Dict = {}  # 当前上下文状态
        self._user_patterns: Dict = {}  # 用户使用模式

        # 记录最后建议时间（避免重复建议）
        self._last_suggestion_time: Dict[str, float] = {}
        # 建议冷却时间（秒）
        self._suggestion_cooldown = 300

    def is_enabled(self) -> bool:
        return self.enabled

    # ============================================================
    # 启动/停止
    # ============================================================

    def start(self):
        """启动主动检测线程"""
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
        print("[Proactive] ✅ 主动智能引擎已启动")

    def stop(self):
        """停止主动检测"""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        print("[Proactive] 主动智能引擎已停止")

    def _proactive_loop(self):
        """主动检测主循环"""
        while not self._stop_event.is_set():
            try:
                self._check_all()
            except Exception as e:
                print(f"[Proactive] 检测异常: {e}")
            # 等待间隔
            self._stop_event.wait(self.check_interval)

    # ============================================================
    # 检测逻辑
    # ============================================================

    def _check_all(self):
        """执行所有检测项"""
        # 检查是否静默时段
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
        """检查是否在静默时段"""
        if not self.quiet_hours or len(self.quiet_hours) < 2:
            return False
        hour = time.localtime().tm_hour
        start, end = self.quiet_hours
        if start > end:  # 跨午夜，如 23-7
            return hour >= start or hour < end
        return start <= hour < end

    def _check_system_resources(self):
        """检查系统资源，预测性维护建议"""
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
            # 限制历史长度
            if len(self._system_history) > 100:
                self._system_history = self._system_history[-80:]

            # 内存不足预警（>85%）
            if memory.percent > 85:
                self._suggest(
                    type="performance",
                    title="⚠️ 内存不足预警",
                    description=f"当前内存使用率 {memory.percent:.1f}%，建议关闭不必要的后台程序",
                    confidence=min(memory.percent / 100, 0.95),
                    suggested_action="关闭后台浏览器标签页",
                )

            # CPU 瓶颈预警（>90% 持续）
            recent_cpu = [s["cpu"] for s in self._system_history[-10:]]
            if len(recent_cpu) >= 5 and sum(recent_cpu) / len(recent_cpu) > 90:
                self._suggest(
                    type="performance",
                    title="🔥 CPU 负载过高",
                    description=f"CPU 平均使用率 {sum(recent_cpu)/len(recent_cpu):.1f}%，检测到系统卡顿",
                    confidence=0.85,
                    suggested_action="结束CPU占用最高的进程",
                )

            # 磁盘空间预警（<10GB 或 >90%）
            free_gb = disk.free / (1024**3)
            if free_gb < 10 or disk.percent > 90:
                self._suggest(
                    type="performance",
                    title="💾 磁盘空间不足",
                    description=f"剩余空间仅 {free_gb:.1f}GB，建议清理临时文件",
                    confidence=0.9,
                    suggested_action="清理临时文件和回收站",
                )

        except ImportError:
            pass

    def _check_context_awareness(self):
        """上下文感知：根据当前应用推断用户意图"""
        # 获取当前活跃窗口（简化实现，实际可用pygetwindow等）
        # 这里基于系统监控推断
        try:
            import psutil

            # 检查是否有PPT进程
            for proc in psutil.process_iter(['name']):
                name = proc.info['name']
                if name and ('powerpnt' in name.lower() or 'presentation' in name.lower()):
                    self._suggest(
                        type="context",
                        title="📊 PPT 辅助建议",
                        description="检测到你正在制作PPT，是否需要调用模板或数据？",
                        confidence=0.7,
                        suggested_action="打开PPT模板库",
                    )
                    break

                # 检查是否有Excel进程
                if name and ('excel' in name.lower()):
                    self._suggest(
                        type="context",
                        title="📈 Excel 数据助手",
                        description="检测到你正在处理表格，是否需要生成图表或数据透视？",
                        confidence=0.7,
                        suggested_action="生成数据可视化图表",
                    )
                    break

        except ImportError:
            pass

    def _check_smart_schedule(self):
        """智能日程提醒"""
        # 简化的日程提醒（基于时间模式）
        now = time.localtime()
        hour = now.tm_hour
        minute = now.tm_min

        # 早上提醒（8:00-8:05）
        if hour == 8 and 0 <= minute <= 5:
            self._suggest(
                type="schedule",
                title="🌅 早安提醒",
                description="新的一天开始了。今日待办事项已就绪，是否需要查看？",
                confidence=0.8,
                suggested_action="查看今日日程",
            )

        # 午餐提醒（12:00-12:05）
        if hour == 12 and 0 <= minute <= 5:
            self._suggest(
                type="schedule",
                title="🍜 午餐提醒",
                description="已工作一上午，建议休息片刻。",
                confidence=0.6,
                suggested_action=None,  # 纯提醒，不操作
            )

        # 下班提醒（17:30-17:35）
        if hour == 17 and 30 <= minute <= 35:
            self._suggest(
                type="schedule",
                title="🌆 下班提醒",
                description="工作即将结束，建议保存未保存的文件。",
                confidence=0.7,
                suggested_action="保存所有未保存文档",
            )

    # ============================================================
    # 建议生成
    # ============================================================

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
        生成主动建议
        带冷却时间，避免重复建议
        """
        suggestion_key = f"{type}:{title}"
        now = time.time()

        # 检查冷却时间
        last_time = self._last_suggestion_time.get(suggestion_key, 0)
        if now - last_time < self._suggestion_cooldown:
            return

        # 仅高置信度日常操作可自动执行
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

        # 自动执行（仅限高置信度日常操作）
        if auto_execute:
            print(f"[Proactive] ⚡ 自动执行: {suggested_action}")
            # 实际执行交给 executor 模块

        print(f"[Proactive] 💡 {title} ({confidence:.0%}置信度): {description}")

    # ============================================================
    # 跨域信息整合（进化卷一）
    # ============================================================

    def prepare_briefing(self, topic: str) -> Dict:
        """
        根据模糊指令整合多源信息生成 briefing
        例如："帮我准备下周见客户的资料"
        """
        result = {
            "topic": topic,
            "sources": [],
            "summary": "",
            "suggested_actions": [],
        }

        # 1. 搜索本地文档
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

        # 2. 检查最近修改的文件（跨应用）
        # 这里简化处理，实际可扫描常见文档目录

        # 3. 生成建议
        result["summary"] = f"已为您整合'{topic}'相关资源。建议："
        result["suggested_actions"] = [
            "打开相关文档整理",
            "生成PPT大纲",
            "发送邮件确认会议时间",
        ]

        return result

    # ============================================================
    # 状态查询
    # ============================================================

    def get_pending_suggestions(self) -> List[ProactiveSuggestion]:
        """获取未处理的建议"""
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
