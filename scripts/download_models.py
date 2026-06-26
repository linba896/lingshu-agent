#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 模型下载与量化脚本
功能：
  1. 从 Hugging Face / ModelScope 下载模型
  2. 执行 INT8/FP8/INT4 量化压缩
  3. 将模型放入 models/ 对应目录

支持的模型：
  - ASR: openai/whisper-tiny, openai/whisper-base
  - NLU: Qwen/Qwen2.5-1.5B-Instruct (+ LoRA)
  - VLM: Qwen/Qwen3-VL-8B-Instruct

用法：
  python scripts/download_models.py --model vlm --source huggingface
  python scripts/download_models.py --model asr --quantize int8
"""

import argparse
import sys
from pathlib import Path


# 模型注册表
MODEL_REGISTRY = {
    "asr": {
        "whisper-tiny": {
            "hf_repo": "openai/whisper-tiny",
            "ms_repo": "OpenAI/whisper-tiny",
            "size_gb": 0.075,
            "description": "轻量级语音识别，39M参数",
        },
        "whisper-base": {
            "hf_repo": "openai/whisper-base",
            "ms_repo": "OpenAI/whisper-base",
            "size_gb": 0.148,
            "description": "基础语音识别，74M参数",
        },
    },
    "nlu": {
        "qwen2.5-1.5b": {
            "hf_repo": "Qwen/Qwen2.5-1.5B-Instruct",
            "ms_repo": "qwen/Qwen2.5-1.5B-Instruct",
            "size_gb": 3.1,
            "description": "意图理解，1.5B参数",
        },
    },
    "vlm": {
        "qwen3-vl-8b": {
            "hf_repo": "Qwen/Qwen3-VL-8B-Instruct",
            "ms_repo": "qwen/Qwen3-VL-8B-Instruct",
            "size_gb": 16.0,  # 原始FP16，量化后更小
            "description": "视觉语言模型，8B参数，GUI操作核心",
        },
    },
}


def get_model_info(model_type: str, model_name: str) -> dict:
    """获取模型注册信息"""
    registry = MODEL_REGISTRY.get(model_type, {})
    return registry.get(model_name)


def list_models():
    """打印所有可用模型清单"""
    print("\n灵枢模型仓库\n" + "=" * 50)
    for model_type, models in MODEL_REGISTRY.items():
        print(f"\n[{model_type.upper()}]")
        for name, info in models.items():
            print(f"  {name:20s} {info['size_gb']:6.2f}GB  {info['description']}")
            print(f"  {'':20s}  HF: {info['hf_repo']}")
    print("\n" + "=" * 50)


def download_from_huggingface(repo_id: str, local_dir: Path, token: str = None):
    """从 Hugging Face 下载模型"""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[ERROR] 未安装 huggingface_hub。请先运行: pip install huggingface-hub")
        sys.exit(1)

    print(f"[DOWNLOAD] 从 Hugging Face 下载: {repo_id}")
    print(f"[DOWNLOAD] 目标目录: {local_dir}")
    local_dir.mkdir(parents=True, exist_ok=True)

    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            token=token,
        )
        print(f"[SUCCESS] 下载完成: {local_dir}")
    except Exception as e:
        print(f"[ERROR] 下载失败: {e}")
        print("[HINT] 如果网络受限，请尝试 --source modelscope 或使用代理")
        sys.exit(1)


def download_from_modelscope(repo_id: str, local_dir: Path):
    """从 ModelScope 下载模型（国内镜像）"""
    try:
        from modelscope import snapshot_download
    except ImportError:
        print("[ERROR] 未安装 modelscope。请先运行: pip install modelscope")
        sys.exit(1)

    print(f"[DOWNLOAD] 从 ModelScope 下载: {repo_id}")
    print(f"[DOWNLOAD] 目标目录: {local_dir}")
    local_dir.mkdir(parents=True, exist_ok=True)

    try:
        snapshot_download(repo_id, cache_dir=str(local_dir.parent))
        print(f"[SUCCESS] 下载完成: {local_dir}")
    except Exception as e:
        print(f"[ERROR] 下载失败: {e}")
        sys.exit(1)


def quantize_model(model_dir: Path, quantize_type: str, target_dir: Path):
    """
    模型量化压缩
    支持的量化类型: int8, fp8, int4, gguf
    """
    print(f"[QUANTIZE] 对 {model_dir} 执行 {quantize_type} 量化...")
    print(f"[QUANTIZE] 目标目录: {target_dir}")

    # 检查 llama.cpp 或 auto-gptq 等工具
    # 此处为桩实现，实际量化需根据模型类型选择工具

    if quantize_type == "gguf":
        print("[INFO] GGUF 量化需要 llama.cpp 的 convert.py / quantize 工具")
        print("[HINT] 参考: https://github.com/ggerganov/llama.cpp")
    elif quantize_type in ("int8", "int4"):
        print("[INFO] INT8/INT4 量化可使用 AutoGPTQ / AutoAWQ / llama.cpp")
        print("[HINT] 推荐工具: https://github.com/casper-hansen/AutoAWQ")
    elif quantize_type == "fp8":
        print("[INFO] FP8 量化需要支持 FP8 的推理框架（如 vLLM, TensorRT-LLM）")
        print("[HINT] 注意：FP8 需 NVIDIA Ampere/Ada 架构 GPU 支持")
    else:
        print(f"[WARN] 不支持的量化类型: {quantize_type}")
        return

    # 创建标记文件，表示量化任务待完成
    target_dir.mkdir(parents=True, exist_ok=True)
    marker = target_dir / f".quantize_{quantize_type}_pending"
    marker.write_text(
        f"量化任务: {model_dir} -> {target_dir}\n"
        f"类型: {quantize_type}\n"
        f"请使用对应工具完成量化后删除此标记文件。\n",
        encoding="utf-8"
    )
    print(f"[MARKER] 已创建量化标记: {marker}")
    print("[WARN] 量化压缩为手动步骤，请根据模型类型选择量化工具执行")


def main():
    parser = argparse.ArgumentParser(description="灵枢模型下载与量化工具")
    parser.add_argument("--model", type=str, choices=["asr", "nlu", "vlm"], help="模型类型")
    parser.add_argument("--name", type=str, help="模型名称（如 whisper-tiny, qwen3-vl-8b）")
    parser.add_argument("--source", type=str, choices=["huggingface", "modelscope"], default="huggingface", help="下载源")
    parser.add_argument("--quantize", type=str, choices=["int8", "fp8", "int4", "gguf"], help="量化类型")
    parser.add_argument("--root", type=str, default=None, help="灵枢根目录")
    parser.add_argument("--list", action="store_true", help="列出所有可用模型")
    parser.add_argument("--token", type=str, default=None, help="Hugging Face Token（如需下载 gated 模型）")
    args = parser.parse_args()

    if args.list:
        list_models()
        return

    if not args.model or not args.name:
        print("[ERROR] 请指定 --model 和 --name。使用 --list 查看可用模型。")
        sys.exit(1)

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    root = root.resolve()

    model_info = get_model_info(args.model, args.name)
    if not model_info:
        print(f"[ERROR] 未知模型: {args.model}/{args.name}")
        print("使用 --list 查看可用模型")
        sys.exit(1)

    local_dir = root / "models" / args.model / args.name

    print("=" * 60)
    print("  灵枢模型下载工具")
    print("=" * 60)
    print(f"  模型: {args.name} ({model_info['description']})")
    print(f"  大小: 约 {model_info['size_gb']} GB (原始)")
    print(f"  源:   {args.source}")
    print(f"  目标: {local_dir}")
    print("=" * 60 + "\n")

    # 下载
    if args.source == "huggingface":
        repo_id = model_info["hf_repo"]
        download_from_huggingface(repo_id, local_dir, token=args.token)
    else:
        repo_id = model_info["ms_repo"]
        download_from_modelscope(repo_id, local_dir)

    # 量化（可选）
    if args.quantize:
        quantize_dir = root / "models" / args.model / f"{args.name}-{args.quantize}"
        quantize_model(local_dir, args.quantize, quantize_dir)

    print("\n[SUCCESS] 模型处理完成！")
    print(f"[NEXT] 在配置中设置模型路径: models/{args.model}/{args.name}")


if __name__ == "__main__":
    main()
