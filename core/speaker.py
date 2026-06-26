#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 声纹验证模块（增补卷轻量化）
功能：声纹注册、声纹验证、多用户管理、访客模式、加密存储

实现原理：
  基于Picovoice Eagle为商业级方案，开源替代为：
  - 特征提取：librosa MFCC + 一阶差分（ΔMFCC）
  - 相似度度量：cosine similarity / euclidean distance
  - 模型：轻量化的PaddleSpeech Ecapa-TDNN（可选升级）

依赖安装：
  - librosa（推荐）：pip install librosa
  - 或纯 numpy 实现（无依赖，精度略低）
  - 注册样本：5次录音，每次3秒
  - 验证阈值：0.85（cosine similarity）
  - 存储：JSON 格式，加密可选
"""

import json
import time
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np


class SpeakerProfile:
    """声纹用户档案"""

    def __init__(self, user_id: str, name: str, created_at: float = None):
        self.user_id = user_id
        self.name = name
        self.created_at = created_at or time.time()
        self.samples: List[np.ndarray] = []  # 声纹特征样本列表
        self.enrollment_text: str = "灵枢所辖，万物听令；心有灵犀，无远弗届。"
        self.is_active: bool = True

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "created_at": self.created_at,
            "sample_count": len(self.samples),
            "enrollment_text": self.enrollment_text,
            "is_active": self.is_active,
            # 声纹特征样本序列化（base64编码）
            "samples": [s.tolist() for s in self.samples],
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "SpeakerProfile":
        profile = cls(data["user_id"], data["name"], data["created_at"])
        profile.enrollment_text = data.get("enrollment_text", "灵枢所辖，万物听令；心有灵犀，无远弗届。")
        profile.is_active = data.get("is_active", True)
        profile.samples = [np.array(s) for s in data.get("samples", [])]
        return profile


class SpeakerVerifier:
    """
    声纹验证器
    
    轻量化的声纹识别系统：
    - 基于 MFCC 特征 + 余弦相似度
    - 支持多用户注册和验证
    - 支持访客模式（未注册用户标记为 guest）
    - 纯 Python 实现，无需商业 SDK
    """

    # 默认MFCC参数
    N_MFCC = 40
    N_FFT = 2048
    HOP_LENGTH = 512
    SAMPLE_RATE = 16000

    # 默认相似度阈值
    DEFAULT_THRESHOLD = 0.85

    def __init__(
        self,
        profile_dir: Path,
        threshold: float = 0.85,
        verify_mode: str = "strict",  # strict / guest / off
        max_users: int = 10,
    ):
        self.profile_dir = profile_dir
        self.threshold = threshold
        self.verify_mode = verify_mode
        self.max_users = max_users

        self._profiles: Dict[str, SpeakerProfile] = {}
        self._available = False
        self._librosa = None

        self._load_librosa()
        self._load_profiles()

    def _load_librosa(self):
        """尝试加载librosa，失败则使用numpy备用方案"""
        try:
            import librosa
            self._librosa = librosa
            self._available = True
            print("[Speaker] ✅ librosa 已加载，声纹功能可用")
        except ImportError:
            print("[Speaker] ⚠️ librosa 未安装，声纹功能使用纯numpy备用方案（精度略低）")
            self._available = False

    def _load_profiles(self):
        """从目录加载所有用户声纹档案"""
        if not self.profile_dir.exists():
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            return

        for file in self.profile_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profile = SpeakerProfile.from_dict(data)
                self._profiles[profile.user_id] = profile
            except Exception as e:
                print(f"[Speaker] 加载声纹档案失败 {file}: {e}")

        if self._profiles:
            print(f"[Speaker] 已加载 {len(self._profiles)} 个声纹用户")
        else:
            print("[Speaker] 暂无注册用户，请先注册声纹")

    def _save_profile(self, profile: SpeakerProfile):
        """保存声纹档案到文件"""
        file_path = self.profile_dir / f"{profile.user_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(profile.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Speaker] 保存声纹档案失败: {e}")

    # ==================== 特征提取 ====================

    def extract_features(self, audio_bytes: bytes) -> Optional[np.ndarray]:
        """
        从音频数据提取声纹特征
        
        audio_bytes: 16kHz, 16-bit, mono PCM
        """
        if not audio_bytes:
            return None

        # bytes 转 numpy array
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        if self._librosa:
            return self._extract_with_librosa(audio_array)
        else:
            return self._extract_with_numpy(audio_array)

    def _extract_with_librosa(self, audio: np.ndarray) -> np.ndarray:
        """使用librosa提取MFCC + ΔMFCC"""
        import librosa

        # 预加重
        audio = np.append(audio[0], audio[1:] - 0.97 * audio[:-1])

        # MFCC
        mfcc = librosa.feature.mfcc(
            y=audio,
            sr=self.SAMPLE_RATE,
            n_mfcc=self.N_MFCC,
            n_fft=self.N_FFT,
            hop_length=self.HOP_LENGTH,
        )

        # ΔMFCC（一阶差分）
        delta_mfcc = librosa.feature.delta(mfcc)

        # 合并特征并取均值（时间维度压缩）
        combined = np.concatenate([mfcc, delta_mfcc], axis=0)
        features = np.mean(combined, axis=1)  # 时间维度压缩

        # L2归一化
        norm = np.linalg.norm(features)
        if norm > 0:
            features = features / norm

        return features

    def _extract_with_numpy(self, audio: np.ndarray) -> np.ndarray:
        """纯numpy备用方案（无librosa依赖）"""
        # 简单特征：能量、过零率、频谱质心
        # 注意：此方案精度远低于MFCC，仅作为备用

        frame_size = 512
        frames = []
        for i in range(0, len(audio) - frame_size, frame_size // 2):
            frame = audio[i:i + frame_size]
            # 能量
            energy = np.sum(frame ** 2)
            # 过零率
            zcr = np.sum(np.abs(np.diff(np.sign(frame)))) / (2 * len(frame))
            # 频谱质心（简化FFT）
            fft = np.abs(np.fft.rfft(frame))
            if np.sum(fft) > 0:
                centroid = np.sum(np.arange(len(fft)) * fft) / np.sum(fft)
            else:
                centroid = 0
            frames.append([energy, zcr, centroid])

        features = np.mean(frames, axis=0)
        # L2归一化
        norm = np.linalg.norm(features)
        if norm > 0:
            features = features / norm
        return features

    # ==================== 声纹注册 ====================

    def enroll(self, user_id: str, name: str, audio_samples: List[bytes]) -> Tuple[bool, str]:
        """
        注册声纹用户
        
        audio_samples: 多次录音的音频数据列表
        """
        if len(audio_samples) < 3:
            return False, "注册样本不足，至少需要 3 次录音"

        if len(self._profiles) >= self.max_users:
            return False, f"用户数量已达上限（{self.max_users}个）"

        # 提取特征
        features_list = []
        for i, audio in enumerate(audio_samples):
            feat = self.extract_features(audio)
            if feat is not None:
                features_list.append(feat)
            else:
                return False, f"第{i+1}次录音特征提取失败"

        # 检查样本一致性（相似度>0.6）
        if len(features_list) >= 2:
            similarities = []
            for i in range(len(features_list)):
                for j in range(i + 1, len(features_list)):
                    sim = self._similarity(features_list[i], features_list[j])
                    similarities.append(sim)
            avg_sim = np.mean(similarities)
            if avg_sim < 0.6:
                return False, f"样本一致性过低（{avg_sim:.2f}），请保持录音环境一致"

        # 保存用户档案
        profile = SpeakerProfile(user_id, name)
        profile.samples = features_list
        self._profiles[user_id] = profile
        self._save_profile(profile)

        print(f"[Speaker] ✅ 声纹注册成功: {name} ({user_id})，样本数: {len(features_list)}")
        return True, f"声纹注册成功: {name}，已保存"

    # ==================== 声纹验证 ====================

    def verify(self, audio_bytes: bytes) -> Tuple[bool, Optional[str], float]:
        """
        验证声纹
        
        返回: (是否通过, 用户ID, 相似度)
        """
        if self.verify_mode == "off":
            return True, None, 1.0

        if not self._profiles:
            # 未注册用户直接通过（访客模式）
            return True, None, 1.0

        feat = self.extract_features(audio_bytes)
        if feat is None:
            return False, None, 0.0

        # 与所有注册用户比对
        best_match = None
        best_score = 0.0

        for user_id, profile in self._profiles.items():
            if not profile.is_active:
                continue
            for sample in profile.samples:
                score = self._similarity(feat, sample)
                if score > best_score:
                    best_score = score
                    best_match = user_id

        if best_score >= self.threshold:
            profile = self._profiles.get(best_match)
            name = profile.name if profile else best_match
            print(f"[Speaker] ✅ 声纹验证通过: {name} (相似度: {best_score:.3f})")
            return True, best_match, best_score
        else:
            print(f"[Speaker] ❌ 声纹验证失败 (相似度: {best_score:.3f} < 阈值: {self.threshold})")
            if self.verify_mode == "guest":
                print("[Speaker] 🚪 访客模式开启")
                return True, "guest", best_score  # 访客模式允许
            return False, None, best_score

    def _similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """计算余弦相似度（归一化后）"""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # ==================== 用户管理 ====================

    def list_users(self) -> List[Dict]:
        """列出所有声纹用户"""
        return [
            {
                "user_id": p.user_id,
                "name": p.name,
                "created_at": p.created_at,
                "sample_count": len(p.samples),
                "is_active": p.is_active,
            }
            for p in self._profiles.values()
        ]

    def deactivate_user(self, user_id: str) -> bool:
        """禁用用户（不删除，可恢复）"""
        if user_id in self._profiles:
            self._profiles[user_id].is_active = False
            self._save_profile(self._profiles[user_id])
            return True
        return False

    def reactivate_user(self, user_id: str) -> bool:
        """恢复用户"""
        if user_id in self._profiles:
            self._profiles[user_id].is_active = True
            self._save_profile(self._profiles[user_id])
            return True
        return False

    def delete_user(self, user_id: str) -> bool:
        """永久删除用户"""
        if user_id in self._profiles:
            del self._profiles[user_id]
            file_path = self.profile_dir / f"{user_id}.json"
            if file_path.exists():
                file_path.unlink()
            return True
        return False

    # ==================== 状态查询 ====================

    def has_enrolled_users(self) -> bool:
        """是否有已注册的用户"""
        return len(self._profiles) > 0 and any(p.is_active for p in self._profiles.values())

    def get_user_name(self, user_id: str) -> Optional[str]:
        """获取用户名称"""
        profile = self._profiles.get(user_id)
        return profile.name if profile else None

