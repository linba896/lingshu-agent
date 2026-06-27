#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 性能监控测试
覆盖：PerformanceMonitor、MetricsCollector、MetricValue、MetricAlert、TraceSpan
"""

import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.metrics import (
    PerformanceMonitor,
    MetricsCollector,
    MetricValue,
    MetricAlert,
    MetricType,
    AlertSeverity,
    TraceSpan,
)


@pytest.fixture
def temp_root():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def collector():
    return MetricsCollector(max_history=1000)


class TestMetricValue:
    """测试指标值"""

    def test_create(self):
        metric = MetricValue(
            name="cpu_percent",
            value=50.0,
            metric_type=MetricType.GAUGE,
            timestamp=time.time(),
            labels={"source": "system"},
            unit="%",
        )
        assert metric.name == "cpu_percent"
        assert metric.value == 50.0

    def test_to_dict(self):
        metric = MetricValue(
            name="cpu_percent",
            value=50.0,
            metric_type=MetricType.GAUGE,
            timestamp=time.time(),
        )
        d = metric.to_dict()
        assert d["name"] == "cpu_percent"
        assert d["value"] == 50.0
        assert d["type"] == "gauge"
        assert "datetime" in d

    def test_metric_types(self):
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.TIMER.value == "timer"
        assert MetricType.RATE.value == "rate"


class TestMetricAlert:
    """测试告警"""

    def test_create(self):
        alert = MetricAlert(
            alert_id="alert_1",
            metric_name="cpu_percent",
            severity=AlertSeverity.WARNING,
            message="CPU 使用率超过阈值",
            threshold=70.0,
            actual_value=85.0,
            timestamp=time.time(),
        )
        assert alert.alert_id == "alert_1"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.resolved == False

    def test_to_dict(self):
        alert = MetricAlert(
            alert_id="a1",
            metric_name="cpu",
            severity=AlertSeverity.CRITICAL,
            message="test",
            threshold=90.0,
            actual_value=95.0,
            timestamp=time.time(),
        )
        d = alert.to_dict()
        assert d["severity"] == "critical"
        assert d["resolved"] == False


class TestTraceSpan:
    """测试追踪跨度"""

    def test_duration(self):
        span = TraceSpan(
            span_id="span_1",
            trace_id="trace_1",
            operation="test_op",
            start_time=time.time(),
        )
        time.sleep(0.01)
        span.end_time = time.time()
        assert span.duration_ms >= 10

    def test_to_dict(self):
        span = TraceSpan(
            span_id="s1",
            trace_id="t1",
            operation="op",
            start_time=100.0,
            end_time=110.0,
            tags={"key": "value"},
        )
        d = span.to_dict()
        assert d["span_id"] == "s1"
        assert d["duration_ms"] == 10000.0
        assert d["tags"]["key"] == "value"


class TestMetricsCollector:
    """测试指标采集器"""

    def test_record_gauge(self, collector):
        collector.record("cpu", 50.0, MetricType.GAUGE)
        latest = collector.get_latest("cpu")
        assert latest is not None
        assert latest.value == 50.0

    def test_gauge_helper(self, collector):
        collector.gauge("memory", 75.0, labels={"node": "main"})
        latest = collector.get_latest("memory", labels={"node": "main"})
        assert latest.value == 75.0

    def test_counter(self, collector):
        collector.counter("requests", 1)
        collector.counter("requests", 1)
        assert collector.get_counter("requests") == 2

    def test_timer(self, collector):
        collector.timer("api_call", 100.0)
        latest = collector.get_latest("api_call")
        assert latest.value == 100.0

    def test_rate(self, collector):
        collector.rate("qps", 100.0)
        latest = collector.get_latest("qps")
        assert latest.value == 100.0

    def test_get_history(self, collector):
        for i in range(5):
            collector.gauge("metric", float(i))

        history = collector.get_history("metric")
        assert len(history) == 5
        assert history[0].value == 0.0
        assert history[-1].value == 4.0

    def test_get_stats(self, collector):
        for i in range(100):
            collector.gauge("metric", float(i))

        stats = collector.get_stats("metric")
        assert stats["count"] == 100
        assert stats["min"] == 0.0
        assert stats["max"] == 99.0
        assert stats["mean"] == 49.5
        assert stats["latest"] == 99.0
        assert "p50" in stats
        assert "p95" in stats
        assert "p99" in stats

    def test_clear(self, collector):
        collector.gauge("a", 1.0)
        collector.gauge("b", 2.0)
        collector.clear("a")
        assert collector.get_latest("a") is None
        assert collector.get_latest("b") is not None

    def test_clear_all(self, collector):
        collector.gauge("a", 1.0)
        collector.clear()
        assert collector.get_latest("a") is None

    def test_get_all_metrics(self, collector):
        collector.gauge("cpu", 1.0)
        collector.gauge("memory", 2.0)
        names = collector.get_all_metrics()
        assert sorted(names) == ["cpu", "memory"]

    def test_export_json(self, collector):
        collector.gauge("test", 42.0)
        json_str = collector.export_json()
        assert isinstance(json_str, str)
        assert "test" in json_str

    def test_export_to_file(self, collector, temp_root):
        collector.gauge("test", 42.0)
        filepath = temp_root / "metrics.json"
        collector.export_json(filepath)
        assert filepath.exists()

    def test_labels_isolation(self, collector):
        collector.gauge("cpu", 50.0, labels={"node": "a"})
        collector.gauge("cpu", 60.0, labels={"node": "b"})

        a = collector.get_latest("cpu", labels={"node": "a"})
        b = collector.get_latest("cpu", labels={"node": "b"})
        assert a.value == 50.0
        assert b.value == 60.0

    def test_max_history(self):
        c = MetricsCollector(max_history=5)
        for i in range(10):
            c.gauge("metric", float(i))
        history = c.get_history("metric")
        assert len(history) == 5
        assert history[0].value == 5.0
        assert history[-1].value == 9.0


class TestPerformanceMonitor:
    """测试性能监控器"""

    def test_init(self, temp_root):
        monitor = PerformanceMonitor(temp_root)
        assert monitor is not None
        assert monitor.collector is not None

    def test_start_stop(self, temp_root):
        monitor = PerformanceMonitor(temp_root)
        monitor.start()
        assert monitor._collector_running == True
        monitor.stop()
        assert monitor._collector_running == False

    def test_alert_thresholds(self, temp_root):
        monitor = PerformanceMonitor(temp_root)
        assert "cpu_percent" in monitor._thresholds
        assert "memory_percent" in monitor._thresholds
        assert monitor._thresholds["cpu_percent"]["warning"] == 70

    def test_custom_thresholds(self, temp_root):
        monitor = PerformanceMonitor(
            temp_root,
            config={
                "thresholds": {
                    "cpu_percent": {"warning": 60, "critical": 80}
                }
            }
        )
        assert monitor._thresholds["cpu_percent"]["warning"] == 60

    def test_trace(self, temp_root):
        monitor = PerformanceMonitor(temp_root)
        with monitor.trace("test_operation") as span:
            time.sleep(0.01)
        assert span.duration_ms >= 10

    def test_trace_with_tags(self, temp_root):
        monitor = PerformanceMonitor(temp_root)
        with monitor.trace("op", tags={"module": "test"}) as span:
            pass
        assert span.tags["module"] == "test"

    def test_alert_handler_registration(self, temp_root):
        monitor = PerformanceMonitor(temp_root)
        alerts = []

        def handler(alert):
            alerts.append(alert)

        monitor.add_alert_handler(handler)
        assert len(monitor._alert_handlers) == 1

    def test_report_generation(self, temp_root):
        monitor = PerformanceMonitor(temp_root)
        # 记录一些指标
        monitor.collector.gauge("cpu", 50.0)
        monitor.collector.gauge("memory", 60.0)
        report = monitor.generate_report(format="json")
        assert isinstance(report, str)
        assert "cpu" in report or "metrics" in report

    def test_baseline(self, temp_root):
        monitor = PerformanceMonitor(temp_root)
        result = monitor.baseline("test_op", lambda: 42)
        assert result == 42

    def test_collection_interval(self, temp_root):
        monitor = PerformanceMonitor(temp_root, config={"collection_interval_seconds": 1.0})
        assert monitor._collection_interval == 1.0

    def test_alert_severity_levels(self):
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"
        assert AlertSeverity.EMERGENCY.value == "emergency"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
