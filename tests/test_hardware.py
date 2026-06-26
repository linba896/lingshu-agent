#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 硬件控制测试

测试覆盖：
  1. HardwareController 初始化
  2. 场景切换
  3. 命令权限检查
  4. 协议配置

运行：
  pytest tests/test_hardware.py -v
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestHardwareController:
    """测试硬件控制器"""

    def _make_hardware(self, config=None):
        from core.hardware import HardwareController
        if config is None:
            config = {
                "protocols": {
                    "tcp": {"enabled": True},
                    "mqtt": {"enabled": False},
                },
                "default_scene": "computer",
            }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            return HardwareController(config, root)

    def test_init(self):
        """测试初始化"""
        hw = self._make_hardware()
        assert hw is not None
        assert hw.get_scene() == "computer"

    def test_set_scene(self):
        """场景切换"""
        hw = self._make_hardware()
        assert hw.set_scene("stage") is True
        assert hw.get_scene() == "stage"

        assert hw.set_scene("invalid") is False
        assert hw.get_scene() == "stage"  # 保持不变

    def test_scene_commands(self):
        """场景命令权限"""
        hw = self._make_hardware()
        assert hw.is_command_allowed("open") is True  # computer 场景
        assert hw.is_command_allowed("light_on") is False

        hw.set_scene("stage")
        assert hw.is_command_allowed("light_on") is True
        assert hw.is_command_allowed("dmx_preset") is True
        assert hw.is_command_allowed("open") is False  # stage 场景无 open

    def test_scene_commands_hotel(self):
        """酒店场景命令"""
        hw = self._make_hardware()
        hw.set_scene("hotel")
        assert hw.is_command_allowed("light_on") is True
        assert hw.is_command_allowed("temperature_set") is True
        assert hw.is_command_allowed("scene_welcome") is True

    def test_scene_commands_meeting(self):
        """会议场景命令"""
        hw = self._make_hardware()
        hw.set_scene("meeting")
        assert hw.is_command_allowed("projector_on") is True
        assert hw.is_command_allowed("curtain_close") is True
        assert hw.is_command_allowed("mic_mute") is True

    def test_emergency_stop(self):
        """紧急停止"""
        hw = self._make_hardware()
        # 紧急停止方法不应抛出异常
        try:
            hw.emergency_stop_all()
        except Exception as e:
            assert False, f"紧急停止不应抛出异常: {e}"

    def test_protocols_disabled(self):
        """禁用协议"""
        hw = self._make_hardware()
        # MQTT 未启用
        result = hw.send_mqtt("test/topic", {"data": 1})
        assert result is False


import pytest

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
