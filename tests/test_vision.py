#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 视觉模块测试

测试覆盖：
  1. VisionModule 初始化与能力检测
  2. 屏幕尺寸获取
  3. 图像编码
  4. 降级分析（OCR 未安装时）
  5. 结构化解析

运行：
  pytest tests/test_vision.py -v

注意：部分测试依赖 mss/Pillow（截图），CI 环境可能跳过
"""

import sys
import tempfile
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestVisionModule:
    """测试视觉理解模块"""

    def _make_vision(self, config=None):
        from core.vision import VisionModule, VisionCapability
        if config is None:
            config = {
                "model_path": "nonexistent_model",
                "device": "cpu",
                "compute_type": "int8",
            }
        return VisionModule(config, root=None)

    def test_init_no_backend(self):
        """无后端时初始化"""
        vision = self._make_vision()
        assert vision is not None
        cap = vision.get_capability()
        assert cap.value >= 0  # 可能为 NONE 或 SCREENSHOT

    def test_is_ready(self):
        """就绪状态检查"""
        vision = self._make_vision()
        # 未安装 mss/Pillow 时可能为 False
        assert isinstance(vision.is_ready(), bool)

    def test_encode_image_base64(self):
        """图像编码测试"""
        vision = self._make_vision()
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        b64 = vision._encode_image_base64(img, max_size=(50, 50))
        assert isinstance(b64, str)
        assert len(b64) > 0

    def test_fallback_analyze(self):
        """降级分析测试"""
        from core.vision import VisionModule
        vision = VisionModule({"model_path": ""}, root=None)
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        result = vision._fallback_analyze("测试", img)
        assert result.scene_description != ""
        assert result.query == "测试"
        assert isinstance(result.elements, list)

    def test_parse_vlm_response(self):
        """解析 VLM 输出"""
        vision = self._make_vision()
        response = '{"scene": "桌面", "elements": [{"type": "button", "desc": "保存", "bbox": [10,20,30,40]}], "actions": [{"action": "click"}]}'
        result = vision._parse_vlm_response("测试", response, np.zeros((100, 100, 3)))
        assert "桌面" in result.scene_description
        assert len(result.elements) == 1
        assert result.elements[0].element_type == "button"
        assert result.elements[0].bbox == (10, 20, 30, 40)
        assert len(result.suggested_actions) == 1

    def test_parse_vlm_response_invalid_json(self):
        """解析无效 JSON"""
        vision = self._make_vision()
        result = vision._parse_vlm_response("测试", "不是 JSON", np.zeros((100, 100, 3)))
        assert "不是 JSON" in result.scene_description or "不是 JSON" in result.raw_response

    def test_get_screen_size(self):
        """获取屏幕尺寸"""
        vision = self._make_vision()
        size = vision.get_screen_size()
        if size:
            assert len(size) == 2
            assert size[0] > 0
            assert size[1] > 0

    def test_preprocess_image(self):
        """图像预处理"""
        vision = self._make_vision()
        img = np.zeros((2000, 2000, 3), dtype=np.uint8)
        pil = vision._preprocess_image(img, target_pixels=100 * 100)
        assert pil.size[0] <= 200
        assert pil.size[1] <= 200

    def test_describe_screen(self):
        """屏幕描述（降级）"""
        vision = self._make_vision()
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        desc = vision.describe_screen(image=img)
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_understand_instruction(self):
        """视觉指代理解"""
        vision = self._make_vision()
        img = np.zeros((1080, 1920, 3), dtype=np.uint8)
        result = vision.understand_instruction("点击保存按钮", image=img)
        assert "instruction" in result
        assert "scene" in result
        assert "actions" in result


import pytest

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
