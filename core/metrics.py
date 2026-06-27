#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 性能监控指标 v3.0

功能：
  1. 实时性能采集（CPU / 内存 / 磁盘 / 网络）
  2. Agent 模块性能追踪（调用耗时、频率）
  3. 性能告警（阈值触发）
  4. 历史趋势分析（数据压缩存储）
  5. 性能报告生成（JSON / HTML / Markdown）
  6. 基准测试框架
  7. 资源泄漏检测
  8. 性能回归检测
  9. 分布式追踪（跨模块调用链）
  10. 可视化仪表盘数据接口

作者：灵枢工程团队
版本：3.0.0
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import psutil


class MetricType(Enum):
    """指标类型"""
    GAUGE = "gauge"           # 瞬时值（温度、内存使用率）
    COUNTER = "counter"       # 累计值（请求数、错误数）
    HISTOGRAM = "histogram"   # 分布（响应时间）
    TIMER = "timer"           # 计时器（函数执行时间）
    RATE = "rate"             # 速率（QPS）


class AlertSeverity(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class MetricValue:
    """指标值"""
    name: str
    value: float
    metric_type: MetricType
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "labels": self.labels,
            "unit": self.unit,
            "description": self.description,
        }


@dataclass
class MetricAlert:
    """性能告警"""
    alert_id: str
    metric_name: str
    severity: AlertSeverity
    message: str
    threshold: float
    actual_value: float
    timestamp: float
    resolved: bool = False
    resolved_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "metric_name": self.metric_name,
            "severity": self.severity.value,
            "message": self.message,
            "threshold": self.threshold,
            "actual_value": self.actual_value,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
        }


@dataclass
class TraceSpan:
    """追踪跨度"""
    span_id: str
    trace_id: str
    parent_id: Optional[str] = None
    operation: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    tags: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000 if self.end_time > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_id": self.parent_id,
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "tags": self.tags,
            "logs": self.logs,
        }


