# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 屏幕理解模块（Phase 3 桩）
功能：屏幕截图 + VLM 解析 + GUI 元素定位
"""


class VisionModule:
    """视觉模块桩 — Phase 3 实现"""

    def __init__(self, vlm_config: dict):
        self.vlm_config = vlm_config
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready

    def capture_screen(self) -> bytes:
        """截取屏幕"""
        raise NotImplementedError("Phase 3: 集成 mss / PIL 截图")

    def analyze_gui(self, screenshot: bytes, instruction: str) -> dict:
        """VLM 解析屏幕 + 生成操作计划"""
        raise NotImplementedError("Phase 3: 集成 Qwen3-VL-8B")

    def locate_element(self, element_description: str) -> tuple:
        """定位 GUI 元素坐标"""
        raise NotImplementedError("Phase 3: 集成 Ponder & Press 定位器")
