#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 结构化日志系统 v3.0

功能：
  1. 多级别日志（DEBUG/INFO/WARNING/ERROR/CRITICAL）
  2. 多输出目标（控制台、文件、网络、系统日志）
  3. 结构化输出（JSON 格式便于分析）
  4. 日志轮转（按大小/时间自动归档）
  5. 异步写入（高性能非阻塞）
  6. 上下文追踪（请求 ID、会话 ID）
  7. 日志采样（高频率场景降低写入量）
  8. 敏感信息过滤（自动脱敏）
  9. 性能指标记录（执行时间、内存使用）
  10. 日志查询（内存索引，快速检索）

作者：灵枢工程团队
版本：3.0.0
"""

from __future__ import annotations

import functools
import hashlib
import json
import logging
import os
import queue
import re
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union


class LogLevel(Enum):
    """日志级别"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class LogFormat(Enum):
    """日志格式"""
    TEXT = "text"      # 人类可读
    JSON = "json"      # 结构化
    CSV = "csv"        # 表格


class LogTarget:
    """日志输出目标基类"""
    
    def __init__(self, level: LogLevel = LogLevel.DEBUG, format: LogFormat = LogFormat.TEXT):
        self.level = level
        self.format = format
        self._lock = threading.Lock()
    
    def write(self, record: LogRecord) -> None:
        raise NotImplementedError
    
    def flush(self) -> None:
        pass
    
    def close(self) -> None:
        pass
    
    def _format_record(self, record: LogRecord) -> str:
        """格式化记录"""
        if self.format == LogFormat.JSON:
            return record.to_json()
        elif self.format == LogFormat.CSV:
            return record.to_csv()
        else:
            return record.to_text()


@dataclass
class LogRecord:
    """日志记录"""
    timestamp: float
    level: LogLevel
    module: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[str] = None
    source_file: str = ""
    source_line: int = 0
    function: str = ""
    thread_id: int = 0
    process_id: int = 0
    
    def to_text(self) -> str:
        """转换为文本格式"""
        dt = datetime.fromtimestamp(self.timestamp)
        time_str = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        ctx = ""
        if self.context:
            ctx_parts = [f"{k}={v}" for k, v in self.context.items()]
            ctx = " | " + " ".join(ctx_parts)
        
        exc = f"\n{self.exception}" if self.exception else ""
        return f"[{time_str}] [{self.level.name:8}] [{self.module:20}] {self.message}{ctx}{exc}"
    
    def to_json(self) -> str:
        """转换为 JSON 格式"""
        data = {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "level": self.level.name,
            "module": self.module,
            "message": self.message,
            "context": self.context,
            "source": {
                "file": self.source_file,
                "line": self.source_line,
                "function": self.function,
            },
            "thread_id": self.thread_id,
            "process_id": self.process_id,
        }
        if self.exception:
            data["exception"] = self.exception
        return json.dumps(data, ensure_ascii=False, default=str)
    
    def to_csv(self) -> str:
        """转换为 CSV 格式"""
        dt = datetime.fromtimestamp(self.timestamp).isoformat()
        exc = self.exception.replace("\"", "\"\"") if self.exception else ""
        return f"\"{dt}\",\"{self.level.name}\",\"{self.module}\",\"{self.message}\",\"{exc}\""


class ConsoleTarget(LogTarget):
    """控制台输出目标"""
    
    LEVEL_COLORS = {
        LogLevel.DEBUG: "\033[36m",      # 青色
        LogLevel.INFO: "\033[32m",       # 绿色
        LogLevel.WARNING: "\033[33m",  # 黄色
        LogLevel.ERROR: "\033[31m",      # 红色
        LogLevel.CRITICAL: "\033[35m", # 紫色
    }
    RESET = "\033[0m"
    
    def __init__(self, level: LogLevel = LogLevel.INFO, use_color: bool = True, format: LogFormat = LogFormat.TEXT):
        super().__init__(level, format)
        self.use_color = use_color and sys.stdout.isatty()
    
    def write(self, record: LogRecord) -> None:
        if record.level.value < self.level.value:
            return
        
        text = self._format_record(record)
        
        if self.use_color and record.level in self.LEVEL_COLORS:
            color = self.LEVEL_COLORS[record.level]
            text = f"{color}{text}{self.RESET}"
        
        print(text)
    
    def flush(self) -> None:
        sys.stdout.flush()