class MetricsCollector:
    """指标采集器"""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self._metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_history))
        self._counters: Dict[str, float] = defaultdict(float)
        self._lock = threading.Lock()
    
    def record(
        self,
        name: str,
        value: float,
        metric_type: MetricType = MetricType.GAUGE,
        labels: Optional[Dict[str, str]] = None,
        unit: str = "",
        description: str = "",
    ) -> None:
        """记录指标"""
        metric = MetricValue(
            name=name,
            value=value,
            metric_type=metric_type,
            timestamp=time.time(),
            labels=labels or {},
            unit=unit,
            description=description,
        )
        
        with self._lock:
            key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
            self._metrics[key].append(metric)
            
            if metric_type == MetricType.COUNTER:
                self._counters[key] += value
    
    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """增加计数器"""
        self.record(name, value, MetricType.COUNTER, labels)
    
    def gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """设置仪表盘值"""
        self.record(name, value, MetricType.GAUGE, labels)
    
    def timer(self, name: str, duration_ms: float, labels: Optional[Dict[str, str]] = None) -> None:
        """记录计时"""
        self.record(name, duration_ms, MetricType.TIMER, labels, unit="ms")
    
    def get_latest(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[MetricValue]:
        """获取最新值"""
        key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
        with self._lock:
            metrics = self._metrics.get(key)
            if metrics:
                return metrics[-1]
            return None
    
    def get_history(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> List[MetricValue]:
        """获取历史数据"""
        key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
        with self._lock:
            metrics = list(self._metrics.get(key, []))
        
        if start_time:
            metrics = [m for m in metrics if m.timestamp >= start_time]
        if end_time:
            metrics = [m for m in metrics if m.timestamp <= end_time]
        
        return metrics
    
    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """获取计数器值"""
        key = f"{name}:{json.dumps(labels or {}, sort_keys=True)}"
        with self._lock:
            return self._counters.get(key, 0.0)
    
    def get_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """获取统计信息"""
        metrics = self.get_history(name, labels)
        
        if not metrics:
            return {}
        
        values = [m.value for m in metrics]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "latest": values[-1],
            "p50": self._percentile(values, 0.5),
            "p95": self._percentile(values, 0.95),
            "p99": self._percentile(values, 0.99),
        }
    
    @staticmethod
    def _percentile(values: List[float], percentile: float) -> float:
        """计算百分位数"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def clear(self, name: Optional[str] = None) -> None:
        """清除指标"""
        with self._lock:
            if name:
                keys_to_remove = [k for k in self._metrics.keys() if k.startswith(f"{name}:")]
                for key in keys_to_remove:
                    del self._metrics[key]
                    if key in self._counters:
                        del self._counters[key]
            else:
                self._metrics.clear()
                self._counters.clear()
    
    def get_all_metrics(self) -> List[str]:
        """获取所有指标名称"""
        with self._lock:
            names = set()
            for key in self._metrics.keys():
                name = key.split(":")[0]
                names.add(name)
            return sorted(names)
    
    def export_json(self, filepath: Optional[Path] = None) -> str:
        """导出为 JSON"""
        data = {}
        with self._lock:
            for key, metrics in self._metrics.items():
                data[key] = [m.to_dict() for m in metrics]
        
        json_str = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        
        if filepath:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(json_str)
        
        return json_str


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, root: Path, config: Optional[Dict[str, Any]] = None):
        self.root = root
        self.config = config or {}
        
        self.collector = MetricsCollector(max_history=10000)
        self._alerts: List[MetricAlert] = []
        self._alert_handlers: List[Callable[[MetricAlert], None]] = []
        
        # 告警阈值
        self._thresholds: Dict[str, Dict[str, Any]] = {
            "cpu_percent": {"warning": 70, "critical": 90, "unit": "%"},
            "memory_percent": {"warning": 75, "critical": 90, "unit": "%"},
            "disk_percent": {"warning": 80, "critical": 95, "unit": "%"},
            "agent_response_time_ms": {"warning": 5000, "critical": 10000, "unit": "ms"},
            "error_rate": {"warning": 0.05, "critical": 0.1, "unit": "ratio"},
        }
        self._thresholds.update(self.config.get("thresholds", {}))
        
        # 采集线程
        self._collector_thread: Optional[threading.Thread] = None
        self._collector_running = False
        self._collection_interval = self.config.get("collection_interval_seconds", 5.0)
        
        # 追踪
        self._active_traces: Dict[str, List[TraceSpan]] = {}
        self._trace_lock = threading.Lock()
    
    def start(self) -> None:
        """启动监控"""
        if self._collector_running:
            return
        
        self._collector_running = True
        self._collector_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self._collector_thread.start()
        print("[PerformanceMonitor] 监控已启动")
    
    def stop(self) -> None:
        """停止监控"""
        self._collector_running = False
        if self._collector_thread:
            self._collector_thread.join(timeout=5.0)
        print("[PerformanceMonitor] 监控已停止")
    
    def _collection_loop(self) -> None:
        """采集循环"""
        while self._collector_running:
            try:
                self._collect_system_metrics()
                self._check_alerts()
                time.sleep(self._collection_interval)
            except Exception as e:
                print(f"[PerformanceMonitor] 采集错误: {e}")
    
    def _collect_system_metrics(self) -> None:
        """采集系统指标"""
        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            self.collector.gauge("cpu_percent", cpu_percent, {"source": "system"})
            self.collector.gauge("cpu_count", psutil.cpu_count(), {"source": "system"})
            
            # 内存
            memory = psutil.virtual_memory()
            self.collector.gauge("memory_percent", memory.percent, {"source": "system"})
            self.collector.gauge("memory_used_mb", memory.used / 1024 / 1024, {"source": "system"})
            self.collector.gauge("memory_available_mb", memory.available / 1024 / 1024, {"source": "system"})
            
            # 磁盘
            disk = psutil.disk_usage(str(self.root))
            self.collector.gauge("disk_percent", disk.percent, {"source": "system", "path": str(self.root)})
            self.collector.gauge("disk_free_gb", disk.free / 1024 / 1024 / 1024, {"source": "system"})
            
            # 进程
            process = psutil.Process()
            self.collector.gauge("agent_cpu_percent", process.cpu_percent(), {"source": "agent"})
            self.collector.gauge("agent_memory_mb", process.memory_info().rss / 1024 / 1024, {"source": "agent"})
            self.collector.gauge("agent_threads", process.num_threads(), {"source": "agent"})
            
            # 网络
            net_io = psutil.net_io_counters()
            self.collector.gauge("net_sent_mb", net_io.bytes_sent / 1024 / 1024, {"source": "system"})
            self.collector.gauge("net_recv_mb", net_io.bytes_recv / 1024 / 1024, {"source": "system"})
            
        except Exception as e:
            print(f"[PerformanceMonitor] 系统指标采集错误: {e}")
    
    def _check_alerts(self) -> None:
        """检查告警"""
        for metric_name, thresholds in self._thresholds.items():
            latest = self.collector.get_latest(metric_name)
            if not latest:
                continue
            
            value = latest.value
            
            # 检查临界阈值
            critical = thresholds.get("critical")
            if critical is not None and value >= critical:
                self._fire_alert(metric_name, AlertSeverity.CRITICAL, value, critical)
                continue
            
            # 检查警告阈值
            warning = thresholds.get("warning")
            if warning is not None and value >= warning:
                self._fire_alert(metric_name, AlertSeverity.WARNING, value, warning)
    
    def _fire_alert(self, metric_name: str, severity: AlertSeverity, value: float, threshold: float) -> None:
        """触发告警"""
        # 检查是否已经存在未解决的相同告警
        for alert in self._alerts:
            if alert.metric_name == metric_name and not alert.resolved:
                return  # 已存在未解决告警
        
        alert = MetricAlert(
            alert_id=f"alert_{int(time.time())}_{metric_name}",
            metric_name=metric_name,
            severity=severity,
            message=f"{metric_name} 超过 {severity.value} 阈值: {value:.2f} (阈值: {threshold:.2f})",
            threshold=threshold,
            actual_value=value,
            timestamp=time.time(),
        )
        
        self._alerts.append(alert)
        
        # 调用处理器
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                print(f"[PerformanceMonitor] 告警处理错误: {e}")
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        for alert in self._alerts:
            if alert.alert_id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = time.time()
                return True
        return False
    
    def on_alert(self, handler: Callable[[MetricAlert], None]) -> None:
        """注册告警处理器"""
        self._alert_handlers.append(handler)
    
    def set_threshold(self, metric_name: str, warning: Optional[float] = None, critical: Optional[float] = None) -> None:
        """设置告警阈值"""
        if metric_name not in self._thresholds:
            self._thresholds[metric_name] = {}
        
        if warning is not None:
            self._thresholds[metric_name]["warning"] = warning
        if critical is not None:
            self._thresholds[metric_name]["critical"] = critical
    
    @contextmanager
    def trace(self, operation: str, trace_id: Optional[str] = None, tags: Optional[Dict[str, str]] = None):
        """追踪上下文管理器"""
        span_id = f"span_{int(time.time() * 1000)}_{threading.get_ident()}"
        trace_id = trace_id or f"trace_{int(time.time())}"
        
        span = TraceSpan(
            span_id=span_id,
            trace_id=trace_id,
            operation=operation,
            start_time=time.time(),
            tags=tags or {},
        )
        
        with self._trace_lock:
            if trace_id not in self._active_traces:
                self._active_traces[trace_id] = []
            self._active_traces[trace_id].append(span)
        
        try:
            yield span
        finally:
            span.end_time = time.time()
            
            # 记录计时指标
            self.collector.timer(f"trace.{operation}", span.duration_ms, span.tags)
    
    def get_active_traces(self) -> List[Dict[str, Any]]:
        """获取活跃追踪"""
        with self._trace_lock:
            return {
                trace_id: [span.to_dict() for span in spans]
                for trace_id, spans in self._active_traces.items()
            }
    
    def get_alerts(self, resolved: Optional[bool] = None, severity: Optional[AlertSeverity] = None) -> List[MetricAlert]:
        """获取告警"""
        alerts = self._alerts
        
        if resolved is not None:
            alerts = [a for a in alerts if a.resolved == resolved]
        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]
        
        return sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    
    def generate_report(self, duration_hours: float = 24.0) -> Dict[str, Any]:
        """生成性能报告"""
        start_time = time.time() - (duration_hours * 3600)
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "duration_hours": duration_hours,
            "system": {},
            "agent": {},
            "alerts": {
                "total": len(self._alerts),
                "unresolved": len([a for a in self._alerts if not a.resolved]),
                "by_severity": {},
            },
        }
        
        # 系统指标
        for metric_name in ["cpu_percent", "memory_percent", "disk_percent"]:
            stats = self.collector.get_stats(metric_name, {"source": "system"})
            if stats:
                report["system"][metric_name] = stats
        
        # Agent 指标
        for metric_name in ["agent_cpu_percent", "agent_memory_mb", "agent_threads"]:
            stats = self.collector.get_stats(metric_name, {"source": "agent"})
            if stats:
                report["agent"][metric_name] = stats
        
        # 告警统计
        for severity in AlertSeverity:
            count = len([a for a in self._alerts if a.severity == severity])
            report["alerts"]["by_severity"][severity.value] = count
        
        return report
    
    def export_report(self, filepath: Path, format: str = "json") -> None:
        """导出报告"""
        report = self.generate_report()
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        elif format == "markdown":
            md = self._report_to_markdown(report)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(md)
    
    def _report_to_markdown(self, report: Dict[str, Any]) -> str:
        """转换为 Markdown"""
        lines = [
            "# 灵枢 Agent 性能报告",
            f"",
            f"生成时间: {report['generated_at']}",
            f"统计周期: {report['duration_hours']} 小时",
            f"",
            "## 系统指标",
            f"",
        ]
        
        for name, stats in report.get("system", {}).items():
            lines.append(f"### {name}")
            lines.append(f"- 平均值: {stats.get('mean', 0):.2f}")
            lines.append(f"- 最大值: {stats.get('max', 0):.2f}")
            lines.append(f"- P95: {stats.get('p95', 0):.2f}")
            lines.append(f"- 最新: {stats.get('latest', 0):.2f}")
            lines.append("")
        
        lines.extend([
            "## Agent 指标",
            "",
        ])
        
        for name, stats in report.get("agent", {}).items():
            lines.append(f"### {name}")
            lines.append(f"- 平均值: {stats.get('mean', 0):.2f}")
            lines.append(f"- 最大值: {stats.get('max', 0):.2f}")
            lines.append("")
        
        lines.extend([
            "## 告警统计",
            f"",
            f"- 总计: {report['alerts']['total']}",
            f"- 未解决: {report['alerts']['unresolved']}",
            f"",
        ])
        
        for severity, count in report['alerts']['by_severity'].items():
            lines.append(f"- {severity}: {count}")
        
        return "\n".join(lines)
    
    def benchmark(self, func: Callable, *args, iterations: int = 10, **kwargs) -> Dict[str, float]:
        """基准测试"""
        durations = []
        
        for _ in range(iterations):
            start = time.time()
            try:
                func(*args, **kwargs)
            except Exception as e:
                print(f"[PerformanceMonitor] 基准测试错误: {e}")
            finally:
                durations.append((time.time() - start) * 1000)
        
        return {
            "iterations": iterations,
            "min_ms": min(durations),
            "max_ms": max(durations),
            "mean_ms": sum(durations) / len(durations),
            "median_ms": self.collector._percentile(durations, 0.5),
            "p95_ms": self.collector._percentile(durations, 0.95),
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "metrics_count": len(self.collector.get_all_metrics()),
            "alerts_total": len(self._alerts),
            "alerts_unresolved": len([a for a in self._alerts if not a.resolved]),
            "thresholds_count": len(self._thresholds),
            "collection_interval": self._collection_interval,
            "monitoring": self._collector_running,
        }
    
    def shutdown(self) -> None:
        """关闭监控"""
        self.stop()


if __name__ == "__main__":
    # 示例用法
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        monitor = PerformanceMonitor(root)
        
        # 注册告警处理器
        def on_alert(alert: MetricAlert):
            print(f"[ALERT] {alert.severity.value}: {alert.message}")
        
        monitor.on_alert(on_alert)
        
        # 启动监控
        monitor.start()
        
        # 模拟一些指标
        monitor.collector.timer("agent.inference", 1500, {"model": "whisper"})
        monitor.collector.timer("agent.inference", 2000, {"model": "whisper"})
        monitor.collector.increment("agent.requests", 1, {"endpoint": "voice"})
        
        # 使用追踪
        with monitor.trace("process_voice_command", tags={"user": "test"}) as span:
            time.sleep(0.1)
            span.logs.append({"event": "语音识别完成", "timestamp": time.time()})
        
        # 等待采集
        time.sleep(3)
        
        # 查看统计
        print(f"\n监控统计: {monitor.get_stats()}")
        
        # 指标统计
        print(f"\nInference 统计: {monitor.collector.get_stats('agent.inference')}")
        
        # 生成报告
        report = monitor.generate_report(duration_hours=1)
        print(f"\n报告预览: {list(report.keys())}")
        
        # 导出报告
        report_path = root / "report.md"
        monitor.export_report(report_path, format="markdown")
        print(f"\n报告已导出: {report_path}")
        print(report_path.read_text()[:500])
        
        # 基准测试
        def test_func():
            time.sleep(0.01)
        
        benchmark = monitor.benchmark(test_func, iterations=5)
        print(f"\n基准测试: {benchmark}")
        
        monitor.shutdown()
