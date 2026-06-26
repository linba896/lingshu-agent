import base64
import io
import json
import threading
import time
import warnings
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


class VisionCapability(Enum):
    """视觉能力等级"""
    NONE = 0          # 未就绪
    SCREENSHOT = 1    # 仅能截图
    BASIC_OCR = 2     # 截图 + 基础 OCR（pytesseract 备选）
    VLM = 3           # 截图 + VLM 视觉理解（完整）


@dataclass
class ScreenElement:
    """屏幕上的 UI 元素"""
    element_id: str
    element_type: str       # button, icon, text, link, image, input, window...
    description: str        # 自然语言描述
    bbox: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    text_content: Optional[str] = None
    confidence: float = 0.0
    action_hint: Optional[str] = None  # "clickable", "draggable", "editable"...


@dataclass
class VisionAnalysisResult:
    """视觉分析结果"""
    query: str                      # 原始查询/指令
    scene_description: str          # 整体场景描述
    elements: List[ScreenElement]   # 检测到的元素
    suggested_actions: List[Dict[str, Any]]  # 建议操作（含坐标）
    raw_response: Optional[str] = None


class VisionModule:
    """
    视觉理解模块

    管理屏幕捕获与视觉理解：
      - 截图：支持多显示器、区域截图、连续捕获
      - 预处理：分辨率自适应、Base64 编码、格式转换
      - VLM：Qwen3-VL-8B-Instruct 本地推理 / API fallback
      - 解析：提取 UI 元素、文本、语义上下文
      - 联动：接收语音指令中的视觉指代（"这个"、"那里"），解析后返回操作坐标
    """

    # 图像处理常量
    MAX_IMAGE_SIZE = (1920, 1080)    # 最大输入分辨率（VLM 输入限制）
    JPEG_QUALITY = 85                  # 编码质量
    TARGET_PIXELS = 512 * 512         # 目标像素数（控制 VLM 输入大小）

    def __init__(self, vlm_config: Dict, root: Optional[Path] = None):
        self.config = vlm_config or {}
        self.root = root

        # 模型配置
        self.model_path = self.config.get("model_path")
        self.base_model = self.config.get("base_model", "Qwen/Qwen3-VL-8B-Instruct")
        self.device = self.config.get("device", "cpu")
        self.compute_type = self.config.get("compute_type", "fp8")
        self.max_fps = self.config.get("screenshot_fps", 2)

        # 状态
        self._capability = VisionCapability.NONE
        self._capture_backend = None       # "mss" or "pillow"
        self._vlm_backend = None          # "transformers" or "api" or None
        self._model = None
        self._processor = None
        self._tokenizer = None
        self._last_screenshot: Optional[np.ndarray] = None
        self._last_screenshot_time: float = 0.0
        self._screenshot_lock = threading.Lock()
        self._stop_continuous = threading.Event()
        self._continuous_thread: Optional[threading.Thread] = None

        self._init_backends()

    # ==================== 后端初始化 ====================

    def _init_backends(self):
        """按优先级初始化截图后端和 VLM 后端"""
        # 1. 截图后端
        try:
            import mss
            self._capture_backend = "mss"
            self._mss = mss.mss()
            print("[Vision] ✅ mss 已加载，截图后端: mss")
        except ImportError:
            try:
                from PIL import ImageGrab
                self._capture_backend = "pillow"
                print("[Vision] ⚠️ mss 未安装，使用 Pillow 截图后端")
            except ImportError:
                print("[Vision] ❌ mss 和 Pillow 都未安装，截图功能不可用")
                return

        # 基础能力就绪
        self._capability = VisionCapability.SCREENSHOT

        # 2. OCR 备选（pytesseract）
        try:
            import pytesseract
            self._capability = VisionCapability.BASIC_OCR
            print("[Vision] ✅ pytesseract 已加载，基础 OCR 可用")
        except ImportError:
            pass

        # 3. VLM 后端（延迟加载，避免启动时阻塞）
        self._vlm_model_path = self._resolve_model_path()
        if self._vlm_model_path and self._vlm_model_path.exists():
            print(f"[Vision] ℹ️ VLM 模型路径已就绪: {self._vlm_model_path}")
            # 不立即加载模型，首次调用时懒加载
        else:
            print(f"[Vision] ℹ️ VLM 模型未找到，将在首次调用时尝试下载/加载")

    def _resolve_model_path(self) -> Optional[Path]:
        """解析模型路径"""
        if not self.model_path:
            return None
        path = Path(self.model_path)
        if path.is_absolute():
            return path
        if self.root:
            return self.root / path
        return path

    def _load_vlm(self) -> bool:
        """懒加载 VLM 模型"""
        if self._capability == VisionCapability.VLM:
            return True
        if self._capability.value < VisionCapability.SCREENSHOT.value:
            return False

        try:
            import torch
            from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor, AutoTokenizer
            from qwen_vl_utils import process_vision_info

            model_path = str(self._resolve_model_path() or self.base_model)
            print(f"[Vision] 🔄 正在加载 VLM 模型: {model_path} ...")

            # 加载模型（支持 FP8/INT8/INT4 量化）
            load_kwargs = {
                "torch_dtype": torch.float32 if self.device == "cpu" else torch.bfloat16,
                "device_map": "auto" if torch.cuda.is_available() else None,
                "low_cpu_mem_usage": True,
            }

            # 量化配置
            if self.compute_type == "int4":
                try:
                    from transformers import BitsAndBytesConfig
                    load_kwargs["quantization_config"] = BitsAndBytesConfig(
                        load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16
                    )
                    print("[Vision] ℹ️ 使用 INT4 量化加载")
                except ImportError:
                    print("[Vision] ⚠️ bitsandbytes 未安装，回退到 fp16")
            elif self.compute_type == "int8":
                load_kwargs["load_in_8bit"] = True

            self._model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                model_path, **load_kwargs
            )
            self._processor = AutoProcessor.from_pretrained(model_path)
            self._tokenizer = AutoTokenizer.from_pretrained(model_path)
            self._process_vision_info = process_vision_info

            self._capability = VisionCapability.VLM
            print("[Vision] ✅ VLM 模型加载完成，视觉理解能力就绪")
            return True

        except Exception as e:
            print(f"[Vision] ❌ VLM 模型加载失败: {e}")
            print("[Vision] ℹ️ 视觉模块降级为截图+OCR模式")
            return False

    # ==================== 截图能力 ====================

    def get_capability(self) -> VisionCapability:
        return self._capability

    def is_ready(self) -> bool:
        return self._capability.value >= VisionCapability.SCREENSHOT.value

    def can_understand(self) -> bool:
        """是否具备视觉理解能力（VLM）"""
        return self._capability == VisionCapability.VLM

    def capture_screen(self, monitor: Optional[int] = None, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[np.ndarray]:
        """
        截取屏幕

        Args:
            monitor: 显示器索引（None=主屏，-1=所有显示器拼接）
            region: 区域截图 (left, top, width, height)

        Returns:
            RGB numpy array (H, W, 3) or None
        """
        try:
            if self._capture_backend == "mss":
                return self._capture_mss(monitor, region)
            elif self._capture_backend == "pillow":
                return self._capture_pillow(region)
            else:
                return None
        except Exception as e:
            print(f"[Vision] 截图失败: {e}")
            return None

    def _capture_mss(self, monitor: Optional[int], region: Optional[Tuple[int, int, int, int]]) -> Optional[np.ndarray]:
        """使用 mss 截图"""
        import mss
        if not hasattr(self, '_mss') or self._mss is None:
            self._mss = mss.mss()

        if region:
            left, top, width, height = region
            mon = {"left": left, "top": top, "width": width, "height": height}
        else:
            if monitor is None or monitor == -1:
                mon = self._mss.monitors[0]  # 所有显示器
            else:
                mon = self._mss.monitors[monitor + 1] if monitor + 1 < len(self._mss.monitors) else self._mss.monitors[1]

        sct_img = self._mss.grab(mon)
        img = np.array(sct_img)[:, :, :3]  # RGBA -> RGB
        return img

    def _capture_pillow(self, region: Optional[Tuple[int, int, int, int]]) -> Optional[np.ndarray]:
        """使用 Pillow 截图"""
        from PIL import ImageGrab
        if region:
            left, top, width, height = region
            img = ImageGrab.grab(bbox=(left, top, left + width, top + height))
        else:
            img = ImageGrab.grab()
        return np.array(img)[:, :, :3]

    def capture_to_file(self, path: Path, monitor: Optional[int] = None) -> bool:
        """截图保存到文件"""
        img = self.capture_screen(monitor=monitor)
        if img is None:
            return False
        try:
            from PIL import Image
            Image.fromarray(img).save(str(path))
            return True
        except Exception as e:
            print(f"[Vision] 保存截图失败: {e}")
            return False

    def start_continuous_capture(self, interval: float = 0.5, callback: Optional[callable] = None):
        """启动后台连续截图线程（用于实时监控）"""
        if self._continuous_thread and self._continuous_thread.is_alive():
            return
        self._stop_continuous.clear()

        def _loop():
            while not self._stop_continuous.is_set():
                img = self.capture_screen()
                if img is not None:
                    with self._screenshot_lock:
                        self._last_screenshot = img
                        self._last_screenshot_time = time.time()
                    if callback:
                        try:
                            callback(img)
                        except Exception:
                            pass
                self._stop_continuous.wait(interval)

        self._continuous_thread = threading.Thread(target=_loop, daemon=True, name="LingShu-Vision-Capture")
        self._continuous_thread.start()
        print(f"[Vision] 🎥 连续截图线程已启动，间隔 {interval}s")

    def stop_continuous_capture(self):
        """停止连续截图"""
        self._stop_continuous.set()
        if self._continuous_thread:
            self._continuous_thread.join(timeout=2)

    def get_latest_screenshot(self) -> Optional[np.ndarray]:
        """获取最近一次截图"""
        with self._screenshot_lock:
            return self._last_screenshot.copy() if self._last_screenshot is not None else None

    # ==================== 图像预处理 ====================

    def _preprocess_image(self, image: np.ndarray, target_pixels: Optional[int] = None) -> Image.Image:
        """预处理图像：调整尺寸、转 PIL"""
        from PIL import Image
        target_pixels = target_pixels or self.TARGET_PIXELS

        h, w = image.shape[:2]
        current_pixels = h * w

        if current_pixels > target_pixels * 2:
            # 按比例缩小
            scale = (target_pixels / current_pixels) ** 0.5
            new_w, new_h = int(w * scale), int(h * scale)
            image = Image.fromarray(image).resize((new_w, new_h), Image.Resampling.LANCZOS)
        else:
            image = Image.fromarray(image)

        return image

    def _encode_image_base64(self, image: Union[np.ndarray, Image.Image], max_size: Optional[Tuple[int, int]] = None) -> str:
        """将图像编码为 base64 字符串（用于 VLM 输入）"""
        from PIL import Image
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)

        if max_size:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)

        buffered = io.BytesIO()
        image.save(buffered, format="JPEG", quality=self.JPEG_QUALITY)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    # ==================== VLM 视觉理解 ====================

    def analyze(self, query: str, image: Optional[np.ndarray] = None, screenshot: bool = True) -> VisionAnalysisResult:
        """
        视觉分析主入口

        Args:
            query: 视觉查询，如 "屏幕上有什么？"、"定位'文件'按钮"、"描述当前界面"
            image: 直接传入图像（None 则自动截图）
            screenshot: 是否自动截图（image 为 None 时生效）

        Returns:
            VisionAnalysisResult: 结构化分析结果
        """
        # 获取图像
        if image is None and screenshot:
            image = self.capture_screen()

        if image is None:
            return VisionAnalysisResult(
                query=query,
                scene_description="截图失败，无法获取图像",
                elements=[],
                suggested_actions=[],
            )

        # 如果 VLM 不可用，降级为 OCR/描述
        if not self.can_understand():
            return self._fallback_analyze(query, image)

        # 确保 VLM 已加载
        if not self._load_vlm():
            return self._fallback_analyze(query, image)

        # VLM 推理
        return self._vlm_analyze(query, image)

    def _vlm_analyze(self, query: str, image: np.ndarray) -> VisionAnalysisResult:
        """使用 VLM 进行视觉理解"""
        try:
            from PIL import Image

            pil_img = self._preprocess_image(image)
            b64_image = self._encode_image_base64(pil_img)

            # 构建 Qwen-VL 对话格式
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": f"data:image/jpeg;base64,{b64_image}"},
                        {"type": "text", "text": self._build_prompt(query)},
                    ],
                }
            ]

            # 处理输入
            text = self._processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            image_inputs, video_inputs = self._process_vision_info(messages)
            inputs = self._processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
            inputs = inputs.to(self._model.device)

            # 生成
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                generated_ids = self._model.generate(**inputs, max_new_tokens=512, do_sample=False)
                generated_ids_trimmed = [
                    out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
                ]
                output_text = self._processor.batch_decode(
                    generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
                )[0]

            # 解析输出
            return self._parse_vlm_response(query, output_text, image)

        except Exception as e:
            print(f"[Vision] VLM 推理失败: {e}")
            return self._fallback_analyze(query, image)

    def _build_prompt(self, query: str) -> str:
        """构建 VLM 提示词"""
        base = """你是一个桌面视觉助手。请分析用户提供的屏幕截图，并以 JSON 格式回答。

请分析以下内容：
1. 整体场景描述（当前是什么界面/窗口/应用）
2. 可见的 UI 元素列表（按钮、图标、文本框、链接等），每个元素包含：类型、描述、大致位置（屏幕坐标）、是否可点击
3. 如果用户有特定指令，提供建议的操作步骤

请用以下 JSON 格式回答：
{
  "scene": "场景描述",
  "elements": [
    {"type": "button", "desc": "保存按钮", "bbox": [x1,y1,x2,y2], "action": "clickable"}
  ],
  "actions": [
    {"action": "click", "target": "元素描述", "coords": [x, y], "reason": "原因"}
  ]
}

用户指令："""
        return base + query

    def _parse_vlm_response(self, query: str, response: str, image: np.ndarray) -> VisionAnalysisResult:
        """解析 VLM 输出为结构化结果"""
        # 尝试提取 JSON
        try:
            # 找 JSON 块
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
            else:
                data = {}

            scene = data.get("scene", response[:200])  # 降级：取前200字
            elements = []
            for e in data.get("elements", []):
                bbox = e.get("bbox", [0, 0, 0, 0])
                if isinstance(bbox, list) and len(bbox) == 4:
                    bbox = tuple(bbox)
                else:
                    bbox = (0, 0, 0, 0)
                elements.append(ScreenElement(
                    element_id=e.get("id", f"elem_{len(elements)}"),
                    element_type=e.get("type", "unknown"),
                    description=e.get("desc", ""),
                    bbox=bbox,
                    text_content=e.get("text"),
                    confidence=e.get("confidence", 0.8),
                    action_hint=e.get("action"),
                ))

            actions = data.get("actions", [])
            return VisionAnalysisResult(
                query=query,
                scene_description=scene,
                elements=elements,
                suggested_actions=actions,
                raw_response=response,
            )
        except Exception as e:
            print(f"[Vision] VLM 响应解析失败: {e}")
            return VisionAnalysisResult(
                query=query,
                scene_description=response[:300],
                elements=[],
                suggested_actions=[],
                raw_response=response,
            )

    def _fallback_analyze(self, query: str, image: np.ndarray) -> VisionAnalysisResult:
        """降级分析：仅使用 OCR + 简单描述"""
        elements = []
        scene = "屏幕截图（VLM 未加载，使用降级分析）"

        # 尝试 OCR
        if self._capability.value >= VisionCapability.BASIC_OCR.value:
            try:
                import pytesseract
                from PIL import Image
                pil_img = Image.fromarray(image)
                text = pytesseract.image_to_string(pil_img, lang="chi_sim+eng")
                if text.strip():
                    elements.append(ScreenElement(
                        element_id="ocr_text_1",
                        element_type="text",
                        description=f"识别到的文本: {text[:100]}...",
                        bbox=(0, 0, image.shape[1], image.shape[0]),
                        text_content=text,
                        confidence=0.6,
                        action_hint="readable",
                    ))
                    scene = f"包含文本的界面，识别内容: {text[:80]}..."
            except Exception as e:
                print(f"[Vision] OCR 失败: {e}")

        # 基础图像统计
        if not elements:
            scene = f"屏幕截图，尺寸 {image.shape[1]}x{image.shape[0]}，无法识别具体内容（VLM 未加载）"

        return VisionAnalysisResult(
            query=query,
            scene_description=scene,
            elements=elements,
            suggested_actions=[],
        )

    # ==================== 高级视觉任务 ====================

    def locate_element(self, description: str, image: Optional[np.ndarray] = None) -> Optional[Tuple[int, int, int, int]]:
        """
        定位屏幕上的元素

        Args:
            description: 元素描述，如 "左上角的后退按钮"、"文件菜单"

        Returns:
            (x1, y1, x2, y2) 坐标，或 None
        """
        result = self.analyze(f"定位元素: {description}", image=image)
        for elem in result.elements:
            if description.lower() in elem.description.lower() or description.lower() in (elem.text_content or "").lower():
                return elem.bbox
        # 返回整个屏幕作为 fallback
        return None

    def describe_screen(self, image: Optional[np.ndarray] = None) -> str:
        """描述当前屏幕内容（自然语言）"""
        result = self.analyze("请描述当前屏幕上显示的内容", image=image)
        return result.scene_description

    def understand_instruction(self, instruction: str, image: Optional[np.ndarray] = None) -> Dict:
        """
        理解包含视觉指代的指令

        示例：
          "打开这个文件" → 识别当前聚焦/选中的文件
          "点击那个红色按钮" → 定位红色按钮并返回坐标
          "把这张图保存下来" → 识别图片元素并返回保存操作
        """
        result = self.analyze(f"用户指令: {instruction}。请识别指代的对象并提供操作方案", image=image)
        return {
            "instruction": instruction,
            "scene": result.scene_description,
            "target_elements": [
                {
                    "id": e.element_id,
                    "type": e.element_type,
                    "desc": e.description,
                    "bbox": e.bbox,
                    "text": e.text_content,
                }
                for e in result.elements
            ],
            "actions": result.suggested_actions,
            "raw": result.raw_response,
        }

    # ==================== 工具方法 ====================

    def get_screen_size(self) -> Tuple[int, int]:
        """获取主屏幕分辨率"""
        if self._capture_backend == "mss":
            import mss
            if not hasattr(self, '_mss') or self._mss is None:
                self._mss = mss.mss()
            mon = self._mss.monitors[1] if len(self._mss.monitors) > 1 else self._mss.monitors[0]
            return (mon["width"], mon["height"])
        else:
            img = self.capture_screen()
            if img is not None:
                return (img.shape[1], img.shape[0])
            return (1920, 1080)

    def draw_debug_overlay(self, image: np.ndarray, result: VisionAnalysisResult) -> np.ndarray:
        """在图像上绘制检测框（调试用）"""
        from PIL import Image, ImageDraw, ImageFont
        pil_img = Image.fromarray(image).copy()
        draw = ImageDraw.Draw(pil_img)
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font = ImageFont.load_default()

        for elem in result.elements:
            x1, y1, x2, y2 = elem.bbox
            draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
            label = f"{elem.element_type}: {elem.description[:20]}"
            draw.text((x1, max(0, y1 - 20)), label, fill="red", font=font)

        return np.array(pil_img)

    def __del__(self):
        """清理资源"""
        self.stop_continuous_capture()
        if hasattr(self, '_mss') and self._mss is not None:
            try:
                self._mss.close()
            except Exception:
                pass
