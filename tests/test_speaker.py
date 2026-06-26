#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 声纹验证测试

测试覆盖：
  1. SpeakerVerifier 初始化
  2. 特征提取（无 librosa 时降级）
  3. 用户注册/验证/删除
  4. 多用户管理
  5. 访客模式

运行：
  pytest tests/test_speaker.py -v
"""

import sys
import tempfile
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestSpeakerVerifier:
    """测试声纹验证器"""

    def _make_speaker(self, tmpdir=None, max_users=5):
        from core.speaker import SpeakerVerifier
        if tmpdir is None:
            tmpdir = tempfile.mkdtemp()
        profile_dir = Path(tmpdir) / "profiles"
        return SpeakerVerifier(
            profile_dir=profile_dir,
            threshold=0.85,
            verify_mode="strict",
            max_users=max_users,
        )

    def test_init(self):
        """测试初始化"""
        speaker = self._make_speaker()
        assert speaker is not None
        assert speaker.has_enrolled_users() is False
        assert speaker.threshold == 0.85

    def test_extract_features_empty(self):
        """空音频返回 None"""
        speaker = self._make_speaker()
        result = speaker.extract_features(b"")
        assert result is None

    def test_extract_features_dummy(self):
        """虚拟音频特征提取"""
        speaker = self._make_speaker()
        # 生成 1 秒 16kHz 正弦波
        samples = np.sin(2 * np.pi * 440 * np.arange(16000) / 16000)
        audio_bytes = (samples * 32767).astype(np.int16).tobytes()
        result = speaker.extract_features(audio_bytes)
        assert result is not None
        assert isinstance(result, np.ndarray)

    def test_enroll_and_verify(self):
        """注册和验证流程"""
        speaker = self._make_speaker()
        # 生成 5 个样本
        samples = []
        for _ in range(5):
            s = np.sin(2 * np.pi * 440 * np.arange(16000) / 16000)
            audio_bytes = (s * 32767).astype(np.int16).tobytes()
            samples.append(audio_bytes)

        ok, msg = speaker.enroll("user_1", "测试用户", samples)
        assert ok is True
        assert speaker.has_enrolled_users() is True

        # 用相同样本验证（应通过）
        ok, uid, score = speaker.verify(samples[0])
        assert ok is True
        assert uid == "user_1"
        assert score >= 0.85

    def test_verify_unknown(self):
        """未注册用户返回 guest 或失败"""
        speaker = self._make_speaker()
        speaker.verify_mode = "guest"

        s = np.sin(2 * np.pi * 880 * np.arange(16000) / 16000)
        audio_bytes = (s * 32767).astype(np.int16).tobytes()

        ok, uid, score = speaker.verify(audio_bytes)
        # 无注册用户时直接通过（guest）
        assert ok is True

    def test_delete_user(self):
        """删除用户"""
        speaker = self._make_speaker()
        samples = [b"\x00" * 32000] * 5  # 简化样本
        speaker.enroll("u1", "用户1", samples)
        assert speaker.has_enrolled_users() is True

        speaker.delete_user("u1")
        assert speaker.has_enrolled_users() is False

    def test_max_users(self):
        """用户上限"""
        speaker = self._make_speaker(max_users=2)
        samples = [b"\x00" * 32000] * 5

        speaker.enroll("u1", "用户1", samples)
        speaker.enroll("u2", "用户2", samples)

        ok, msg = speaker.enroll("u3", "用户3", samples)
        assert ok is False
        assert "上限" in msg

    def test_list_users(self):
        """列出用户"""
        speaker = self._make_speaker()
        samples = [b"\x00" * 32000] * 5
        speaker.enroll("u1", "Alice", samples)
        speaker.enroll("u2", "Bob", samples)

        users = speaker.list_users()
        assert len(users) == 2
        names = {u["name"] for u in users}
        assert "Alice" in names
        assert "Bob" in names

    def test_similarity(self):
        """余弦相似度计算"""
        speaker = self._make_speaker()
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])
        assert speaker._similarity(a, b) == 1.0

        c = np.array([0.0, 1.0, 0.0])
        sim = speaker._similarity(a, c)
        assert abs(sim) < 0.01  # 正交向量


import pytest

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
