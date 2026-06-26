# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 语音交互模块（Phase 2 桩）
功能：语音转文字（ASR）+ 意图理解（NLU）
"""


class VoiceModule:
    """语音模块桩 — Phase 2 实现"""

    def __init__(self, voice_config: dict, asr_config: dict):
        self.voice_config = voice_config
        self.asr_config = asr_config
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def start_listening(self):
        """开始监听麦克风"""
        raise NotImplementedError("Phase 2: 实现 ASR 与 NLU 集成")

    def transcribe(self, audio_data) -> str:
        """语音转文字"""
        raise NotImplementedError("Phase 2: 集成 Whisper / WeNet")

    def understand_intent(self, text: str) -> dict:
        """意图理解"""
        raise NotImplementedError("Phase 2: 集成 Qwen2.5-1.5B + LoRA")
