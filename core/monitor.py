#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 系统监控模块（观星术）
实时监测 CPU、内存、磁盘、网络，主动预警系统资源瓶颈。
Phase 1 实现基础桩，后续扩展告警与主动干预。
"""

import threading
import time
from typing import Dict, Optional


class SystemMonitor:
    """系统资源监控器"""

    def __init__(self, config: Dict, root_path):
        self.config = config
        self.root_path = root_path
        self.interval = config.get("interval_seconds", 5)
        self.cpu_threshold = config.get("cpu_threshold", 85)
        self.memory_threshold = config.get("memory_threshold", 85)
        self.disk_threshold = config.get("disk_threshold", 90)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._latest_stats: Dict = {}

        # 尝试导入 psutil，如果未安装则降级为占位
        try:
            import psutil
            self._psutil = psutil
            self._available = True
        except ImportError:
            self._psutil = None
            self._available = False

    def _collect(self) -> Dict:
        """采集系统指标"""
        if not self._available:
            return {"status": "psutil 未安装，监控不可用"}

        psutil = self._psutil
        stats = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": psutil.virtual_memory()._asdict(),
            "disk": {},
            "network": {},
        }

        # 磁盘（监控灵枢所在盘）
        try:
            disk_usage = psutil.disk_usage(str(self.root_path))
            stats["disk"][str(self.root_path)] = {
                "total_gb": round(disk_usage.total / (1024**3), 2),
                "used_gb": round(disk_usage.used / (1024**3), 2),
                "free_gb": round(disk_usage.free / (1024**3), 2),
                "percent": disk_usage.percent,
            }
        except Exception as e:
            stats["disk"]["error"] = str(e)

        # 网络（简单统计）
        try:
            net_io = psutil.net_io_counters()
            stats["network"] = {
                "bytes_sent_mb": round(net_io.bytes_sent / (1024**2), 2),
                "bytes_recv_mb": round(net_io.bytes_recv / (1024**2), 2),
            }
        except Exception as e:
            stats["network"]["error"] = str(e)

        return stats

    def _check_alerts(self, stats: Dict):
        """检查是否需要告警"""
        alerts = []
        if "cpu_percent" in stats and stats["cpu_percent"] > self.cpu_threshold:
            alerts.append(f"CPU 使用率告警: {stats['cpu_percent']}% > {self.cpu_threshold}%")

        if "memory" in stats and stats["memory"].get("percent", 0) > self.memory_threshold:
            alerts.append(f"内存使用率告警: {stats['memory']['percent']}% > {self.memory_threshold}%")

        for path, disk_info in stats.get("disk", {}).items():
            if isinstance(disk_info, dict) and disk_info.get("percent", 0) > self.disk_threshold:
                alerts.append(f"磁盘告警 [{path}]: {disk_info['percent']}% > {self.disk_threshold}%")

        return alerts

    def _loop(self):
        """后台监控线程"""
        while self._running:
            try:
                stats = self._collect()
                self._latest_stats = stats
                alerts = self._check_alerts(stats)
                for alert in alerts:
                    print(f"[观星术 ⚠️] {alert}")
            except Exception as e:
                print(f"[观星术 ❌] 监控异常: {e}")
            time.sleep(self.interval)

    def start(self):
        """启动后台监控线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="LingShu-Monitor")
        self._thread.start()

    def stop(self):
        """停止监控线程"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def get_stats(self) -> Dict:
        """获取最新统计"""
        return self._latest_stats.copy()

    def print_status(self):
        """打印当前状态到终端"""
        stats = self.get_stats()
        if not stats:
            print("暂无监控数据")
            return

        print("\n--- 系统状态（观星术）---")
        if "status" in stats:
            print(f"  状态: {stats['status']}")
            return

        print(f"  时间: {stats.get('timestamp', '-')}")
        print(f"  CPU:  {stats.get('cpu_percent', '-'):.1f}%")
        mem = stats.get("memory", {})
        print(f"  内存: {mem.get('percent', '-'):.1f}% ({mem.get('used', 0)//(1024**2)}MB / {mem.get('total', 0)//(1024**2)}MB)")
        for path, disk_info in stats.get("disk", {}).items():
            if isinstance(disk_info, dict):
                print(f"  磁盘 [{path}]: {disk_info['percent']}% 已用 ({disk_info['used_gb']}GB / {disk_info['total_gb']}GB)")
        print("------------------------\n")
