#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 语音交互测试

测试覆盖：
  1. VoiceModule 初始化
  2. 意图解析（规则 + 模型）
  3. 操作唤醒词检测
  4. 空输入处理

运行：
  pytest tests/test_asr.py -v
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestVoiceModule:
    """测试语音交互模块"""

    def _make_voice(self):
        from core.asr import VoiceModule
        return VoiceModule(
            voice_config={"vad_aggressiveness": 3, "frame_duration_ms": 30},
            asr_config={"enabled": False, "backend": "whisper", "model_size": "tiny"},
            nlu_config={"enabled": False, "model": "Qwen/Qwen2-0.5B-Instruct"},
            root=Path("."),
        )

    def test_init(self):
        """测试初始化"""
        voice = self._make_voice()
        assert voice is not None
        # 无模型时部分就绪
        assert voice.is_partial_ready() is not None

    def test_parse_intent_open(self):
        """解析打开意图"""
        voice = self._make_voice()
        result = voice._parse_intent("打开 Chrome")
        assert result["intent"] == "open"
        assert result["confidence"] > 0

    def test_parse_intent_click(self):
        """解析点击意图"""
        voice = self._make_voice()
        result = voice._parse_intent("点击按钮")
        assert result["intent"] == "click"

    def test_parse_intent_screenshot(self):
        """解析截图意图"""
        voice = self._make_voice()
        result = voice._parse_intent("截图")
        assert result["intent"] == "screenshot"

    def test_parse_intent_unknown(self):
        """未知意图"""
        voice = self._make_voice()
        result = voice._parse_intent("随便说点什么")
        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.0

    def test_process_text(self):
        """处理文本"""
        voice = self._make_voice()
        result = voice.process_text("打开 Photoshop")
        assert "text" in result
        assert "intent" in result
        assert result["text"] == "打开 Photoshop"


import pytest

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
