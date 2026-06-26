#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 语音交互模块（Phase 2 完整实现）
功能：语音活动检测（VAD）→ 录音 → ASR（Whisper）→ NLU（Qwen2.5）→ 意图结构化

架构：
  VADRecorder   — 基于 webrtcvad + sounddevice 的实时语音检测与录音
  WhisperASR    — 基于 faster-whisper 的本地语音识别
  NLUProcessor  — 基于 transformers 的意图理解（Qwen2.5-1.5B-Instruct）
  VoiceModule   — 主控模块，协调 VAD → ASR → NLU → 唤醒词过滤

降级策略：
  - 如果 faster-whisper 不可用 → 尝试 openai-whisper → 降级为文本输入
  - 如果 transformers 不可用 → 使用基于规则的意图解析
  - 如果 sounddevice 不可用 → 完全降级为键盘输入
"""

import json
import re
import threading
import time
import wave
from collections import deque
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


# ============================================================
# 工具函数
# ============================================================

def _find_model_path(model_path: str, root: Path) -> Optional[Path]:
    """解析模型路径（支持绝对路径、相对路径、自动补全）"""
    if not model_path:
        return None
    p = Path(model_path)
    if p.is_absolute():
        return p if p.exists() else None
    # 相对灵枢根目录
    p = root / model_path
    return p if p.exists() else None


# ============================================================
# VAD 录音器
# ============================================================

class VADRecorder:
    """
    基于 WebRTC VAD 的语音活动检测录音器
    支持：实时流式检测、自动开始/停止录音、噪声过滤
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        vad_aggressiveness: int = 3,
        padding_duration_ms: int = 300,
        max_recording_seconds: float = 30.0,
    ):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        self.vad_aggressiveness = vad_aggressiveness
        self.padding_duration_ms = padding_duration_ms
        self.max_recording_seconds = max_recording_seconds

        self._vad = None
        self._available = False

        try:
            import webrtcvad
            self._vad = webrtcvad.Vad(vad_aggressiveness)
            self._available = True
        except ImportError:
            pass

    def is_available(self) -> bool:
        return self._available

    def _record_frames(
        self,
        duration: float,
        on_frame: Callable[[bytes], bool],
        stop_event: Optional[threading.Event] = None,
    ) -> bool:
        """
        录音指定时长，每帧回调 on_frame(frame)
        on_frame 返回 True 表示继续录音，False 表示停止
        """
        import sounddevice as sd

        frames = []
        start_time = time.time()

        def callback(indata, frame_count, time_info, status):
            if status:
                print(f"[VAD] 录音状态: {status}")
            frames.append(indata.copy())

        # 使用阻塞式录音
        num_frames = int(duration * self.sample_rate / self.frame_size)
        for _ in range(num_frames):
            if stop_event and stop_event.is_set():
                break
            frame = sd.rec(
                self.frame_size,
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocking=True,
            )
            frame_bytes = frame.tobytes()
            if not on_frame(frame_bytes):
                break

        return True

    def record_until_silence(
        self,
        stop_event: Optional[threading.Event] = None,
    ) -> Tuple[Optional[bytes], float]:
        """
        检测语音活动开始，记录直到语音结束（静音超时）
        返回: (audio_bytes, duration_seconds)
        """
        if not self._available:
            return None, 0.0

        import sounddevice as sd

        ring_buffer = deque(maxlen=int(self.padding_duration_ms / self.frame_duration_ms))
        triggered = False
        voiced_frames = []
        start_time = time.time()
        max_frames = int(self.max_recording_seconds * 1000 / self.frame_duration_ms)
        frame_count = 0

        print("[VAD] 正在监听...")

        while frame_count < max_frames:
            if stop_event and stop_event.is_set():
                break

            frame = sd.rec(
                self.frame_size,
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocking=True,
            )
            frame_bytes = frame.tobytes()
            is_speech = self._vad.is_speech(frame_bytes, self.sample_rate)

            if not triggered:
                ring_buffer.append(frame_bytes)
                if is_speech:
                    triggered = True
                    voiced_frames.extend(ring_buffer)
                    ring_buffer.clear()
                    print("[VAD] 语音开始")
            else:
                voiced_frames.append(frame_bytes)
                if not is_speech:
                    ring_buffer.append(frame_bytes)
                    if len(ring_buffer) >= ring_buffer.maxlen:
                        print("[VAD] 语音结束（静音超时）")
                        break
                else:
                    ring_buffer.clear()

            frame_count += 1

        duration = time.time() - start_time
        if voiced_frames:
            audio = b"".join(voiced_frames)
            return audio, duration
        return None, 0.0

    def record_fixed_duration(self, duration: float = 5.0) -> Tuple[Optional[bytes], float]:
        """录制固定时长的音频"""
        import sounddevice as sd

        print(f"[VAD] 录制 {duration} 秒...")
        frames = sd.rec(
            int(self.sample_rate * duration),
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            blocking=True,
        )
        audio = frames.tobytes()
        return audio, duration


