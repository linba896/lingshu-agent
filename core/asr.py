#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢语音交互模块（Phase 2 ASR + NLU）
整合：语音端点检测(VAD) + 语音识别(ASR) + 自然语言理解(NLU)
"""

import sys
import json
import time
import queue
import threading
import pathlib
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass


@dataclass
class IntentResult:
    """意图理解结果"""
    intent: str
    params: Dict[str, Any]
    raw_text: str
    confidence: float


class VoiceModule:
    """语音交互模块：VAD + ASR + NLU"""

    def __init__(self, voice_config: Dict, asr_config: Dict, nlu_config: Dict, root: pathlib.Path):
        self.voice_config = voice_config
        self.asr_config = asr_config
        self.nlu_config = nlu_config
        self.root = root
        self._vad = None
        self._asr = None
        self._nlu = None
        self._listening = False
        self._intent_callback: Optional[Callable] = None
        self._listen_thread: Optional[threading.Thread] = None
        self._init_modules()

    def _init_modules(self):
        """初始化 VAD / ASR / NLU 子模块"""
        # VAD
        try:
            from core.vad import WebRTCVAD
            self._vad = WebRTCVAD(
                aggressiveness=self.voice_config.get("vad_aggressiveness", 3),
                frame_duration_ms=self.voice_config.get("frame_duration_ms", 30),
            )
        except ImportError as e:
            self._vad = None

        # ASR
        if self.asr_config.get("enabled", True):
            self._load_asr()

        # NLU
        if self.nlu_config.get("enabled", True):
            self._load_nlu()

    def _load_asr(self):
        """加载 ASR 模型"""
        backend = self.asr_config.get("backend", "whisper")
        try:
            if backend == "whisper":
                import whisper
                model_size = self.asr_config.get("model_size", "base")
                self._asr = whisper.load_model(model_size)
                self._asr_type = "whisper"
            elif backend == "faster-whisper":
                from faster_whisper import WhisperModel
                model_size = self.asr_config.get("model_size", "base")
                self._asr = WhisperModel(model_size, device="cpu", compute_type="int8")
                self._asr_type = "faster-whisper"
            else:
                self._asr = None
        except Exception as e:
            self._asr = None

    def _load_nlu(self):
        """加载 NLU 模型"""
        try:
            from transformers import pipeline
            self._nlu = pipeline(
                "text-generation",
                model=self.nlu_config.get("model", "Qwen/Qwen2-0.5B-Instruct"),
                device=-1,
            )
            self._nlu_type = "transformers"
        except Exception as e:
            self._nlu = None

    def is_ready(self) -> bool:
        return self._vad is not None and self._asr is not None and self._nlu is not None

    def is_partial_ready(self) -> bool:
        return self._vad is not None or self._asr is not None

    def record_and_transcribe(self, duration: float = 5.0) -> str:
        """录制并转录为文本"""
        if not self._vad:
            return ""
        audio, sr = self._vad.record_fixed_duration(duration)
        if audio is None:
            return ""
        return self._transcribe(audio, sr)

    def _transcribe(self, audio: Any, sr: int) -> str:
        """内部转录"""
        if self._asr is None:
            return ""
        try:
            if self._asr_type == "whisper":
                import whisper
                import numpy as np
                result = self._asr.transcribe(audio, language="zh")
                return result["text"]
            elif self._asr_type == "faster-whisper":
                segments, _ = self._asr.transcribe(audio, language="zh")
                return "".join([s.text for s in segments])
        except Exception as e:
            return f"[ASR 错误: {e}]"
        return ""

    def process_text(self, text: str) -> Dict[str, Any]:
        """文本意图理解"""
        intent = self._parse_intent(text)
        return {
            "text": text,
            "intent": intent,
            "timestamp": time.time(),
        }

    def _parse_intent(self, text: str) -> Dict[str, Any]:
        """解析意图（规则 + 模型）"""
        text_lower = text.lower().strip()

        # 规则匹配
        wake_words = ["灵枢", "ling shu", "lingshu"]
        if any(w in text_lower for w in wake_words):
            # 唤醒词检测
            pass

        # 简单意图分类
        intents = {
            "open": ["打开", "open", "启动", "start"],
            "close": ["关闭", "close", "退出", "quit"],
            "search": ["搜索", "search", "查找", "find"],
            "click": ["点击", "click", "按下", "press"],
            "type": ["输入", "type", "填写", "write"],
            "scroll": ["滚动", "scroll", "下滑", "下滑"],
            "screenshot": ["截图", "screenshot", "截屏"],
            "status": ["状态", "status", "情况", "怎么样"],
        }

        for intent_type, keywords in intents.items():
            if any(k in text_lower for k in keywords):
                return {
                    "intent": intent_type,
                    "raw_text": text,
                    "params": {},
                    "confidence": 0.8,
                }

        # 使用 NLU 模型（如果可用）
        if self._nlu and self._nlu_type == "transformers":
            try:
                prompt = f"请分析用户意图，输出 JSON：{{'intent': '意图类型', 'params': {{}}}}\n用户: {text}\n意图:"
                result = self._nlu(prompt, max_new_tokens=100, do_sample=False)[0]["generated_text"]
                # 尝试解析 JSON
                import json
                try:
                    parsed = json.loads(result.split("\n")[-1])
                    return parsed
                except json.JSONDecodeError:
                    pass
            except Exception:
                pass

        return {
            "intent": "unknown",
            "raw_text": text,
            "params": {},
            "confidence": 0.0,
        }

    def record_and_understand(self) -> Optional[Dict[str, Any]]:
        """录制并理解意图"""
        text = self.record_and_transcribe(duration=5.0)
        if not text:
            return None
        return self.process_text(text)

    def start_continuous_listening(self, on_intent: Callable):
        """启动持续监听（后台线程）"""
        if self._listening:
            return
        self._intent_callback = on_intent
        self._listening = True
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()

    def stop_continuous_listening(self):
        """停止持续监听"""
        self._listening = False
        if self._listen_thread:
            self._listen_thread.join(timeout=2)

    def _listen_loop(self):
        """监听循环"""
        while self._listening:
            try:
                result = self.record_and_understand()
                if result and self._intent_callback:
                    self._intent_callback(result)
            except Exception as e:
                time.sleep(1)

    # 兼容旧代码
    def start_listening(self, on_intent: Callable):
        return self.start_continuous_listening(on_intent)

    def stop_listening(self):
        return self.stop_continuous_listening()


# 兼容旧导入
from core.vad import WebRTCVAD
