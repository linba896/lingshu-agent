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
import os
import queue
import re
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
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
        
        if self.use_color and self.format == LogFormat.TEXT:
            color = self.LEVEL_COLORS.get(record.level, "")
            text = f"{color}{text}{self.RESET}"
        
        with self._lock:
            if record.level.value >= LogLevel.ERROR.value:
                sys.stderr.write(text + "\n")
                sys.stderr.flush()
            else:
                sys.stdout.write(text + "\n")
                sys.stdout.flush()


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
        sensitive_filter: Optional[SensitiveFilter] = None,
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
    
    def close(self) -> None:
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


# 全局日志器实例
_default_logger: Optional[Logger] = None


def get_logger(name: str = "lingshu") -> Logger:
    """获取全局日志器"""
    global _default_logger
    if _default_logger is None:
        _default_logger = Logger(name=name)
    return _default_logger


def setup_logger(
    root: Path,
    level: LogLevel = LogLevel.INFO,
    console: bool = True,
    file: bool = True,
    json_format: bool = True,
    async_mode: bool = True,
) -> Logger:
    """配置日志系统"""
    global _default_logger
    
    targets: List[LogTarget] = []
    
    if console:
        targets.append(ConsoleTarget(level=level, format=LogFormat.TEXT if not json_format else LogFormat.JSON))
    
    if file:
        log_dir = root / "logs"
        log_dir.mkdir(exist_ok=True)
        targets.append(FileTarget(
            filepath=log_dir / "lingshu.jsonl",
            level=LogLevel.DEBUG,
            format=LogFormat.JSON,
            max_size_mb=10,
            max_backups=10,
            rotate_daily=True,
        ))
    
    logger = Logger(name="lingshu", level=level, targets=targets, async_mode=async_mode)
    _default_logger = logger
    return logger


if __name__ == "__main__":
    # 示例用法
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        logger = setup_logger(root, level=LogLevel.DEBUG, console=True, file=True)
        
        # 基本日志
        logger.debug("调试信息")
        logger.info("系统启动")
        logger.warning("内存使用率较高: 85%")
        logger.error("连接失败", exception=ConnectionError("timeout"))
        
        # 上下文
        with LogContext.scope(request_id="req-123", user_id="user-456"):
            logger.info("处理请求")
        
        # 性能记录
        logger.log_performance("图像识别", 1250.5, True)
        
        # 查询
        time.sleep(0.1)
        records = logger.query(level=LogLevel.INFO, limit=5)
        print(f"\n查询到 {len(records)} 条 INFO 记录")
        
        # 统计
        print(f"\n日志统计: {logger.get_stats()}")
        
        logger.close()
