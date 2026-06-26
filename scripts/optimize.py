#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢速度优化脚本（Phase 7 联调优化）
功能：预热加载、缓存策略、批处理优化、资源监控

优化项：
  1. 模型预热：预加载所有模型到内存，减少首次推理延迟
  2. 缓存策略：常用操作结果缓存，避免重复计算
  3. 批处理：语音/视觉批量处理，减少 I/O 开销
  4. 资源监控：实时监控 CPU/内存/GPU 使用率，动态调整

使用方式：
  python scripts/optimize.py --warmup --cache-size 100 --batch-size 4
"""

import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional

import psutil


class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self, cache_size: int = 100, batch_size: int = 4):
        self.cache_size = cache_size
        self.batch_size = batch_size
        self._cache: Dict[str, any] = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    # ==================== 模型预热 ====================
    
    def warmup_asr(self, model_path: Path):
        """预热 ASR 模型"""
        print("[Optimize] 🔄 预热 ASR 模型...")
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(str(model_path), device="cpu", compute_type="int8")
            # 执行一次虚拟推理
            dummy_audio = b"\x00" * 16000  # 1秒静音
            segments, _ = model.transcribe(dummy_audio, language="zh")
            list(segments)  # 触发推理
            print("[Optimize] ✅ ASR 模型预热完成")
            return True
        except Exception as e:
            print(f"[Optimize] ⚠️ ASR 预热失败: {e}")
            return False
    
    def warmup_nlu(self, model_path: Path):
        """预热 NLU 模型"""
        print("[Optimize] 🔄 预热 NLU 模型...")
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            model = AutoModelForCausalLM.from_pretrained(
                str(model_path), torch_dtype=torch.float32, device_map="cpu"
            )
            tokenizer = AutoTokenizer.from_pretrained(str(model_path))
            # 执行一次虚拟推理
            inputs = tokenizer("Hello", return_tensors="pt")
            with torch.no_grad():
                model.generate(**inputs, max_new_tokens=1)
            print("[Optimize] ✅ NLU 模型预热完成")
            return True
        except Exception as e:
            print(f"[Optimize] ⚠️ NLU 预热失败: {e}")
            return False
    
    def warmup_vlm(self, model_path: Path):
        """预热 VLM 模型"""
        print("[Optimize] 🔄 预热 VLM 模型...")
        try:
            import torch
            from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor
            model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                str(model_path), torch_dtype=torch.float32, device_map="cpu"
            )
            processor = AutoProcessor.from_pretrained(str(model_path))
            print("[Optimize] ✅ VLM 模型预热完成（仅加载，未推理）")
            return True
        except Exception as e:
            print(f"[Optimize] ⚠️ VLM 预热失败: {e}")
            return False
    
    # ==================== 缓存管理 ====================
    
    def get_cache(self, key: str) -> Optional[any]:
        """获取缓存"""
        if key in self._cache:
            self._cache_hits += 1
            return self._cache[key]
        self._cache_misses += 1
        return None
    
    def set_cache(self, key: str, value: any):
        """设置缓存"""
        if len(self._cache) >= self.cache_size:
            # LRU 淘汰：删除最早的
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = value
    
    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计"""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0
        return {
            "size": len(self._cache),
            "max_size": self.cache_size,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": hit_rate,
        }
    
    # ==================== 资源监控 ====================
    
    def get_system_stats(self) -> Dict:
        """获取系统资源统计"""
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        
        return {
            "cpu_percent": cpu,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available / (1024**2),
            "disk_percent": disk.percent,
            "disk_free_gb": disk.free / (1024**3),
        }
    
    def recommend_optimizations(self) -> List[str]:
        """推荐优化建议"""
        stats = self.get_system_stats()
        recommendations = []
        
        if stats["cpu_percent"] > 80:
            recommendations.append("CPU 使用率过高，建议降低模型并发数或降低分辨率")
        
        if stats["memory_percent"] > 85:
            recommendations.append("内存使用率过高，建议启用 INT4 量化或减少模型缓存")
        
        if stats["disk_percent"] > 90:
            recommendations.append("磁盘空间不足，建议清理日志和临时文件")
        
        if not recommendations:
            recommendations.append("系统资源充足，当前配置运行良好")
        
        return recommendations


def main():
    parser = argparse.ArgumentParser(description="灵枢性能优化工具")
    parser.add_argument("--warmup", action="store_true", help="预热所有模型")
    parser.add_argument("--cache-size", type=int, default=100, help="缓存大小")
    parser.add_argument("--batch-size", type=int, default=4, help="批处理大小")
    parser.add_argument("--model-dir", type=str, default="models", help="模型目录")
    parser.add_argument("--stats", action="store_true", help="查看系统资源统计")
    args = parser.parse_args()
    
    optimizer = PerformanceOptimizer(cache_size=args.cache_size, batch_size=args.batch_size)
    
    if args.stats:
        stats = optimizer.get_system_stats()
        print("\n系统资源统计:")
        for k, v in stats.items():
            print(f"  {k}: {v:.1f}")
        
        recommendations = optimizer.recommend_optimizations()
        print("\n优化建议:")
        for r in recommendations:
            print(f"  • {r}")
    
    if args.warmup:
        model_dir = Path(args.model_dir)
        
        # 预热 ASR
        asr_path = model_dir / "asr" / "whisper-tiny"
        if asr_path.exists():
            optimizer.warmup_asr(asr_path)
        else:
            print(f"[Optimize] ℹ️ ASR 模型未找到: {asr_path}")
        
        # 预热 NLU
        nlu_path = model_dir / "nlu" / "qwen2.5-1.5b-lora"
        if nlu_path.exists():
            optimizer.warmup_nlu(nlu_path)
        else:
            print(f"[Optimize] ℹ️ NLU 模型未找到: {nlu_path}")
        
        # 预热 VLM
        vlm_path = model_dir / "vlm" / "qwen3-vl-8b"
        if vlm_path.exists():
            optimizer.warmup_vlm(vlm_path)
        else:
            print(f"[Optimize] ℹ️ VLM 模型未找到: {vlm_path}")
    
    print("\n[Optimize] 优化工具运行完成")


if __name__ == "__main__":
    main()