class FileTarget(LogTarget):
    """文件输出目标"""
    
    def __init__(self, filepath: Path, level: LogLevel = LogLevel.DEBUG, format: LogFormat = LogFormat.TEXT, max_size: int = 10 * 1024 * 1024, max_backups: int = 5, rotate_daily: bool = False):
        super().__init__(level, format)
        self.filepath = Path(filepath)
        self.max_size = max_size
        self.max_backups = max_backups
        self.rotate_daily = rotate_daily
        self._file = None
        self._current_date = datetime.now().date()
        self._open_file()
    
    def _open_file(self) -> None:
        """打开文件"""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.filepath, "a", encoding="utf-8")
    
    def _should_rotate(self) -> bool:
        """检查是否需要轮转"""
        if not self.filepath.exists():
            return False
        
        # 按大小轮转
        if self.filepath.stat().st_size >= self.max_size:
            return True
        
        # 按日期轮转
        if self.rotate_daily and datetime.now().date() != self._current_date:
            return True
        
        return False
    
    def _rotate(self) -> None:
        """执行日志轮转"""
        if self._file:
            self._file.close()
        
        # 移动旧文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = self.filepath.parent / f"{self.filepath.stem}_{timestamp}{self.filepath.suffix}"
        
        if self.filepath.exists():
            shutil.move(str(self.filepath), str(backup))
        
        # 清理旧备份
        self._cleanup_backups()
        
        # 重新打开
        self._current_date = datetime.now().date()
        self._open_file()
    
    def _cleanup_backups(self) -> None:
        """清理旧备份文件"""
        backups = sorted(
            self.filepath.parent.glob(f"{self.filepath.stem}_*{self.filepath.suffix}"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        
        for old in backups[self.max_backups:]:
            old.unlink()
    
    def write(self, record: LogRecord) -> None:
        if record.level.value < self.level.value:
            return
        
        if self._should_rotate():
            self._rotate()
        
        text = self._format_record(record)
        
        with self._lock:
            if self._file:
                self._file.write(text + "\n")
    
    def flush(self) -> None:
        with self._lock:
            if self._file:
                self._file.flush()
    
    def close(self) -> None:
        with self._lock:
            if self._file:
                self._file.close()
                self._file = None


class AsyncLogQueue:
    """异步日志队列"""
    
    def __init__(self, targets: List[LogTarget], max_queue_size: int = 10000):
        self.targets = targets
        self._queue: queue.Queue[Optional[LogRecord]] = queue.Queue(maxsize=max_queue_size)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._dropped_count = 0
    
    def start(self) -> None:
        """启动后台写入线程"""
        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """停止后台线程"""
        self._running = False
        self._queue.put(None)  # 发送结束信号
        if self._thread:
            self._thread.join(timeout=5.0)
    
    def put(self, record: LogRecord) -> None:
        """放入队列"""
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            self._dropped_count += 1
    
    def _process_loop(self) -> None:
        """处理循环"""
        while self._running:
            record = self._queue.get()
            if record is None:
                break
            
            for target in self.targets:
                try:
                    target.write(record)
                except Exception:
                    pass
    
    def flush(self) -> None:
        """刷新所有目标"""
        for target in self.targets:
            target.flush()
    
    def get_dropped_count(self) -> int:
        """获取丢弃数量"""
        return self._dropped_count


class SensitiveFilter:
    """敏感信息过滤器"""
    
    PATTERNS = [
        (r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?[^"\'\s]+["\']?', r'\1: ***'),
        (r'(?i)(api[_-]?key|token|secret)\s*[:=]\s*["\']?[^"\'\s]+["\']?', r'\1: ***'),
        (r'(?i)(authorization|auth)\s*[:=]\s*["\']?[^"\'\s]+["\']?', r'\1: ***'),
        (r'\b\d{16,19}\b', r'**** **** **** ****'),  # 银行卡/信用卡号
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', r'***@***.***'),  # 邮箱
        (r'\b1[3-9]\d{9}\b', r'1**** ****'),  # 手机号
        (r'(?i)(ssh|https?)://[^\s]+', r'\1://***'),
    ]
    
    def __init__(self, additional_patterns: Optional[List[tuple]] = None):
        self._patterns = []
        for pattern, replacement in self.PATTERNS:
            self._patterns.append((re.compile(pattern), replacement))
        
        if additional_patterns:
            for pattern, replacement in additional_patterns:
                self._patterns.append((re.compile(pattern), replacement))
    
    def filter(self, text: str) -> str:
        """过滤敏感信息"""
        for pattern, replacement in self._patterns:
            text = pattern.sub(replacement, text)
        return text


class LogContext:
    """日志上下文管理器"""
    
    _local = threading.local()
    
    @classmethod
    def get_context(cls) -> Dict[str, Any]:
        """获取当前线程上下文"""
        if not hasattr(cls._local, "context"):
            cls._local.context = {}
        return cls._local.context
    
    @classmethod
    def set_value(cls, key: str, value: Any) -> None:
        """设置上下文值"""
        cls.get_context()[key] = value
    
    @classmethod
    def get_value(cls, key: str, default: Any = None) -> Any:
        """获取上下文值"""
        return cls.get_context().get(key, default)
    
    @classmethod
    def clear(cls) -> None:
        """清除上下文"""
        cls._local.context = {}
    
    @classmethod
    @contextmanager
    def scope(cls, **kwargs):
        """上下文作用域"""
        old = cls.get_context().copy()
        cls.get_context().update(kwargs)
        try:
            yield
        finally:
            cls._local.context = old


class Logger:
    """灵枢结构化日志器"""
    
    def __init__(
        self,
        name: str = "lingshu",
        level: LogLevel = LogLevel.INFO,
        targets: Optional[List[LogTarget]] = None,
        async_mode: bool = True,
        sanitize: bool = True,
    ):
        self.name = name
        self.level = level
        self._sanitize = sanitize
        self._filter = SensitiveFilter() if sanitize else None
        
        # 目标
        self._targets: List[LogTarget] = list(targets) if targets else []
        
        # 异步模式
        self._async_mode = async_mode
        self._async_queue: Optional[AsyncLogQueue] = None
        if async_mode and self._targets:
            self._async_queue = AsyncLogQueue(self._targets)
            self._async_queue.start()
        
        # 内存缓存（最近 1000 条）
        self._recent_logs: List[LogRecord] = []
        self._recent_lock = threading.Lock()
        self._max_recent = 1000
    
    def _create_record(self, level: LogLevel, message: str, exception: Optional[BaseException] = None) -> LogRecord:
        """创建日志记录"""
        # 获取调用者信息
        frame = sys._getframe(2)
        source_file = frame.f_code.co_filename
        source_line = frame.f_lineno
        function = frame.f_code.co_name
        
        # 脱敏
        if self._filter:
            message = self._filter.filter(message)
        
        record = LogRecord(
            timestamp=time.time(),
            level=level,
            module=self.name,
            message=message,
            context=LogContext.get_context(),
            exception=traceback.format_exc() if exception else None,
            source_file=source_file,
            source_line=source_line,
            function=function,
            thread_id=threading.get_ident(),
            process_id=os.getpid(),
        )
        
        return record
    
    def _write(self, record: LogRecord) -> None:
        """写入日志"""
        if self._async_queue:
            self._async_queue.put(record)
        else:
            for target in self._targets:
                try:
                    target.write(record)
                except Exception:
                    pass
        
        # 缓存到内存
        with self._recent_lock:
            self._recent_logs.append(record)
            if len(self._recent_logs) > self._max_recent:
                self._recent_logs = self._recent_logs[-self._max_recent:]
    
    def debug(self, message: str) -> None:
        """DEBUG 级别日志"""
        if self.level.value <= LogLevel.DEBUG.value:
            self._write(self._create_record(LogLevel.DEBUG, message))
    
    def info(self, message: str) -> None:
        """INFO 级别日志"""
        if self.level.value <= LogLevel.INFO.value:
            self._write(self._create_record(LogLevel.INFO, message))
    
    def warning(self, message: str) -> None:
        """WARNING 级别日志"""
        if self.level.value <= LogLevel.WARNING.value:
            self._write(self._create_record(LogLevel.WARNING, message))
    
    def error(self, message: str, exception: Optional[BaseException] = None) -> None:
        """ERROR 级别日志"""
        if self.level.value <= LogLevel.ERROR.value:
            self._write(self._create_record(LogLevel.ERROR, message, exception))
    
    def critical(self, message: str, exception: Optional[BaseException] = None) -> None:
        """CRITICAL 级别日志"""
        if self.level.value <= LogLevel.CRITICAL.value:
            self._write(self._create_record(LogLevel.CRITICAL, message, exception))
    
    def set_level(self, level: LogLevel) -> None:
        """设置日志级别"""
        self.level = level
    
    def add_target(self, target: LogTarget) -> None:
        """添加输出目标"""
        self._targets.append(target)
        if self._async_queue:
            self._async_queue.targets.append(target)
    
    def remove_target(self, target: LogTarget) -> None:
        """移除输出目标"""
        if target in self._targets:
            self._targets.remove(target)
        if self._async_queue and target in self._async_queue.targets:
            self._async_queue.targets.remove(target)
    
    def get_recent_logs(self, limit: int = 100, level: Optional[LogLevel] = None) -> List[LogRecord]:
        """获取最近日志"""
        with self._recent_lock:
            logs = self._recent_logs
            if level:
                logs = [log for log in logs if log.level.value >= level.value]
            return logs[-limit:]
    
    def search_logs(self, pattern: str, limit: int = 100) -> List[LogRecord]:
        """搜索日志"""
        import re
        regex = re.compile(pattern, re.IGNORECASE)
        
        with self._recent_lock:
            results = [log for log in self._recent_logs if regex.search(log.message)]
            return results[-limit:]
    
    def flush(self) -> None:
        """刷新所有目标"""
        if self._async_queue:
            self._async_queue.flush()
        for target in self._targets:
            target.flush()
    
    def close(self) -> None:
        """关闭日志器"""
        if self._async_queue:
            self._async_queue.stop()
        for target in self._targets:
            target.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    # 测试代码
    logger = Logger(
        name="test",
        level=LogLevel.DEBUG,
        targets=[
            ConsoleTarget(level=LogLevel.DEBUG, use_color=True),
            FileTarget(Path("test.log"), level=LogLevel.INFO),
        ],
        async_mode=False,
    )
    
    # 设置上下文
    LogContext.set_value("request_id", "12345")
    LogContext.set_value("user_id", "user_1")
    
    logger.debug("调试信息")
    logger.info("普通信息")
    logger.warning("警告信息")
    logger.error("错误信息")
    logger.critical("严重错误")
    
    # 测试敏感信息过滤
    logger.info("password: secret123")
    logger.info("api_key: abc123")
    
    # 获取最近日志
    recent = logger.get_recent_logs(5)
    print(f"\n最近 5 条日志:")
    for log in recent:
        print(f"  {log.to_text()}")
    
    logger.close()
