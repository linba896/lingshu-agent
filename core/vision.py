#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢视觉模块（Phase 4 视觉理解）
支持：屏幕截图 + VLM 视觉理解（Qwen2-VL / MiniCPM-V 等）
"""

from __future__ import annotations
import enum
import io
import pathlib
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass


class VisionCapability(enum.Enum):
    """视觉能力等级"""
    NONE = 0
    SCREENSHOT = 1
    OCR = 2
    VLM = 3


@dataclass
class UIElement:
    """检测到的 UI 元素"""
    element_type: str
    description: str
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float


@dataclass
class VisionResult:
    """视觉分析结果"""
    scene_description: str
    elements: List[UIElement]
    suggested_actions: List[str]
    raw_response: str


class VisionModule:
    """视觉理解模块"""

    def __init__(self, vlm_config: Dict, root: pathlib.Path):
        self.config = vlm_config
        self.root = root
        self._vlm = None
        self._vlm_type = None
        self._capture_backend = "mss"  # mss / PIL
        self._init_backend()

    def _init_backend(self):
        """初始化截图后端"""
        try:
            import mss
            self._capture_backend = "mss"
        except ImportError:
            try:
                from PIL import ImageGrab
                self._capture_backend = "PIL"
            except ImportError:
                self._capture_backend = None

        # 尝试加载 VLM
        if self.config.get("enabled", False):
            self._load_vlm()

    def _load_vlm(self):
        """加载视觉大模型"""
        model_name = self.config.get("model", "Qwen/Qwen2-VL-2B-Instruct")
        try:
            # 尝试 transformers 方式加载
            from transformers import AutoProcessor, AutoModelForVision2Seq
            import torch

            self._processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
            self._vlm = AutoModelForVision2Seq.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else "cpu",
                trust_remote_code=True,
            )
            self._vlm_type = "transformers"
        except Exception as e:
            # 尝试使用 LLaVA-CLI 或 API 方式
            self._vlm = None
            self._vlm_type = None

    def get_capability(self) -> VisionCapability:
        if self._vlm is not None:
            return VisionCapability.VLM
        elif self._capture_backend is not None:
            return VisionCapability.SCREENSHOT
        return VisionCapability.NONE

    def get_screen_size(self) -> Optional[Tuple[int, int]]:
        try:
            if self._capture_backend == "mss":
                import mss
                with mss.mss() as sct:
                    monitor = sct.monitors[0]
                    return (monitor["width"], monitor["height"])
            elif self._capture_backend == "PIL":
                from PIL import ImageGrab
                img = ImageGrab.grab()
                return img.size
        except Exception:
            return None
        return None

    def capture(self) -> Optional[Any]:
        """截取屏幕"""
        try:
            if self._capture_backend == "mss":
                import mss
                import numpy as np
                with mss.mss() as sct:
                    monitor = sct.monitors[1]  # 主屏幕
                    img = sct.grab(monitor)
                    return np.array(img)
            elif self._capture_backend == "PIL":
                from PIL import ImageGrab
                return ImageGrab.grab()
        except Exception as e:
            return None
        return None

    def capture_to_file(self, path: pathlib.Path) -> bool:
        """截图保存到文件"""
        img = self.capture()
        if img is None:
            return False
        try:
            from PIL import Image
            if hasattr(img, "save"):
                img.save(path)
            else:
                Image.fromarray(img).save(path)
            return True
        except Exception:
            return False

    def analyze(self, query: str = "描述当前屏幕内容") -> VisionResult:
        """使用 VLM 分析屏幕"""
        img = self.capture()
        if img is None:
            return VisionResult(
                scene_description="无法截取屏幕",
                elements=[],
                suggested_actions=[],
                raw_response="",
            )

        if self._vlm_type == "transformers":
            return self._analyze_transformers(img, query)
        else:
            # 降级：使用 OCR + 规则分析
            return self._analyze_degraded(img, query)

    def _analyze_transformers(self, img, query: str) -> VisionResult:
        """使用 transformers VLM 分析"""
        try:
            from PIL import Image
            if not isinstance(img, Image.Image):
                img = Image.fromarray(img)

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": img},
                        {"type": "text", "text": query},
                    ],
                }
            ]
            text = self._processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = self._processor(text=[text], images=[img], return_tensors="pt")
            inputs = {k: v.to(self._vlm.device) for k, v in inputs.items()}

            outputs = self._vlm.generate(**inputs, max_new_tokens=256)
            response = self._processor.batch_decode(outputs, skip_special_tokens=True)[0]

            return VisionResult(
                scene_description=response,
                elements=[],
                suggested_actions=[],
                raw_response=response,
            )
        except Exception as e:
            return self._analyze_degraded(img, query)

    def _analyze_degraded(self, img, query: str) -> VisionResult:
        """降级分析：OCR + 简单规则"""
        try:
            from PIL import Image
            import pytesseract
            if not isinstance(img, Image.Image):
                img = Image.fromarray(img)
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            return VisionResult(
                scene_description=f"屏幕 OCR 识别:\n{text[:500]}",
                elements=[],
                suggested_actions=["建议安装 VLM 模型以获取完整视觉理解"],
                raw_response=text,
            )
        except Exception as e:
            return VisionResult(
                scene_description="视觉分析失败（OCR 和 VLM 均不可用）",
                elements=[],
                suggested_actions=["请安装 tesseract 或 VLM 模型"],
                raw_response=str(e),
            )

    def stop_continuous_capture(self):
        """停止持续捕获（如果有）"""
        pass