# ============================================================
# Whisper ASR 引擎
# ============================================================

class WhisperASR:
    """
    基于 faster-whisper 的语音识别引擎
    支持：本地模型、多语言、CPU/GPU 推理、量化
    """

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "zh",
        root: Path = Path("."),
    ):
        self.model_path = model_path
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.root = root

        self._model = None
        self._available = False
        self._load_error = None

        self._load()

    def _load(self):
        """加载模型"""
        try:
            from faster_whisper import WhisperModel

            model_path = _find_model_path(self.model_path, self.root)

            if model_path is None:
                # 尝试使用模型名称（在线下载或缓存）
                model_path = self.model_path
                print(f"[ASR] 未找到本地模型，尝试在线加载或缓存: {model_path}")
            else:
                print(f"[ASR] 加载本地模型: {model_path}")

            self._model = WhisperModel(
                str(model_path),
                device=self.device,
                compute_type=self.compute_type,
            )
            self._available = True
            print(f"[ASR] Whisper 模型加载成功 (device={self.device}, compute={self.compute_type})")

        except ImportError:
            self._load_error = "faster-whisper 未安装"
            print(f"[ASR] ⚠️ {self._load_error}")
        except Exception as e:
            self._load_error = f"模型加载失败: {e}"
            print(f"[ASR] ❌ {self._load_error}")

    def is_available(self) -> bool:
        return self._available

    def transcribe(self, audio_bytes: bytes) -> Optional[str]:
        """
        将音频字节转录为文本
        audio_bytes: 16kHz, 16-bit, mono PCM 音频
        """
        if not self._available:
            return None

        import numpy as np

        try:
            # bytes → numpy float32
            audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            segments, info = self._model.transcribe(
                audio_array,
                language=self.language if self.language != "auto" else None,
                beam_size=5,
                vad_filter=True,  # 使用 faster-whisper 内置 VAD 过滤
                vad_parameters=dict(min_silence_duration_ms=500),
            )

            text = " ".join([segment.text for segment in segments]).strip()
            return text

        except Exception as e:
            print(f"[ASR] 转录失败: {e}")
            return None


# ============================================================
# NLU 意图处理器
# ============================================================

