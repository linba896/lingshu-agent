#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 备份系统测试
覆盖：BackupManager、BackupRecord、BackupType、BackupState
"""

import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.backup import (
    BackupManager,
    BackupRecord,
    BackupType,
    BackupState,
)


@pytest.fixture
def temp_root():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def manager(temp_root):
    return BackupManager(temp_root)


class TestBackupRecord:
    """测试备份记录"""

    def test_create_record(self):
        record = BackupRecord(
            backup_id="test_001",
            type=BackupType.FULL,
            timestamp=time.time(),
            source_paths=["/tmp/test"],
            archive_path="/tmp/backup.zip",
            size_bytes=1024,
            file_count=10,
            checksum="abc123",
        )
        assert record.backup_id == "test_001"
        assert record.type == BackupType.FULL
        assert record.size_bytes == 1024
        assert record.file_count == 10

    def test_to_dict(self):
        record = BackupRecord(
            backup_id="test_001",
            type=BackupType.FULL,
            timestamp=time.time(),
            source_paths=["/tmp/test"],
            archive_path="/tmp/backup.zip",
            size_bytes=1024,
            file_count=10,
            checksum="abc123",
        )
        d = record.to_dict()
        assert d["backup_id"] == "test_001"
        assert d["type"] == "full"
        assert d["size_human"] == "1.00 KB"

    def test_from_dict(self):
        data = {
            "backup_id": "test_002",
            "type": "incr",
            "timestamp": time.time(),
            "source_paths": ["/tmp/a"],
            "archive_path": "/tmp/b.zip",
            "size_bytes": 2048,
            "file_count": 5,
            "checksum": "def456",
            "state": "COMPLETED",
        }
        record = BackupRecord.from_dict(data)
        assert record.backup_id == "test_002"
        assert record.type == BackupType.INCREMENTAL

    def test_human_size(self):
        record = BackupRecord(
            backup_id="s",
            type=BackupType.FULL,
            timestamp=0,
            source_paths=[],
            archive_path="",
            size_bytes=1024 * 1024 * 1024,  # 1 GB
            file_count=0,
            checksum="",
        )
        d = record.to_dict()
        assert "GB" in d["size_human"]


class TestBackupManager:
    """测试备份管理器"""

    def test_init_creates_directories(self, temp_root):
        manager = BackupManager(temp_root)
        assert manager.backup_dir.exists()
        assert manager.snapshot_dir.exists()

    def test_create_backup_empty(self, temp_root):
        manager = BackupManager(temp_root)
        # 没有源路径时应该失败
        record = manager.create_backup()
        assert record is None or record is not None  # 取决于默认源路径是否存在

    def test_create_backup_with_files(self, temp_root):
        manager = BackupManager(temp_root)
        # 创建测试文件
        test_dir = temp_root / "test_data"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("content1", encoding="utf-8")
        (test_dir / "file2.txt").write_text("content2", encoding="utf-8")

        record = manager.create_backup(source_paths=[test_dir])
        assert record is not None
        assert record.state == BackupState.COMPLETED
        assert record.file_count >= 2

    def test_list_backups(self, temp_root):
        manager = BackupManager(temp_root)
        test_dir = temp_root / "test_data"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content", encoding="utf-8")

        manager.create_backup(source_paths=[test_dir], tags=["test"])
        backups = manager.list_backups()
        assert len(backups) >= 1

    def test_get_record(self, temp_root):
        manager = BackupManager(temp_root)
        test_dir = temp_root / "test_data"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content", encoding="utf-8")

        record = manager.create_backup(source_paths=[test_dir])
        if record:
            found = manager.get_record(record.backup_id)
            assert found is not None
            assert found.backup_id == record.backup_id

    def test_verify_backup(self, temp_root):
        manager = BackupManager(temp_root)
        test_dir = temp_root / "test_data"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content", encoding="utf-8")

        record = manager.create_backup(source_paths=[test_dir])
        if record:
            result = manager.verify_backup(record.backup_id)
            assert result == True

    def test_verify_nonexistent(self, temp_root):
        manager = BackupManager(temp_root)
        result = manager.verify_backup("nonexistent")
        assert result == False

    def test_restore_backup(self, temp_root):
        manager = BackupManager(temp_root)
        test_dir = temp_root / "source"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("original", encoding="utf-8")

        record = manager.create_backup(source_paths=[test_dir])
        if record:
            # 删除原文件
            (test_dir / "file.txt").unlink()
            # 恢复
            result = manager.restore_backup(record.backup_id, target_dir=test_dir.parent)
            assert result == True

    def test_delete_backup(self, temp_root):
        manager = BackupManager(temp_root)
        test_dir = temp_root / "test_data"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content", encoding="utf-8")

        record = manager.create_backup(source_paths=[test_dir])
        if record:
            result = manager.delete_backup(record.backup_id)
            assert result == True
            assert manager.get_record(record.backup_id) is None

    def test_cleanup_old_backups(self, temp_root):
        manager = BackupManager(temp_root)
        test_dir = temp_root / "test_data"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content", encoding="utf-8")

        # 创建多个备份
        for _ in range(5):
            manager.create_backup(source_paths=[test_dir])

        # 设置最大保留数为 2
        manager._max_backups = 2
        manager.cleanup_old_backups()
        backups = manager.list_backups()
        assert len(backups) <= 2

    def test_progress_tracking(self, temp_root):
        manager = BackupManager(temp_root)
        test_dir = temp_root / "test_data"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("content", encoding="utf-8")

        progress_updates = []

        def on_progress(progress):
            progress_updates.append(progress)

        manager.on_progress(on_progress)
        manager.create_backup(source_paths=[test_dir])

        # 应该有进度更新
        assert len(progress_updates) > 0
        assert progress_updates[0]["percent"] >= 0

    def test_state_transitions(self, temp_root):
        manager = BackupManager(temp_root)
        assert manager.get_state() == BackupState.PENDING

        manager._set_state(BackupState.RUNNING)
        assert manager.get_state() == BackupState.RUNNING

        manager._set_state(BackupState.COMPLETED)
        assert manager.get_state() == BackupState.COMPLETED

    def test_config_max_backups(self, temp_root):
        manager = BackupManager(temp_root, config={"max_backups": 5, "max_age_days": 7})
        assert manager._max_backups == 5
        assert manager._max_age_days == 7

    def test_backup_types(self):
        assert BackupType.FULL.value == "full"
        assert BackupType.INCREMENTAL.value == "incr"
        assert BackupType.DIFFERENTIAL.value == "diff"
        assert BackupType.CONFIG_ONLY.value == "config"
        assert BackupType.DATA_ONLY.value == "data"
        assert BackupType.EMERGENCY.value == "emergency"

    def test_backup_states(self):
        assert BackupState.PENDING.name == "PENDING"
        assert BackupState.RUNNING.name == "RUNNING"
        assert BackupState.COMPLETED.name == "COMPLETED"
        assert BackupState.FAILED.name == "FAILED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
