#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 更新管理器测试
覆盖：UpdateManager、VersionInfo、UpdateRecord、UpdateState、UpdateChannel
"""

import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.update_manager import (
    UpdateManager,
    VersionInfo,
    UpdateRecord,
    UpdateState,
    UpdateChannel,
)


@pytest.fixture
def temp_root():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


class TestVersionInfo:
    """测试版本信息"""

    def test_create(self):
        info = VersionInfo(
            version="1.0.0",
            channel=UpdateChannel.STABLE,
            release_date="2024-01-01",
            changelog="初始版本",
            download_url="https://example.com/v1.0.0.zip",
            size_bytes=1024000,
            checksum="abc123",
        )
        assert info.version == "1.0.0"
        assert info.channel == UpdateChannel.STABLE
        assert info.required_restart == True

    def test_to_dict(self):
        info = VersionInfo(
            version="1.0.0",
            channel=UpdateChannel.STABLE,
            release_date="2024-01-01",
            changelog="初始版本",
            download_url="https://example.com/v1.0.0.zip",
            size_bytes=1024000,
            checksum="abc123",
        )
        d = info.to_dict()
        assert d["version"] == "1.0.0"
        assert d["channel"] == "stable"
        assert d["is_mandatory"] == False

    def test_from_dict(self):
        data = {
            "version": "2.0.0",
            "channel": "beta",
            "release_date": "2024-06-01",
            "changelog": "Beta 版本",
            "download_url": "https://example.com/v2.0.0.zip",
            "size_bytes": 2048000,
            "checksum": "def456",
            "is_mandatory": True,
        }
        info = VersionInfo.from_dict(data)
        assert info.version == "2.0.0"
        assert info.channel == UpdateChannel.BETA
        assert info.is_mandatory == True


class TestUpdateRecord:
    """测试更新记录"""

    def test_create(self):
        record = UpdateRecord(
            version="1.0.0",
            from_version="0.9.0",
            timestamp=time.time(),
            success=True,
            duration_seconds=60.0,
        )
        assert record.version == "1.0.0"
        assert record.success == True


class TestUpdateManager:
    """测试更新管理器"""

    def test_init(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        assert manager.current_version == "1.0.0"
        assert manager.update_dir.exists()
        assert manager.cache_dir.exists()

    def test_default_channel(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        assert manager.channel == UpdateChannel.STABLE

    def test_custom_channel(self, temp_root):
        manager = UpdateManager(
            temp_root,
            current_version="1.0.0",
            config={"channel": "beta"}
        )
        assert manager.channel == UpdateChannel.BETA

    def test_state_idle(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        assert manager.get_state() == UpdateState.IDLE

    def test_state_transitions(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        manager._set_state(UpdateState.CHECKING)
        assert manager.get_state() == UpdateState.CHECKING

    def test_progress(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        manager._update_progress(50, "下载中...")
        progress = manager.get_progress()
        assert progress["percent"] == 50
        assert progress["message"] == "下载中..."

    def test_history(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        history = manager.get_history()
        assert isinstance(history, list)

    def test_history_persistence(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        # 添加历史记录
        manager._add_to_history("1.0.0", "0.9.0", True, 30.0)
        manager._save_history()
        # 重新加载
        manager2 = UpdateManager(temp_root, current_version="1.0.0")
        history = manager2.get_history()
        assert len(history) >= 1

    def test_compare_versions(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        assert manager._compare_versions("1.0.0", "1.0.0") == 0
        assert manager._compare_versions("1.1.0", "1.0.0") > 0
        assert manager._compare_versions("0.9.0", "1.0.0") < 0
        assert manager._compare_versions("1.0.1", "1.0.0") > 0

    def test_parse_version(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        assert manager._parse_version("1.2.3") == [1, 2, 3]
        assert manager._parse_version("2.0") == [2, 0, 0]
        assert manager._parse_version("3.0.0-beta") == [3, 0, 0]

    def test_on_callbacks(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        
        progress_calls = []
        def on_progress(p):
            progress_calls.append(p)
        
        complete_calls = []
        def on_complete(success, msg):
            complete_calls.append((success, msg))
        
        manager.on_progress(on_progress)
        manager.on_complete(on_complete)
        
        assert manager._on_progress is not None
        assert manager._on_complete is not None

    def test_check_updates_while_busy(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        manager._set_state(UpdateState.DOWNLOADING)
        result = manager.check_updates()
        assert result is None  # 忙碌时应返回 None

    def test_auto_check_config(self, temp_root):
        manager = UpdateManager(
            temp_root,
            current_version="1.0.0",
            config={
                "auto_check": True,
                "check_interval_hours": 12,
                "auto_download": False,
                "auto_install": False,
            }
        )
        assert manager.auto_check == True
        assert manager.check_interval_hours == 12
        assert manager.auto_download == False
        assert manager.auto_install == False

    def test_update_states(self):
        assert UpdateState.IDLE.name == "IDLE"
        assert UpdateState.CHECKING.name == "CHECKING"
        assert UpdateState.DOWNLOADING.name == "DOWNLOADING"
        assert UpdateState.VERIFYING.name == "VERIFYING"
        assert UpdateState.INSTALLING.name == "INSTALLING"
        assert UpdateState.RESTARTING.name == "RESTARTING"
        assert UpdateState.ROLLING_BACK.name == "ROLLING_BACK"
        assert UpdateState.ERROR.name == "ERROR"

    def test_update_channels(self):
        assert UpdateChannel.STABLE.value == "stable"
        assert UpdateChannel.BETA.value == "beta"
        assert UpdateChannel.DEV.value == "dev"
        assert UpdateChannel.NIGHTLY.value == "nightly"

    def test_rollback_no_history(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        result = manager.rollback()
        assert result == False

    def test_is_newer_version(self, temp_root):
        manager = UpdateManager(temp_root, current_version="1.0.0")
        # 当前版本是 1.0.0，所以 1.0.0 不是新版本
        assert manager._compare_versions("1.0.0", "1.0.0") <= 0
        # 2.0.0 是新版本
        assert manager._compare_versions("2.0.0", "1.0.0") > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