class NLUProcessor:
    """
    基于 Qwen2.5-1.5B-Instruct 的意图理解处理器
    将自然语言转换为结构化操作指令

    输出格式（JSON）：
    {
        "intent": "open" | "close" | "click" | "type" | "scroll" | "search" | "execute" | "query" | "unknown",
        "target": "软件名/元素描述/文件路径",
        "params": {"key": "value"},
        "confidence": 0.0~1.0,
        "raw_text": "原始用户输入"
    }
    """

    INTENT_PROMPT = """你是一个专门解析电脑操作指令的AI助手。请将用户说的话解析为结构化的JSON操作指令。

可识别的意图类型：
- open: 打开/启动软件或文件
- close: 关闭/退出软件
- click: 点击某个按钮或元素
- type: 输入文字
- scroll: 滚动页面
- screenshot: 截图
- search: 搜索内容
- execute: 执行命令或操作序列
- query: 查询信息或状态
- unknown: 无法识别的意图

用户指令："{text}"

请只输出JSON，不要有任何其他文字："""

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        max_tokens: int = 512,
        temperature: float = 0.3,
        root: Path = Path("."),
    ):
        self.model_path = model_path
        self.device = device
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.root = root

        self._tokenizer = None
        self._model = None
        self._pipeline = None
        self._available = False
        self._load_error = None

        self._load()

    def _load(self):
        """加载模型"""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
            import torch

            model_path = _find_model_path(self.model_path, self.root)
            if model_path is None:
                model_path = self.model_path
                print(f"[NLU] 未找到本地模型，尝试在线加载或缓存: {model_path}")
            else:
                print(f"[NLU] 加载本地模型: {model_path}")

            self._tokenizer = AutoTokenizer.from_pretrained(
                str(model_path),
                trust_remote_code=True,
            )

            self._model = AutoModelForCausalLM.from_pretrained(
                str(model_path),
                torch_dtype=torch.float32 if self.device == "cpu" else torch.float16,
                device_map="auto" if self.device != "cpu" else None,
                trust_remote_code=True,
            )

            if self.device == "cpu":
                self._model = self._model.to("cpu")

            self._pipeline = pipeline(
                "text-generation",
                model=self._model,
                tokenizer=self._tokenizer,
                max_new_tokens=self.max_tokens,
                temperature=self.temperature,
                do_sample=True,
                return_full_text=False,
            )

            self._available = True
            print(f"[NLU] 意图理解模型加载成功 (device={self.device})")

        except ImportError:
            self._load_error = "transformers/torch 未安装"
            print(f"[NLU] ⚠️ {self._load_error}")
        except Exception as e:
            self._load_error = f"模型加载失败: {e}"
            print(f"[NLU] ❌ {self._load_error}")

    def is_available(self) -> bool:
        return self._available

    def understand(self, text: str) -> Dict:
        """
        解析用户意图，返回结构化指令
        如果模型不可用，回退到基于规则的正则解析
        """
        if self._available:
            return self._understand_with_llm(text)
        else:
            return self._understand_with_rules(text)

    def _understand_with_llm(self, text: str) -> Dict:
        """使用 LLM 进行意图理解"""
        try:
            prompt = self.INTENT_PROMPT.format(text=text)
            messages = [{"role": "user", "content": prompt}]

            # 使用 chat template（如果支持）
            if hasattr(self._tokenizer, "apply_chat_template"):
                prompt_text = self._tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
            else:
                prompt_text = prompt

            outputs = self._pipeline(prompt_text)
            generated = outputs[0]["generated_text"]

            # 提取 JSON
            result = self._extract_json(generated)
            result["raw_text"] = text
            result["source"] = "llm"
            return result

        except Exception as e:
            print(f"[NLU] LLM 解析失败: {e}，回退到规则解析")
            return self._understand_with_rules(text)

    def _understand_with_rules(self, text: str) -> Dict:
        """基于规则的正则解析（降级方案）"""
        text_lower = text.lower()

        # 意图识别规则
        rules = [
            (r"打开|启动|运行|开启", "open"),
            (r"关闭|退出|关掉|结束", "close"),
            (r"点击|按下|点一下", "click"),
            (r"输入|打字|填写|写入", "type"),
            (r"滚动|下滑|上滑|翻页", "scroll"),
            (r"截图|截屏|拍个照", "screenshot"),
            (r"搜索|查找|查一下", "search"),
            (r"执行|运行|调用", "execute"),
            (r"查看|显示|告诉我", "query"),
        ]

        intent = "unknown"
        for pattern, intent_type in rules:
            if re.search(pattern, text_lower):
                intent = intent_type
                break

        # 目标提取（简单启发式）
        target = ""
        software_names = [
            "photoshop", "ps", "ppt", "powerpoint", "excel", "word",
            "chrome", "浏览器", "edge", "firefox", "微信", "qq",
            "文件管理器", "计算器", "记事本", "终端", "命令行",
            "vscode", "idea", "pycharm", "音乐", "视频", "播放器",
        ]

        for name in software_names:
            if name in text_lower:
                target = name
                break

        # 如果没找到软件名，尝试提取引号内容或后面的名词
        if not target:
            match = re.search(r'[\"'](.+?)[\"']', text)
            if match:
                target = match.group(1)
            else:
                # 提取动词后的名词短语
                match = re.search(r'(?:打开|启动|关闭|点击|输入|搜索|查找|查看|运行)\s*([\u4e00-\u9fa5a-zA-Z0-9_\-]+)', text_lower)
                if match:
                    target = match.group(1)

        return {
            "intent": intent,
            "target": target,
            "params": {},
            "confidence": 0.5 if intent != "unknown" else 0.0,
            "raw_text": text,
            "source": "rule",
        }

    @staticmethod
    def _extract_json(text: str) -> Dict:
        """从 LLM 输出中提取 JSON"""
        # 尝试直接找到 JSON 块
        try:
            # 先尝试直接解析整个文本
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json 代码块
        code_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取最外层的大括号
        brace_match = re.search(r'\{.*\}', text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        # 兜底：返回未知意图
        return {"intent": "unknown", "target": "", "params": {}, "confidence": 0.0}


# ============================================================
# 语音主控模块
# ============================================================

class VoiceModule:
    """
    灵枢语音交互主控模块
    协调 VAD → ASR → NLU 的完整流程
    """

    def __init__(
        self,
        voice_config: dict,
        asr_config: dict,
        nlu_config: Optional[dict] = None,
        root: Path = Path("."),
    ):
        self.voice_config = voice_config or {}
        self.asr_config = asr_config or {}
        self.nlu_config = nlu_config or {}
        self.root = root

        # 配置项
        self.wake_word = self.voice_config.get("wake_word", "灵枢")
        self.skip_wake_word = self.voice_config.get("skip_wake_word", False)
        self.max_recording_seconds = self.voice_config.get("max_recording_seconds", 30)
        self.vad_sensitivity = self.voice_config.get("vad_sensitivity", 3)
        self.sample_rate = self.voice_config.get("sample_rate", 16000)

        # 子模块
        self._vad: Optional[VADRecorder] = None
        self._asr: Optional[WhisperASR] = None
        self._nlu: Optional[NLUProcessor] = None

        self._ready = False
        self._stop_event = threading.Event()
        self._listening_thread: Optional[threading.Thread] = None
        self._on_intent_callback: Optional[Callable[[Dict], None]] = None

        self._init()

    def _init(self):
        """初始化所有子模块"""
        print("[Voice] 初始化语音模块...")

        # 1. VAD
        try:
            self._vad = VADRecorder(
                sample_rate=self.sample_rate,
                vad_aggressiveness=self.vad_sensitivity,
                max_recording_seconds=self.max_recording_seconds,
            )
            if self._vad.is_available():
                print("[Voice] VAD 录音器已就绪")
            else:
                print("[Voice] ⚠️ VAD 不可用（webrtcvad 或 sounddevice 未安装）")
        except Exception as e:
            print(f"[Voice] ⚠️ VAD 初始化失败: {e}")

        # 2. ASR
        try:
            self._asr = WhisperASR(
                model_path=self.asr_config.get("model_path", "tiny"),
                device=self.asr_config.get("device", "cpu"),
                compute_type=self.asr_config.get("compute_type", "int8"),
                language=self.asr_config.get("language", "zh"),
                root=self.root,
            )
            if self._asr.is_available():
                print("[Voice] ASR 已就绪")
            else:
                print(f"[Voice] ⚠️ ASR 不可用: {self._asr._load_error}")
        except Exception as e:
            print(f"[Voice] ⚠️ ASR 初始化失败: {e}")

        # 3. NLU
        try:
            nlu_path = self.nlu_config.get("model_path", "")
            if nlu_path:
                self._nlu = NLUProcessor(
                    model_path=nlu_path,
                    device=self.nlu_config.get("device", "cpu"),
                    max_tokens=self.nlu_config.get("max_tokens", 512),
                    temperature=self.nlu_config.get("temperature", 0.3),
                    root=self.root,
                )
                if self._nlu.is_available():
                    print("[Voice] NLU 已就绪")
                else:
                    print(f"[Voice] ⚠️ NLU 不可用: {self._nlu._load_error}")
            else:
                print("[Voice] NLU 模型路径未配置，仅使用规则解析")
                self._nlu = NLUProcessor("", root=self.root)  # 规则模式
        except Exception as e:
            print(f"[Voice] ⚠️ NLU 初始化失败: {e}")
            self._nlu = NLUProcessor("", root=self.root)

        # 判断整体就绪状态
        self._ready = (
            self._vad is not None and self._vad.is_available() and
            self._asr is not None and self._asr.is_available()
        )

        if self._ready:
            print("[Voice] ✅ 语音模块完全就绪（VAD + ASR + NLU）")
        elif self._asr is not None and self._asr.is_available():
            print("[Voice] ⚠️ 语音模块部分就绪（ASR 可用，但 VAD 不可用）")
        else:
            print("[Voice] ❌ 语音模块未就绪，将回退到文本输入模式")

    def is_ready(self) -> bool:
        return self._ready

    def is_partial_ready(self) -> bool:
        """ASR 可用但 VAD 不可用（可手动提供音频文件）"""
        return self._asr is not None and self._asr.is_available()

    def transcribe_audio(self, audio_bytes: bytes) -> Optional[str]:
        """直接转录音频字节为文本"""
        if self._asr is None or not self._asr.is_available():
            return None
        return self._asr.transcribe(audio_bytes)

    def understand_intent(self, text: str) -> Dict:
        """解析文本意图"""
        if self._nlu is None:
            return NLUProcessor._understand_with_rules(text)
        return self._nlu.understand(text)

    def process_text(self, text: str) -> Dict:
        """
        完整处理文本：唤醒词检测 → 意图理解
        返回结构化指令
        """
        result = {
            "text": text,
            "wake_word_detected": False,
            "intent": None,
        }

        # 唤醒词检测
        if self.wake_word and not self.skip_wake_word:
            if self.wake_word.lower() in text.lower():
                result["wake_word_detected"] = True
                print(f"[Voice] 唤醒词检测到: '{self.wake_word}'")
            else:
                print(f"[Voice] 未检测到唤醒词 '{self.wake_word}'，忽略")
                result["intent"] = {"intent": "idle", "raw_text": text, "source": "wake_filter"}
                return result

        # 意图理解
        intent = self.understand_intent(text)
        result["intent"] = intent
        return result

    def record_and_transcribe(self, duration: Optional[float] = None) -> Optional[str]:
        """
        录音并转录为文本
        duration: None 表示使用 VAD 自动检测，否则录制固定秒数
        """
        if self._vad is None or not self._vad.is_available():
            print("[Voice] VAD 不可用，无法录音。请使用文本输入或提供音频文件。")
            return None

        if duration is not None:
            audio, _ = self._vad.record_fixed_duration(duration)
        else:
            audio, _ = self._vad.record_until_silence(stop_event=self._stop_event)

        if audio is None:
            print("[Voice] 未检测到语音")
            return None

        print("[Voice] 检测到语音，正在转录...")
        return self.transcribe_audio(audio)

    def record_and_understand(self, duration: Optional[float] = None) -> Optional[Dict]:
        """
        完整流程：录音 → 转录 → 意图理解
        返回结构化指令
        """
        text = self.record_and_transcribe(duration)
        if text is None:
            return None

        print(f"[Voice] ASR 结果: \"{text}\"")
        return self.process_text(text)

    def start_continuous_listening(self, callback: Callable[[Dict], None]):
        """
        启动持续监听模式（后台线程）
        callback: 检测到意图时的回调函数
        """
        if not self._ready:
            print("[Voice] 语音模块未就绪，无法启动监听")
            return

        self._on_intent_callback = callback
        self._stop_event.clear()

        self._listening_thread = threading.Thread(
            target=self._listening_loop,
            daemon=True,
            name="LingShu-VoiceListener",
        )
        self._listening_thread.start()
        print("[Voice] 已启动持续监听模式（唤醒词 + VAD）")

    def stop_continuous_listening(self):
        """停止持续监听"""
        self._stop_event.set()
        if self._listening_thread and self._listening_thread.is_alive():
            self._listening_thread.join(timeout=2)
        print("[Voice] 已停止监听")

    def _listening_loop(self):
        """持续监听循环"""
        while not self._stop_event.is_set():
            try:
                result = self.record_and_understand()
                if result and self._on_intent_callback:
                    self._on_intent_callback(result)
            except Exception as e:
                print(f"[Voice] 监听循环异常: {e}")
                time.sleep(0.5)

    def save_audio(self, audio_bytes: bytes, path: Path):
        """将音频保存为 WAV 文件"""
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_bytes)

    def load_audio(self, path: Path) -> bytes:
        """从 WAV 文件加载音频"""
        with wave.open(str(path), "rb") as wf:
            return wf.readframes(wf.getnframes())
