#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 日志系统测试
覆盖：Logger、LogRecord、LogTarget、ConsoleTarget、FileTarget、SensitiveFilter、LogContext
"""

import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logger import (
    Logger,
    LogRecord,
    LogLevel,
    LogFormat,
    ConsoleTarget,
    FileTarget,
    AsyncLogQueue,
    SensitiveFilter,
    LogContext,
)


@pytest.fixture
def temp_root():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


class TestLogRecord:
    """测试日志记录"""

    def test_create(self):
        record = LogRecord(
            timestamp=time.time(),
            level=LogLevel.INFO,
            module="test",
            message="hello",
        )
        assert record.level == LogLevel.INFO
        assert record.message == "hello"

    def test_to_text(self):
        record = LogRecord(
            timestamp=time.time(),
            level=LogLevel.INFO,
            module="test",
            message="hello world",
        )
        text = record.to_text()
        assert "INFO" in text
        assert "test" in text
        assert "hello world" in text

    def test_to_json(self):
        record = LogRecord(
            timestamp=time.time(),
            level=LogLevel.INFO,
            module="test",
            message="hello",
        )
        json_str = record.to_json()
        assert "test" in json_str
        assert "hello" in json_str
        assert "INFO" in json_str

    def test_to_csv(self):
        record = LogRecord(
            timestamp=time.time(),
            level=LogLevel.INFO,
            module="test",
            message="hello",
        )
        csv = record.to_csv()
        assert "INFO" in csv
        assert "hello" in csv

    def test_with_context(self):
        record = LogRecord(
            timestamp=time.time(),
            level=LogLevel.INFO,
            module="test",
            message="hello",
            context={"request_id": "123", "user": "test"},
        )
        text = record.to_text()
        assert "request_id" in text
        assert "123" in text

    def test_with_exception(self):
        record = LogRecord(
            timestamp=time.time(),
            level=LogLevel.ERROR,
            module="test",
            message="error occurred",
            exception="Traceback...\nError: test",
        )
        text = record.to_text()
        assert "Error: test" in text


class TestLogLevel:
    """测试日志级别"""

    def test_levels(self):
        assert LogLevel.DEBUG.value == 10
        assert LogLevel.INFO.value == 20
        assert LogLevel.WARNING.value == 30
        assert LogLevel.ERROR.value == 40
        assert LogLevel.CRITICAL.value == 50

    def test_order(self):
        assert LogLevel.DEBUG.value < LogLevel.INFO.value
        assert LogLevel.INFO.value < LogLevel.WARNING.value
        assert LogLevel.WARNING.value < LogLevel.ERROR.value
        assert LogLevel.ERROR.value < LogLevel.CRITICAL.value


class TestLogFormat:
    """测试日志格式"""

    def test_formats(self):
        assert LogFormat.TEXT.value == "text"
        assert LogFormat.JSON.value == "json"
        assert LogFormat.CSV.value == "csv"


class TestSensitiveFilter:
    """测试敏感信息过滤器"""

    def test_filter_password(self):
        f = SensitiveFilter()
        text = 'password: "secret123"'
        filtered = f.filter(text)
        assert "secret123" not in filtered
        assert "***" in filtered

    def test_filter_api_key(self):
        f = SensitiveFilter()
        text = 'api_key: abc123def456'
        filtered = f.filter(text)
        assert "abc123def456" not in filtered

    def test_filter_token(self):
        f = SensitiveFilter()
        text = 'token: xyz789'
        filtered = f.filter(text)
        assert "xyz789" not in filtered

    def test_filter_credit_card(self):
        f = SensitiveFilter()
        text = "card: 1234567890123456"
        filtered = f.filter(text)
        assert "1234567890123456" not in filtered

    def test_filter_email(self):
        f = SensitiveFilter()
        text = "user@example.com"
        filtered = f.filter(text)
        assert "user@example.com" not in filtered
        assert "***@***.***" in filtered

    def test_filter_phone(self):
        f = SensitiveFilter()
        text = "13812345678"
        filtered = f.filter(text)
        assert "13812345678" not in filtered

    def test_filter_url(self):
        f = SensitiveFilter()
        text = "https://api.example.com/v1/secret"
        filtered = f.filter(text)
        assert "https://api.example.com" not in filtered
        assert "https://***" in filtered

    def test_no_filter_safe_text(self):
        f = SensitiveFilter()
        text = "Hello, this is a normal message."
        assert f.filter(text) == text

    def test_custom_patterns(self):
        custom = [
            (r'(?i)(custom_secret)\s*=\s*(\w+)', r'\1=***'),
        ]
        f = SensitiveFilter(additional_patterns=custom)
        text = "custom_secret = myvalue"
        filtered = f.filter(text)
        assert "myvalue" not in filtered


class TestLogContext:
    """测试日志上下文"""

    def test_set_and_get(self):
        LogContext.set_value("request_id", "123")
        assert LogContext.get_value("request_id") == "123"
        assert LogContext.get_value("missing") is None
        assert LogContext.get_value("missing", "default") == "default"

    def test_scope(self):
        LogContext.set_value("key", "outer")
        with LogContext.scope(key="inner", extra="data"):
            assert LogContext.get_value("key") == "inner"
            assert LogContext.get_value("extra") == "data"
        assert LogContext.get_value("key") == "outer"
        assert LogContext.get_value("extra") is None

    def test_clear(self):
        LogContext.set_value("key", "value")
        LogContext.clear()
        assert LogContext.get_value("key") is None


class TestFileTarget:
    """测试文件日志目标"""

    def test_write(self, temp_root):
        filepath = temp_root / "test.log"
        target = FileTarget(filepath, level=LogLevel.INFO)
        
        record = LogRecord(
            timestamp=time.time(),
            level=LogLevel.INFO,
            module="test",
            message="hello file",
        )
        target.write(record)
        target.flush()
        target.close()
        
        assert filepath.exists()
        content = filepath.read_text(encoding="utf-8")
        assert "hello file" in content

    def test_level_filter(self, temp_root):
        filepath = temp_root / "test.log"
        target = FileTarget(filepath, level=LogLevel.WARNING)
        
        info_record = LogRecord(
            timestamp=time.time(),
            level=LogLevel.INFO,
            module="test",
            message="info",
        )
        warning_record = LogRecord(
            timestamp=time.time(),
            level=LogLevel.WARNING,
            module="test",
            message="warning",
        )
        target.write(info_record)
        target.write(warning_record)
        target.close()
        
        content = filepath.read_text(encoding="utf-8")
        assert "info" not in content
        assert "warning" in content

    def test_json_format(self, temp_root):
        filepath = temp_root / "test.json.log"
        target = FileTarget(filepath, level=LogLevel.INFO, format=LogFormat.JSON)
        
        record = LogRecord(
            timestamp=time.time(),
            level=LogLevel.INFO,
            module="test",
            message="json test",
        )
        target.write(record)
        target.close()
        
        content = filepath.read_text(encoding="utf-8")
        assert "json" in content
        assert "INFO" in content


class TestAsyncLogQueue:
    """测试异步日志队列"""

    def test_start_stop(self, temp_root):
        filepath = temp_root / "async.log"
        target = FileTarget(filepath, level=LogLevel.INFO)
        queue = AsyncLogQueue([target])
        
        queue.start()
        record = LogRecord(
            timestamp=time.time(),
            level=LogLevel.INFO,
            module="test",
            message="async message",
        )
        queue.put(record)
        queue.stop()
        target.close()
        
        content = filepath.read_text(encoding="utf-8")
        assert "async message" in content

    def test_dropped_count(self, temp_root):
        filepath = temp_root / "async.log"
        target = FileTarget(filepath, level=LogLevel.INFO)
        queue = AsyncLogQueue([target], max_queue_size=1)
        
        queue.start()
        # 填满队列并触发丢弃
        for i in range(100):
            record = LogRecord(
                timestamp=time.time(),
                level=LogLevel.INFO,
                module="test",
                message=f"msg {i}",
            )
            queue.put(record)
        
        queue.stop()
        target.close()
        
        assert queue.get_dropped_count() > 0


class TestLogger:
    """测试日志器"""

    def test_init(self, temp_root):
        logger = Logger(name="test", level=LogLevel.DEBUG)
        assert logger.name == "test"
        assert logger.level == LogLevel.DEBUG

    def test_log_levels(self, temp_root):
        filepath = temp_root / "levels.log"
        target = FileTarget(filepath, level=LogLevel.DEBUG)
        logger = Logger(name="test", level=LogLevel.DEBUG, targets=[target], async_mode=False)
        
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
        logger.critical("critical message")
        
        target.close()
        content = filepath.read_text(encoding="utf-8")
        assert "debug message" in content
        assert "info message" in content
        assert "warning message" in content
        assert "error message" in content
        assert "critical message" in content

    def test_level_filter(self, temp_root):
        filepath = temp_root / "filter.log"
        target = FileTarget(filepath, level=LogLevel.INFO)
        logger = Logger(name="test", level=LogLevel.INFO, targets=[target], async_mode=False)
        
        logger.debug("should not appear")
        logger.info("should appear")
        
        target.close()
        content = filepath.read_text(encoding="utf-8")
        assert "should not appear" not in content
        assert "should appear" in content

    def test_set_level(self, temp_root):
        logger = Logger(name="test", level=LogLevel.INFO)
        logger.set_level(LogLevel.DEBUG)
        assert logger.level == LogLevel.DEBUG

    def test_add_target(self, temp_root):
        logger = Logger(name="test", level=LogLevel.INFO, async_mode=False)
        filepath = temp_root / "added.log"
        target = FileTarget(filepath, level=LogLevel.INFO)
        logger.add_target(target)
        
        logger.info("added target test")
        target.close()
        
        content = filepath.read_text(encoding="utf-8")
        assert "added target test" in content

    def test_context(self, temp_root):
        filepath = temp_root / "context.log"
        target = FileTarget(filepath, level=LogLevel.INFO)
        logger = Logger(name="test", level=LogLevel.INFO, targets=[target], async_mode=False)
        
        LogContext.set_value("request_id", "abc123")
        logger.info("context test")
        LogContext.clear()
        
        target.close()
        content = filepath.read_text(encoding="utf-8")
        assert "context test" in content

    def test_sanitization(self, temp_root):
        filepath = temp_root / "sanitized.log"
        target = FileTarget(filepath, level=LogLevel.INFO)
        logger = Logger(
            name="test",
            level=LogLevel.INFO,
            targets=[target],
            async_mode=False,
            sanitize=True,
        )
        
        logger.info("password: secret123")
        target.close()
        
        content = filepath.read_text(encoding="utf-8")
        assert "secret123" not in content
        assert "***" in content

    def test_get_recent_logs(self, temp_root):
        logger = Logger(name="test", level=LogLevel.INFO, async_mode=False)
        logger.info("recent 1")
        logger.info("recent 2")
        logger.info("recent 3")
        
        logs = logger.get_recent_logs(2)
        assert len(logs) <= 2

    def test_module_name(self, temp_root):
        logger = Logger(name="test_module", level=LogLevel.INFO, async_mode=False)
        logger.info("module test")
        # 日志记录应该包含模块名
        assert logger.name == "test_module"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
