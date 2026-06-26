#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 执行模块测试

测试覆盖：
  1. ExecutorModule 初始化
  2. 坐标缩放（跨分辨率适配）
  3. 安全确认判断
  4. 操作记录与回滚
  5. 历史栈限制
  6. 便捷方法

运行：
  pytest tests/test_executor.py -v

注意：部分测试需要 pyautogui 已安装（键鼠模拟）
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestExecutorModule:
    """测试执行控制引擎"""

    def _make_executor(self, config=None):
        from core.executor import ExecutorModule
        if config is None:
            config = {
                "safety_level": "normal",
                "action_delay_ms": 50,
                "reference_resolution": [1920, 1080],
            }
        return ExecutorModule(config, root=None)

    def test_init(self):
        """测试初始化"""
        executor = self._make_executor()
        assert executor is not None
        assert executor.safety_level.value == "normal"

    def test_scale_coordinates(self):
        """测试坐标缩放"""
        executor = self._make_executor()
        executor._screen_size = (3840, 2160)  # 4K 屏幕
        executor._scaling_factor = (3840 / 1920, 2160 / 1080)

        x, y = executor._scale_coordinates(100, 200)
        assert x == 200
        assert y == 400

    def test_unscale_coordinates(self):
        """测试坐标反缩放"""
        executor = self._make_executor()
        executor._scaling_factor = (2.0, 2.0)

        x, y = executor._unscale_coordinates(200, 400)
        assert x == 100
        assert y == 200

    def test_needs_confirmation_normal(self):
        """常规模式下敏感操作需要确认"""
        from core.executor import ExecutorAction, ActionType
        executor = self._make_executor()

        action = ExecutorAction(
            action_type=ActionType.MOUSE_CLICK,
            params={"x": 100, "y": 200},
            timestamp=0.0,
            description="点击按钮",
        )
        assert executor._needs_confirmation(action) is False

        sensitive = ExecutorAction(
            action_type=ActionType.SHELL_EXEC,
            params={"command": "rm -rf /"},
            timestamp=0.0,
            description="删除根目录",
        )
        assert executor._needs_confirmation(sensitive) is True

    def test_needs_confirmation_paranoid(self):
        """偏执模式下所有操作需要确认"""
        from core.executor import ExecutorAction, ActionType
        executor = self._make_executor({"safety_level": "paranoid"})

        action = ExecutorAction(
            action_type=ActionType.MOUSE_MOVE,
            params={"x": 100, "y": 200},
            timestamp=0.0,
            description="移动鼠标",
        )
        assert executor._needs_confirmation(action) is True

    def test_history_limit(self):
        """历史栈限制"""
        from core.executor import ExecutorAction, ActionType
        executor = self._make_executor()
        executor._history_limit = 5

        for i in range(10):
            action = ExecutorAction(
                action_type=ActionType.MOUSE_MOVE,
                params={"x": i, "y": i},
                timestamp=float(i),
                description=f"移动 {i}",
            )
            executor._history.append(action)

        executor._trim_history()
        assert len(executor._history) == 5

    def test_undo_redo_empty(self):
        """空栈 undo/redo"""
        executor = self._make_executor()
        assert executor.can_undo() is False
        assert executor.can_redo() is False

        undone = executor.undo(1)
        assert undone == []

        redone = executor.redo(1)
        assert redone == []

    def test_get_status(self):
        """获取状态"""
        executor = self._make_executor()
        status = executor.get_status()
        assert "ready" in status
        assert "safety_level" in status
        assert "dry_run" in status

    def test_convenience_methods(self):
        """便捷方法签名检查"""
        executor = self._make_executor()
        # 这些在无 pyautogui 时返回 False
        assert hasattr(executor, "click")
        assert hasattr(executor, "move")
        assert hasattr(executor, "type_text")
        assert hasattr(executor, "press_key")
        assert hasattr(executor, "hotkey")
        assert hasattr(executor, "scroll")
        assert hasattr(executor, "screenshot")
        assert hasattr(executor, "wait")
        assert hasattr(executor, "alert")


import pytest

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
