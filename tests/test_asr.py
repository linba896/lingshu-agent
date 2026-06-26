#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 语音模块测试

测试场景：
  1. VADRecorder 可用性检测
  2. WhisperASR 模型加载与转录（需模型文件）
  3. NLUProcessor 规则解析（无需模型）
  4. NLUProcessor LLM 解析（需 transformers）
  5. VoiceModule 完整流程
  6. 唤醒词过滤
  7. 意图结构化输出验证

运行：
  cd lingshu-agent
  pytest tests/test_asr.py -v

依赖（按需安装）：
  pip install faster-whisper webrtcvad sounddevice numpy scipy transformers torch
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestVADRecorder:
    """测试 VAD 录音器"""

    def test_import(self):
        """测试 webrtcvad 和 sounddevice 是否可导入"""
        try:
            import webrtcvad
            import sounddevice
            assert True
        except ImportError:
            pytest.skip("webrtcvad 或 sounddevice 未安装")

    def test_init(self):
        """测试 VADRecorder 初始化"""
        try:
            from core.asr import VADRecorder
            recorder = VADRecorder()
            assert recorder.is_available()
            assert recorder.sample_rate == 16000
        except ImportError:
            pytest.skip("webrtcvad 或 sounddevice 未安装")


class TestWhisperASR:
    """测试 Whisper ASR"""

    def test_init_without_model(self):
        """测试无模型时的降级行为"""
        from core.asr import WhisperASR
        asr = WhisperASR(
            model_path="nonexistent_model",
            device="cpu",
            compute_type="int8",
        )
        assert not asr.is_available()
        assert asr._load_error is not None

    def test_init_with_tiny(self):
        """测试加载 tiny 模型（如果存在）"""
        from core.asr import WhisperASR
        root = Path(__file__).resolve().parent.parent
        model_path = root / "models" / "asr" / "whisper-tiny"

        if not model_path.exists():
            pytest.skip("本地 tiny 模型不存在，请先运行 download_models.py")

        try:
            import faster_whisper
        except ImportError:
            pytest.skip("faster-whisper 未安装")

        asr = WhisperASR(
            model_path=str(model_path),
            device="cpu",
            compute_type="int8",
        )
        assert asr.is_available()


class TestNLUProcessor:
    """测试 NLU 意图处理器"""

    def test_rule_parsing_open(self):
        """测试规则解析 — 打开软件"""
        from core.asr import NLUProcessor
        nlu = NLUProcessor("", root=Path("."))  # 规则模式

        result = nlu._understand_with_rules("打开 Photoshop")
        assert result["intent"] == "open"
        assert result["target"] == "photoshop"
        assert result["source"] == "rule"

    def test_rule_parsing_close(self):
        """测试规则解析 — 关闭软件"""
        from core.asr import NLUProcessor
        nlu = NLUProcessor("", root=Path("."))

        result = nlu._understand_with_rules("关闭微信")
        assert result["intent"] == "close"
        assert result["target"] == "微信"

    def test_rule_parsing_click(self):
        """测试规则解析 — 点击操作"""
        from core.asr import NLUProcessor
        nlu = NLUProcessor("", root=Path("."))

        result = nlu._understand_with_rules("点击确认按钮")
        assert result["intent"] == "click"

    def test_rule_parsing_unknown(self):
        """测试规则解析 — 未知意图"""
        from core.asr import NLUProcessor
        nlu = NLUProcessor("", root=Path("."))

        result = nlu._understand_with_rules("今天天气怎么样")
        assert result["intent"] == "query"

    def test_rule_parsing_target_extraction(self):
        """测试目标提取 — 引号内容"""
        from core.asr import NLUProcessor
        nlu = NLUProcessor("", root=Path("."))

        result = nlu._understand_with_rules('打开 "PowerPoint"')
        assert result["target"] == "PowerPoint"

    def test_json_extraction(self):
        """测试 JSON 提取工具"""
        from core.asr import NLUProcessor

        text = '```json\n{"intent": "open", "target": "excel"}\n```'
        result = NLUProcessor._extract_json(text)
        assert result["intent"] == "open"
        assert result["target"] == "excel"

        text2 = "这是一些废话 {\"intent\": \"close\", \"target\": \"word\"} 结束"
        result2 = NLUProcessor._extract_json(text2)
        assert result2["intent"] == "close"

        text3 = "完全不是JSON"
        result3 = NLUProcessor._extract_json(text3)
        assert result3["intent"] == "unknown"


class TestVoiceModule:
    """测试 VoiceModule 主控"""

    def test_init_empty(self):
        """测试空配置初始化（降级模式）"""
        from core.asr import VoiceModule
        root = Path(__file__).resolve().parent.parent

        voice = VoiceModule(
            voice_config={"skip_wake_word": True},
            asr_config={"model_path": "nonexistent"},
            nlu_config={"model_path": ""},
            root=root,
        )
        assert not voice.is_ready()
        assert not voice.is_partial_ready()

    def test_wake_word_detection(self):
        """测试唤醒词检测"""
        from core.asr import VoiceModule
        root = Path(__file__).resolve().parent.parent

        voice = VoiceModule(
            voice_config={"wake_word": "灵枢", "skip_wake_word": False},
            asr_config={},
            nlu_config={"model_path": ""},
            root=root,
        )

        # 包含唤醒词
        result = voice.process_text("灵枢，打开 Photoshop")
        assert result["wake_word_detected"] is True
        assert result["intent"]["intent"] == "open"

        # 不包含唤醒词
        result2 = voice.process_text("打开 Photoshop")
        assert result2["wake_word_detected"] is False
        assert result2["intent"]["intent"] == "idle"

    def test_skip_wake_word(self):
        """测试跳过唤醒词模式"""
        from core.asr import VoiceModule
        root = Path(__file__).resolve().parent.parent

        voice = VoiceModule(
            voice_config={"wake_word": "灵枢", "skip_wake_word": True},
            asr_config={},
            nlu_config={"model_path": ""},
            root=root,
        )

        result = voice.process_text("打开 Photoshop")
        assert result["wake_word_detected"] is False  # 跳过检测时始终 False
        assert result["intent"]["intent"] == "open"  # 但意图正常解析

    def test_process_text_intents(self):
        """测试常见意图解析"""
        from core.asr import VoiceModule
        root = Path(__file__).resolve().parent.parent

        voice = VoiceModule(
            voice_config={"skip_wake_word": True},
            asr_config={},
            nlu_config={"model_path": ""},
            root=root,
        )

        test_cases = [
            ("打开 Chrome", "open", "chrome"),
            ("关闭微信", "close", "微信"),
            ("点击确定", "click", ""),
            ("输入密码", "type", ""),
            ("搜索文件", "search", ""),
            ("截图", "screenshot", ""),
            ("执行脚本", "execute", ""),
            ("查看状态", "query", ""),
        ]

        for text, expected_intent, expected_target in test_cases:
            result = voice.process_text(text)
            intent = result["intent"]
            assert intent["intent"] == expected_intent, f"'{text}' 意图应为 {expected_intent}, 实际为 {intent['intent']}"
            if expected_target:
                assert intent["target"] == expected_target, f"'{text}' 目标应为 {expected_target}, 实际为 {intent['target']}"


import pytest

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
