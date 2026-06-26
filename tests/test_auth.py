#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 授权管理测试

测试覆盖：
  1. AuthManager 初始化（首次使用 / 已授权）
  2. 授权流程（grant_authorization）
  3. 权限检查（check_permission）3 级权限
  4. 撤销授权（revoke_authorization）
  5. 访客模式（guest mode）
  6. 审计日志（log_operation）
  7. 撤销栈（push_undo / pop_undo）

运行：
  pytest tests/test_auth.py -v
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestAuthManager:
    """测试授权管理器"""

    def _make_auth(self, tmpdir=None, config=None):
        from core.auth import AuthManager
        if tmpdir is None:
            tmpdir = tempfile.mkdtemp()
        root = Path(tmpdir)
        auth = AuthManager(root, config or {})
        return auth, root

    def test_first_use(self):
        """首次使用：未授权状态"""
        auth, root = self._make_auth()
        assert auth.is_first_use() is True
        assert auth.is_authorized() is False
        assert auth.is_guest_mode() is False

    def test_grant_and_check(self):
        """授权后检查"""
        auth, root = self._make_auth()
        auth.grant_authorization()
        assert auth.is_authorized() is True
        assert auth.is_first_use() is False

    def test_permission_level_1(self):
        """一级权限：基础操作直接通过"""
        auth, root = self._make_auth()
        auth.grant_authorization()
        ok, level, msg = auth.check_permission("open", is_speaker_verified=False)
        assert ok is True
        assert level.value == 1
        assert "基础" in msg or "允许" in msg

    def test_permission_level_2_no_speaker(self):
        """二级权限：无声纹验证时拒绝"""
        auth, root = self._make_auth()
        auth.grant_authorization()
        ok, level, msg = auth.check_permission("close", is_speaker_verified=False)
        assert ok is False
        assert level.value == 2

    def test_permission_level_2_with_speaker(self):
        """二级权限：声纹验证后通过"""
        auth, root = self._make_auth()
        auth.grant_authorization()
        ok, level, msg = auth.check_permission("close", is_speaker_verified=True)
        assert ok is True
        assert level.value == 2

    def test_permission_level_3(self):
        """三级权限：始终拒绝（需声纹+人脸）"""
        auth, root = self._make_auth()
        auth.grant_authorization()
        ok, level, msg = auth.check_permission("format_disk", is_speaker_verified=True)
        assert ok is False
        assert level.value == 3

    def test_guest_mode(self):
        """访客模式：仅允许基础操作"""
        auth, root = self._make_auth()
        auth.grant_authorization()
        auth.enter_guest_mode()
        assert auth.is_guest_mode() is True

        ok, level, msg = auth.check_permission("open")
        assert ok is True

        ok, level, msg = auth.check_permission("close")
        assert ok is False

        auth.exit_guest_mode()
        assert auth.is_guest_mode() is False

    def test_revoke(self):
        """撤销授权"""
        auth, root = self._make_auth()
        auth.grant_authorization()
        assert auth.is_authorized() is True

        auth.revoke_authorization()
        assert auth.is_authorized() is False

    def test_unauthorized_rejects(self):
        """未授权时拒绝所有操作"""
        auth, root = self._make_auth()
        ok, level, msg = auth.check_permission("open")
        assert ok is False
        assert "未获得授权" in msg

    def test_audit_log(self):
        """审计日志记录"""
        auth, root = self._make_auth()
        auth.grant_authorization()
        auth.log_operation("open", "打开 Chrome", "success")
        logs = auth.get_audit_logs(limit=10)
        assert len(logs) > 0
        assert logs[-1]["event_type"] == "OPERATION"

    def test_undo_stack(self):
        """撤销栈操作"""
        auth, root = self._make_auth()
        auth.push_undo("move", {"x": 100}, {"x": 200})
        assert auth.can_undo() is True

        entry = auth.pop_undo()
        assert entry["action"] == "move"
        assert entry["pre_state"]["x"] == 100
        assert auth.can_undo() is False

    def test_authorization_text(self):
        """授权文本不为空"""
        auth, root = self._make_auth()
        text = auth.get_authorization_text()
        assert "授权" in text or "协议" in text
        assert len(text) > 100

    def test_persistence(self):
        """授权状态持久化到文件"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            auth, root = self._make_auth(tmpdir)
            auth.grant_authorization()

            # 重新加载
            auth2, _ = self._make_auth(tmpdir)
            assert auth2.is_authorized() is True


import pytest

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
