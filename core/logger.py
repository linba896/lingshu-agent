#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 结构化日志系统 v3.0

功能：
  1. 结构化日志（JSON / CSV / 文本）
  2. 多级别日志（DEBUG / INFO / WARNING / ERROR / CRITICAL）
  3. 上下文注入（用户ID、任务ID、追踪链）
  4. 敏感信息脱敏（自动检测密码/API密钥）
  5. 异步写入（非阻塞日志队列）
  6. 日志轮转（按大小/时间）
  7. 查询接口（按时间/级别/模块筛选）
  8. 多目标输出（文件/控制台/远程）

作者：灵枢工程团队
版本：3.0.0
"""

from __future__ import annotations

import functools
import json
import os
import queue
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TextIO, Union

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta


class LogLevel(Enum):
    """日志级别"""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class LogFormat(Enum):
    """日志格式"""
    TEXT = "text"
    JSON = "json"
    CSV = "csv"


@dataclass
class LogRecord:
    """结构化日志记录"""
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
        ts = datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level_name = self.level.name
        ctx = " ".join(f"{k}={v}" for k, v in self.context.items()) if self.context else ""
        exc = f"\n{self.exception}" if self.exception else ""
        return f"[{ts}] {level_name:8} | {self.module:20} | {self.message} {ctx}{exc}"
    
    def to_json(self) -> str:
        """转换为 JSON 格式"""
        data = {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "level": self.level.name,
            "module": self.module,
            "message": self.message,
            "context": self.context,
            "exception": self.exception,
            "source": {
                "file": self.source_file,
                "line": self.source_line,
                "function": self.function,
            },
            "thread_id": self.thread_id,
            "process_id": self.process_id,
        }
        return json.dumps(data, ensure_ascii=False, default=str)
    
    def to_csv(self) -> str:
        """转换为 CSV 行"""
        ts = datetime.fromtimestamp(self.timestamp).isoformat()
        ctx = json.dumps(self.context, ensure_ascii=False, default=str)
        return f"{ts},{self.level.name},{self.module},{json.dumps(self.message)},{ctx}"


class SensitiveFilter:
    """敏感信息过滤器"""
    
    PATTERNS = {
        "password": r"password[=:]\s*\S+",
        "api_key": r"api[_-]?key[=:]\s*\S+",
        "token": r"token[=:]\s*\S+",
        "secret": r"secret[=:]\s*\S+",
        "credit_card": r"\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}",
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"1[3-9]\d{9}",
        "url": r"https?://\S+",
    }
    
    def __init__(self, custom_patterns: Optional[Dict[str, str]] = None):
        import re
        self._re = re
        self.patterns = {**self.PATTERNS, **(custom_patterns or {})}
        self._compiled = {name: self._re.compile(pattern, self._re.IGNORECASE) 
                         for name, pattern in self.patterns.items()}
    
    def filter(self, text: str) -> str:
        """过滤敏感信息"""
        for name, pattern in self._compiled.items():
            text = pattern.sub(lambda m: f"[{name.upper()}_REDACTED]", text)
        return text


class LogContext:
    """日志上下文管理"""
    
    _local = threading.local()
    
    @classmethod
    def get_context(cls) -> Dict[str, Any]:
        if not hasattr(cls._local, "context"):
            cls._local.context = {}
        return cls._local.context
    
    @classmethod
    def set(cls, key: str, value: Any) -> None:
        cls.get_context()[key] = value
    
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        return cls.get_context().get(key, default)
    
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
    
    @classmethod
    def clear(cls) -> None:
        if hasattr(cls._local, "context"):
            cls._local.context = {}


class LogTarget:
    """日志输出目标基类"""
    
    def __init__(self, level: LogLevel = LogLevel.DEBUG, format: LogFormat = LogFormat.TEXT):
        self.level = level
        self.format = format
    
    def write(self, record: LogRecord) -> None:
        if record.level.value >= self.level.value:
            self._write(record)
    
    def _write(self, record: LogRecord) -> None:
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


class FileTarget(LogTarget):
    """文件输出目标（支持轮转）"""
    
    def __init__(
        self,
        filepath: Union[str, Path],
        level: LogLevel = LogLevel.DEBUG,
        format: LogFormat = LogFormat.JSON,
        max_size_mb: float = 10,
        max_backups: int = 5,
        rotate_daily: bool = False,
    ):
        super().__init__(level, format)
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.max_size = max_size_mb * 1024 * 1024
        self.max_backups = max_backups
        self.rotate_daily = rotate_daily
        self._current_date = datetime.now().date()
        self._file: Optional[Any] = None
        self._open_file()
    
    def _open_file(self) -> None:
        """打开日志文件"""
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
            self.filepath.rename(backup)
        
        # 清理旧备份
        backups = sorted(self.filepath.parent.glob(f"{self.filepath.stem}_*{self.filepath.suffix}"))
        if len(backups) > self.max_backups:
            for old in backups[:-self.max_backups]:
                old.unlink()
        
        self._current_date = datetime.now().date()
        self._open_file()
    
    def _write(self, record: LogRecord) -> None:
        if self._should_rotate():
            self._rotate()
        
        if self._file:
            self._file.write(self._format_record(record) + "\n")
            self._file.flush()
    
    def flush(self) -> None:
        if self._file:
            self._file.flush()
    
    def close(self) -> None:
        with self._lock:
            if self._file:
                self._file.close()
                self._file = None


class ConsoleTarget(LogTarget):
    """控制台输出目标"""
    
    def __init__(self, level: LogLevel = LogLevel.INFO, format: LogFormat = LogFormat.TEXT, stream: Optional[TextIO] = None):
        super().__init__(level, format)
        self.stream = stream or sys.stdout
    
    def _write(self, record: LogRecord) -> None:
        self.stream.write(self._format_record(record) + "\n")
        self.stream.flush()


class AsyncLogQueue:
    """异步日志队列"""
    
    def __init__(self, targets: List[LogTarget], max_queue_size: int = 10000):
        self.targets = targets
        self.queue: queue.Queue[LogRecord] = queue.Queue(maxsize=max_queue_size)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._dropped_count = 0
    
    def start(self) -> None:
        """启动异步写入线程"""
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
    
    def stop(self) -> None:
        """停止异步写入"""
        self._running = False
        self.queue.put(None)  # 发送停止信号
        if self._thread:
            self._thread.join(timeout=5.0)
    
    def put(self, record: LogRecord) -> None:
        """放入队列"""
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            self._dropped_count += 1
    
    def flush(self) -> None:
        """刷新队列"""
        while not self.queue.empty():
            try:
                record = self.queue.get(timeout=0.1)
                if record is None:
                    break
                for target in self.targets:
                    target.write(record)
            except queue.Empty:
                break
    
    def get_dropped_count(self) -> int:
        """获取丢弃计数"""
        return self._dropped_count
    
    def _worker(self) -> None:
        """工作线程"""
        while self._running:
            try:
                record = self.queue.get(timeout=1.0)
                if record is None:
                    break
                for target in self.targets:
                    target.write(record)
            except queue.Empty:
                continue
            except Exception:
                continue


class Logger:
    """灵枢结构化日志器"""
    
    def __init__(
        self,
        name: str = "lingshu",
        level: LogLevel = LogLevel.INFO,
        targets: Optional[List[LogTarget]] = None,
        async_mode: bool = True,
        sensitive_filter: Optional[SensitiveFilter] = None,
        sanitize: bool = False,
    ):
        self.name = name
        self.level = level
        self._targets = targets or []
        self._async_mode = async_mode
        self._sensitive_filter = sensitive_filter or SensitiveFilter()
        
        self._async_queue: Optional[AsyncLogQueue] = None
        if async_mode and self._targets:
            self._async_queue = AsyncLogQueue(self._targets)
            self._async_queue.start()
        
        self._query_index: List[LogRecord] = []  # 内存索引（用于查询）
        self._max_index_size = 10000
        self._query_lock = threading.Lock()
    
    def _create_record(
        self,
        level: LogLevel,
        message: str,
        exception: Optional[Exception] = None,
        **kwargs,
    ) -> LogRecord:
        """创建日志记录"""
        # 获取调用信息
        frame = sys._getframe(2)
        source_file = frame.f_code.co_filename
        source_line = frame.f_lineno
        function = frame.f_code.co_name
        
        # 合并上下文
        context = LogContext.get_context().copy()
        context.update(kwargs)
        
        # 过滤敏感信息
        message = self._sensitive_filter.filter(message)
        
        # 异常信息
        exc_str = None
        if exception:
            exc_str = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
            exc_str = self._sensitive_filter.filter(exc_str)
        
        return LogRecord(
            timestamp=time.time(),
            level=level,
            module=self.name,
            message=message,
            context=context,
            exception=exc_str,
            source_file=source_file,
            source_line=source_line,
            function=function,
            thread_id=threading.get_ident(),
            process_id=os.getpid(),
        )
    
    def _write(self, record: LogRecord) -> None:
        """写入日志"""
        # 索引记录
        with self._query_lock:
            self._query_index.append(record)
            if len(self._query_index) > self._max_index_size:
                self._query_index = self._query_index[-self._max_index_size:]
        
        # 输出
        if self._async_mode and self._async_queue:
            self._async_queue.put(record)
        else:
            for target in self._targets:
                try:
                    target.write(record)
                except Exception:
                    pass
    
    def debug(self, message: str, **kwargs) -> None:
        """调试日志"""
        if self.level.value > LogLevel.DEBUG.value:
            return
        record = self._create_record(LogLevel.DEBUG, message, **kwargs)
        self._write(record)
    
    def info(self, message: str, **kwargs) -> None:
        """信息日志"""
        if self.level.value > LogLevel.INFO.value:
            return
        record = self._create_record(LogLevel.INFO, message, **kwargs)
        self._write(record)
    
    def warning(self, message: str, **kwargs) -> None:
        """警告日志"""
        if self.level.value > LogLevel.WARNING.value:
            return
        record = self._create_record(LogLevel.WARNING, message, **kwargs)
        self._write(record)
    
    def error(self, message: str, exception: Optional[Exception] = None, **kwargs) -> None:
        """错误日志"""
        if self.level.value > LogLevel.ERROR.value:
            return
        record = self._create_record(LogLevel.ERROR, message, exception, **kwargs)
        self._write(record)
    
    def critical(self, message: str, exception: Optional[Exception] = None, **kwargs) -> None:
        """严重错误日志"""
        record = self._create_record(LogLevel.CRITICAL, message, exception, **kwargs)
        self._write(record)
    
    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        **kwargs,
    ) -> None:
        """记录性能指标"""
        self.info(
            f"PERF: {operation} {'成功' if success else '失败'} 耗时 {duration_ms:.2f}ms",
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            **kwargs,
        )
    
    def timed(self, operation_name: str):
        """计时装饰器"""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    duration = (time.time() - start) * 1000
                    self.log_performance(operation_name, duration, True)
                    return result
                except Exception as e:
                    duration = (time.time() - start) * 1000
                    self.log_performance(operation_name, duration, False, error=str(e))
                    raise
            return wrapper
        return decorator
    
    def query(
        self,
        level: Optional[LogLevel] = None,
        module: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        message_contains: Optional[str] = None,
        limit: int = 100,
    ) -> List[LogRecord]:
        """查询日志记录"""
        with self._query_lock:
            results = self._query_index.copy()
        
        # 应用过滤
        if level:
            results = [r for r in results if r.level == level]
        if module:
            results = [r for r in results if r.module == module]
        if start_time:
            results = [r for r in results if r.timestamp >= start_time]
        if end_time:
            results = [r for r in results if r.timestamp <= end_time]
        if message_contains:
            results = [r for r in results if message_contains in r.message]
        
        # 按时间倒序
        results.sort(key=lambda r: r.timestamp, reverse=True)
        return results[:limit]
    
    def add_target(self, target: LogTarget) -> None:
        """添加输出目标"""
        self._targets.append(target)
        if self._async_queue:
            self._async_queue.targets.append(target)
    
    def flush(self) -> None:
        """刷新所有输出"""
        if self._async_queue:
            self._async_queue.flush()
        for target in self._targets:
            target.flush()
    
    def set_level(self, level: LogLevel) -> None:
        """Set log level"""
        self.level = level
    
    def get_recent_logs(self, count: int = 10) -> List[LogRecord]:
        """Get recent logs from memory index"""
        with self._query_lock:
            return self._query_index[-count:].copy() if self._query_index else []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "name": self.name,
            "level": self.level.name,
            "targets_count": len(self._targets),
            "async_mode": self._async_mode,
            "indexed_records": len(self._query_index),
            "dropped_records": self._async_queue.get_dropped_count() if self._async_queue else 0,
        }
    
    def close(self) -> None:
        """关闭日志器"""
        if self._async_queue:
            self._async_queue.stop()
        for target in self._targets:
            target.close()
    
    def shutdown(self) -> None:
        """关闭日志器"""
        if self._async_queue:
            self._async_queue.stop()
        for target in self._targets:
            target.close()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "name": self.name,
            "level": self.level.name,
            "targets_count": len(self._targets),
            "async_mode": self._async_mode,
            "indexed_records": len(self._query_index),
            "dropped_records": self._async_queue.get_dropped_count() if self._async_queue else 0,
        }
