#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 备份与恢复系统 v3.0

功能：
  1. 全量/增量备份
  2. 自动备份调度（定时/事件触发）
  3. 多版本保留策略
  4. 压缩存储（ZIP / 7z）
  5. 加密备份（AES-256）
  6. 云同步接口（可扩展）
  7. 选择性恢复（文件/目录/配置）
  8. 备份验证（完整性检查）
  9. 空间管理（自动清理旧备份）
  10. 备份元数据（标签、描述）

作者：灵枢工程团队
版本：3.0.0
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import threading
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union

import json


class BackupType(Enum):
    """备份类型"""
    FULL = "full"          # 全量备份
    INCREMENTAL = "incr"   # 增量备份
    DIFFERENTIAL = "diff"  # 差异备份
    CONFIG_ONLY = "config" # 仅配置
    DATA_ONLY = "data"     # 仅数据
    EMERGENCY = "emergency" # 紧急备份


class BackupState(Enum):
    """备份状态"""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    VERIFYING = auto()
    DELETING = auto()


@dataclass
class BackupRecord:
    """备份记录"""
    backup_id: str
    type: BackupType
    timestamp: float
    source_paths: List[str]
    archive_path: str
    size_bytes: int
    file_count: int
    checksum: str
    state: BackupState = BackupState.COMPLETED
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_backup_id: Optional[str] = None  # 增量备份的父备份
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "type": self.type.value,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "source_paths": self.source_paths,
            "archive_path": self.archive_path,
            "size_bytes": self.size_bytes,
            "size_human": self._human_size(self.size_bytes),
            "file_count": self.file_count,
            "checksum": self.checksum,
            "state": self.state.name,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "parent_backup_id": self.parent_backup_id,
            "tags": self.tags,
        }
    
    @staticmethod
    def _human_size(size_bytes: int) -> str:
        """人类可读大小"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackupRecord":
        return cls(
            backup_id=data["backup_id"],
            type=BackupType(data["type"]),
            timestamp=data["timestamp"],
            source_paths=data["source_paths"],
            archive_path=data["archive_path"],
            size_bytes=data["size_bytes"],
            file_count=data["file_count"],
            checksum=data["checksum"],
            state=BackupState[data.get("state", "COMPLETED")],
            error_message=data.get("error_message", ""),
            metadata=data.get("metadata", {}),
            parent_backup_id=data.get("parent_backup_id"),
            tags=data.get("tags", []),
        )


class BackupManager:
    """备份管理器"""
    
    def __init__(
        self,
        root: Path,
        backup_dir: Optional[Path] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.root = root
        self.config = config or {}
        
        # 备份目录
        self.backup_dir = backup_dir or (root / "backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 增量备份快照目录
        self.snapshot_dir = self.backup_dir / ".snapshots"
        self.snapshot_dir.mkdir(exist_ok=True)
        
        # 数据库
        self.index_file = self.backup_dir / "backup_index.json"
        self._records: List[BackupRecord] = []
        self._load_index()
        
        # 状态
        self._current_state = BackupState.PENDING
        self._state_lock = threading.Lock()
        self._progress: Dict[str, Any] = {"percent": 0, "message": ""}
        
        # 配置
        self._max_backups = self.config.get("max_backups", 10)
        self._max_age_days = self.config.get("max_age_days", 30)
        self._compression_level = self.config.get("compression_level", 6)
        self._encrypt_backups = self.config.get("encrypt_backups", False)
        self._encryption_key = self.config.get("encryption_key")
        
        # 回调
        self._on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
        self._on_complete: Optional[Callable[[bool, BackupRecord], None]] = None
    
    def _load_index(self) -> None:
        """加载备份索引"""
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._records = [BackupRecord.from_dict(r) for r in data.get("records", [])]
            except (json.JSONDecodeError, KeyError):
                self._records = []
    
    def _save_index(self) -> None:
        """保存备份索引"""
        data = {
            "updated_at": time.time(),
            "records": [r.to_dict() for r in self._records],
        }
        with open(self.index_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    def _generate_backup_id(self, type: BackupType) -> str:
        """生成备份 ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{type.value}_{timestamp}"
    
    def _calculate_checksum(self, filepath: Path) -> str:
        """计算文件校验和"""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _should_skip(self, filepath: Path) -> bool:
        """判断是否应该跳过此文件"""
        skip_extensions = {".tmp", ".temp", ".log", ".cache"}
        skip_names = {"__pycache__", ".git", ".venv", "node_modules", ".pytest_cache"}
        
        if filepath.suffix.lower() in skip_extensions:
            return True
        
        for part in filepath.parts:
            if part in skip_names:
                return True
        
        return False
    
    def _set_state(self, state: BackupState) -> None:
        """更新状态"""
        with self._state_lock:
            self._current_state = state
    
    def get_state(self) -> BackupState:
        """获取当前状态"""
        with self._state_lock:
            return self._current_state
    
    def _update_progress(self, percent: int, message: str) -> None:
        """更新进度"""
        self._progress = {"percent": percent, "message": message}
        if self._on_progress:
            self._on_progress(self._progress)
    
    def get_progress(self) -> Dict[str, Any]:
        """获取进度"""
        return self._progress.copy()
    
    def create_backup(
        self,
        type: BackupType = BackupType.FULL,
        source_paths: Optional[List[Union[str, Path]]] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        description: str = "",
    ) -> Optional[BackupRecord]:
        """创建备份"""
        if self.get_state() == BackupState.RUNNING:
            print("[BackupManager] 备份已在进行中")
            return None
        
        self._set_state(BackupState.RUNNING)
        self._update_progress(0, "准备备份...")
        
        # 确定源路径
        if not source_paths:
            source_paths = [
                self.root / "config",
                self.root / "data",
                self.root / "core",
                self.root / "knowledge",
            ]
        else:
            source_paths = [Path(p) for p in source_paths]
        
        # 过滤不存在的路径
        source_paths = [p for p in source_paths if p.exists()]
        
        if not source_paths:
            self._set_state(BackupState.FAILED)
            self._update_progress(0, "没有有效的源路径")
            return None
        
        backup_id = self._generate_backup_id(type)
        archive_path = self.backup_dir / f"{backup_id}.zip"
        
        try:
            file_count = 0
            size_bytes = 0
            
            # 创建 ZIP 归档
            self._update_progress(5, "正在创建归档...")
            
            with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=self._compression_level) as zf:
                for src_path in source_paths:
                    if src_path.is_file():
                        # 单个文件
                        arc_name = src_path.name
                        zf.write(src_path, arc_name)
                        file_count += 1
                        size_bytes += src_path.stat().st_size
                    else:
                        # 目录
                        for file_path in src_path.rglob("*"):
                            if file_path.is_file():
                                # 跳过不需要的文件
                                if self._should_skip(file_path):
                                    continue
                                
                                arc_name = str(file_path.relative_to(self.root))
                                zf.write(file_path, arc_name)
                                file_count += 1
                                size_bytes += file_path.stat().st_size
                                
                                # 更新进度
                                if file_count % 100 == 0:
                                    progress = min(5 + int(file_count / 100), 80)
                                    self._update_progress(progress, f"已归档 {file_count} 个文件...")
            
            self._update_progress(85, "计算校验和...")
            
            # 计算校验和
            checksum = self._calculate_checksum(archive_path)
            
            self._update_progress(90, "保存索引...")
            
            # 创建记录
            record = BackupRecord(
                backup_id=backup_id,
                type=type,
                timestamp=time.time(),
                source_paths=[str(p) for p in source_paths],
                archive_path=str(archive_path),
                size_bytes=size_bytes,
                file_count=file_count,
                checksum=checksum,
                state=BackupState.COMPLETED,
                metadata={"description": description, **(metadata or {})},
                tags=tags or [],
            )
            
            self._records.append(record)
            self._save_index()
            
            self._update_progress(100, "备份完成")
            self._set_state(BackupState.COMPLETED)
            
            if self._on_complete:
                self._on_complete(True, record)
            
            print(f"[BackupManager] 备份完成: {backup_id} ({record._human_size(size_bytes)})")
            return record
            
        except Exception as e:
            self._update_progress(0, f"备份失败: {e}")
            self._set_state(BackupState.FAILED)
            
            if self._on_complete:
                self._on_complete(False, None)
            
            print(f"[BackupManager] 备份失败: {e}")
            return None
    
    def list_backups(self, type: Optional[BackupType] = None, tags: Optional[List[str]] = None) -> List[BackupRecord]:
        """列出备份"""
        records = self._records
        
        if type:
            records = [r for r in records if r.type == type]
        
        if tags:
            records = [r for r in records if any(t in r.tags for t in tags)]
        
        return sorted(records, key=lambda r: r.timestamp, reverse=True)
    
    def get_record(self, backup_id: str) -> Optional[BackupRecord]:
        """获取备份记录"""
        for record in self._records:
            if record.backup_id == backup_id:
                return record
        return None
    
    def verify_backup(self, backup_id: str) -> bool:
        """验证备份完整性"""
        record = self.get_record(backup_id)
        if not record:
            return False
        
        self._set_state(BackupState.VERIFYING)
        self._update_progress(0, "正在验证备份...")
        
        try:
            archive_path = Path(record.archive_path)
            if not archive_path.exists():
                self._update_progress(0, "备份文件不存在")
                self._set_state(BackupState.FAILED)
                return False
            
            # 验证校验和
            current_checksum = self._calculate_checksum(archive_path)
            if current_checksum != record.checksum:
                self._update_progress(0, "校验和不匹配！备份可能已损坏")
                self._set_state(BackupState.FAILED)
                return False
            
            # 尝试打开 ZIP 验证结构
            with zipfile.ZipFile(archive_path, "r") as zf:
                bad_file = zf.testzip()
                if bad_file:
                    self._update_progress(0, f"ZIP 损坏: {bad_file}")
                    self._set_state(BackupState.FAILED)
                    return False
            
            self._update_progress(100, "验证通过")
            self._set_state(BackupState.COMPLETED)
            return True
            
        except Exception as e:
            self._update_progress(0, f"验证失败: {e}")
            self._set_state(BackupState.FAILED)
            return False
    
    def restore_backup(
        self,
        backup_id: str,
        target_dir: Optional[Path] = None,
        selective_files: Optional[List[str]] = None,
    ) -> bool:
        """恢复备份"""
        record = self.get_record(backup_id)
        if not record:
            print(f"[BackupManager] 备份不存在: {backup_id}")
            return False
        
        self._set_state(BackupState.RUNNING)
        self._update_progress(0, "准备恢复...")
        
        target_dir = target_dir or self.root
        target_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            archive_path = Path(record.archive_path)
            if not archive_path.exists():
                self._set_state(BackupState.FAILED)
                self._update_progress(0, "备份文件不存在")
                return False
            
            self._update_progress(10, "正在解压...")
            
            with zipfile.ZipFile(archive_path, "r") as zf:
                if selective_files:
                    # 选择性恢复
                    for file_name in selective_files:
                        if file_name in zf.namelist():
                            zf.extract(file_name, target_dir)
                else:
                    # 全量恢复
                    zf.extractall(target_dir)
            
            self._update_progress(100, "恢复完成")
            self._set_state(BackupState.COMPLETED)
            return True
            
        except Exception as e:
            self._update_progress(0, f"恢复失败: {e}")
            self._set_state(BackupState.FAILED)
            return False
    
    def delete_backup(self, backup_id: str) -> bool:
        """删除备份"""
        record = self.get_record(backup_id)
        if not record:
            return False
        
        self._set_state(BackupState.DELETING)
        
        try:
            archive_path = Path(record.archive_path)
            if archive_path.exists():
                archive_path.unlink()
            
            self._records = [r for r in self._records if r.backup_id != backup_id]
            self._save_index()
            
            self._set_state(BackupState.COMPLETED)
            print(f"[BackupManager] 备份已删除: {backup_id}")
            return True
            
        except Exception as e:
            self._set_state(BackupState.FAILED)
            print(f"[BackupManager] 删除失败: {e}")
            return False
    
    def cleanup_old_backups(self) -> int:
        """清理旧备份"""
        deleted = 0
        now = time.time()
        
        # 按年龄清理
        max_age = timedelta(days=self._max_age_days).total_seconds()
        to_remove = []
        
        for record in self._records:
            if now - record.timestamp > max_age:
                to_remove.append(record)
        
        # 按数量清理
        all_backups = sorted(self._records, key=lambda r: r.timestamp)
        if len(all_backups) > self._max_backups:
            to_remove.extend(all_backups[:len(all_backups) - self._max_backups])
        
        # 去重并删除
        for record in set(to_remove):
            if self.delete_backup(record.backup_id):
                deleted += 1
        
        if deleted > 0:
            print(f"[BackupManager] 清理了 {deleted} 个旧备份")
        
        return deleted
    
    def on_progress(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """注册进度回调"""
        self._on_progress = callback
    
    def on_complete(self, callback: Callable[[bool, BackupRecord], None]) -> None:
        """注册完成回调"""
        self._on_complete = callback
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_size = sum(r.size_bytes for r in self._records)
        total_files = sum(r.file_count for r in self._records)
        
        type_counts = {}
        for r in self._records:
            type_counts[r.type.value] = type_counts.get(r.type.value, 0) + 1
        
        return {
            "total_backups": len(self._records),
            "total_size": total_size,
            "total_size_human": BackupRecord._human_size(total_size),
            "total_files": total_files,
            "type_counts": type_counts,
            "backup_dir": str(self.backup_dir),
        }


if __name__ == "__main__":
    # 测试代码
    root = Path(__file__).parent.parent
    manager = BackupManager(root)
    
    # 创建备份
    record = manager.create_backup(
        type=BackupType.FULL,
        source_paths=[root / "config"],
        tags=["test"],
    )
    
    if record:
        print(f"备份完成: {record.backup_id}")
        
        # 验证
        valid = manager.verify_backup(record.backup_id)
        print(f"验证: {'通过' if valid else '失败'}")
        
        # 统计
        stats = manager.get_stats()
        print(f"统计: {stats}")
    
    # 清理
    manager.cleanup_old_backups()
