#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 便携环境构建脚本
功能：
  1. 下载 Python 嵌入式版本（Windows）/ pyenv（Unix）到本地
  2. 创建虚拟环境到项目目录
  3. 下载所有依赖的离线 wheels 包
  4. 生成安装脚本（供无网络目标机器使用）

用法：
  python scripts/build_portable_env.py --python-version 3.11
"""

import argparse
import subprocess
import sys
import os
import shutil
from pathlib import Path


def run(cmd: list, cwd=None, check=True) -> str:
    """执行命令并返回输出"""
    print(f"[EXEC] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)
    if result.stdout:
        print(result.stdout)
    if result.stderr and check:
        print(result.stderr, file=sys.stderr)
    return result.stdout


def download_embedded_python_windows(version: str, root: Path) -> Path:
    """
    Windows: 下载 python-embedded zip 并解压到 python/ 目录
    参考 https://docs.python.org/3/using/windows.html#the-embeddable-package
    """
    import urllib.request
    import zipfile

    py_dir = root / "python"
    if py_dir.exists():
        print(f"[INFO] Python 目录已存在: {py_dir}，跳过下载")
        return py_dir

    # 构造下载链接（如 python-3.11.9-embed-amd64.zip）
    # 这里使用简化的版本匹配，实际使用时应从 python.org 获取精确版本号
    major_minor = ".".join(version.split(".")[:2])
    # 尝试常见版本号映射（简化处理）
    patch_versions = {
        "3.10": "3.10.11",
        "3.11": "3.11.9",
        "3.12": "3.12.4",
    }
    full_ver = patch_versions.get(major_minor, version)
    arch = "amd64"  # 假设64位
    filename = f"python-{full_ver}-embed-{arch}.zip"
    url = f"https://www.python.org/ftp/python/{full_ver}/{filename}"

    download_dir = root / "downloads"
    download_dir.mkdir(parents=True, exist_ok=True)
    zip_path = download_dir / filename

    if not zip_path.exists():
        print(f"[DOWNLOAD] 正在下载 {url} ...")
        try:
            urllib.request.urlretrieve(url, zip_path)
            print(f"[DOWNLOAD] 完成: {zip_path}")
        except Exception as e:
            print(f"[ERROR] 下载失败: {e}")
            print(f"[HINT] 请手动下载 {url} 并解压到 {py_dir}")
            return py_dir
    else:
        print(f"[INFO] 已存在下载包: {zip_path}")

    # 解压
    print(f"[EXTRACT] 解压到 {py_dir} ...")
    py_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(py_dir)

    # 修改 python311._pth 文件（取消注释 import site）以启用 pip
    pth_files = list(py_dir.glob("python*._pth"))
    if pth_files:
        pth_file = pth_files[0]
        content = pth_file.read_text(encoding="utf-8")
        content = content.replace("#import site", "import site")
        pth_file.write_text(content, encoding="utf-8")
        print(f"[INFO] 已启用 site-packages: {pth_file}")

    # 下载 get-pip.py
    pip_script = download_dir / "get-pip.py"
    if not pip_script.exists():
        print("[DOWNLOAD] 下载 get-pip.py ...")
        urllib.request.urlretrieve("https://bootstrap.pypa.io/get-pip.py", pip_script)

    # 安装 pip
    python_exe = py_dir / "python.exe"
    print("[INSTALL] 安装 pip ...")
    run([str(python_exe), str(pip_script), "--no-warn-script-location"])

    return py_dir


def create_venv_unix(version: str, root: Path) -> Path:
    """
    Linux/macOS: 使用系统 python 创建虚拟环境到 venv/ 目录
    注：Unix 上便携 Python 更复杂，建议用户预先安装 python3
    """
    venv_dir = root / "venv"
    if venv_dir.exists():
        print(f"[INFO] 虚拟环境已存在: {venv_dir}")
        return venv_dir

    python_cmd = f"python{version.split('.')[0]}.{version.split('.')[1]}"
    # 尝试查找可用的 python
    for cmd in [python_cmd, "python3", "python"]:
        if shutil.which(cmd):
            python_cmd = cmd
            break
    else:
        print(f"[ERROR] 未找到 Python {version}，请先安装")
        sys.exit(1)

    print(f"[VENV] 使用 {python_cmd} 创建虚拟环境...")
    run([python_cmd, "-m", "venv", str(venv_dir)])
    return venv_dir


def download_wheels(root: Path, requirements: Path):
    """下载所有依赖的离线 wheels 包到 wheels/ 目录"""
    wheels_dir = root / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)

    if not requirements.exists():
        print(f"[ERROR] 依赖文件不存在: {requirements}")
        return

    print(f"[WHEELS] 下载离线依赖包到 {wheels_dir} ...")

    # 检测可用的 pip
    python_exe = None
    if sys.platform == "win32":
        py_exe = root / "python" / "python.exe"
        if py_exe.exists():
            python_exe = str(py_exe)
    else:
        venv_py = root / "venv" / "bin" / "python"
        if venv_py.exists():
            python_exe = str(venv_py)

    if not python_exe:
        python_exe = sys.executable

    try:
        run([
            python_exe, "-m", "pip", "download",
            "-r", str(requirements),
            "-d", str(wheels_dir),
            "--prefer-binary",
        ])
        print(f"[WHEELS] 下载完成，共 {len(list(wheels_dir.glob('*')))} 个包")
    except subprocess.CalledProcessError as e:
        print(f"[WARN] pip download 部分失败: {e}")
        print(f"[HINT] 某些包（如 torch）体积巨大，建议手动下载并放入 {wheels_dir}")


def install_from_wheels(root: Path, requirements: Path):
    """从本地 wheels 目录安装依赖（在无网络的目标机器使用）"""
    wheels_dir = root / "wheels"
    if not wheels_dir.exists() or not any(wheels_dir.iterdir()):
        print(f"[ERROR] 本地 wheels 目录为空: {wheels_dir}")
        print("[HINT] 先在有网络的环境中运行: python build_portable_env.py --download")
        return

    python_exe = sys.executable
    if sys.platform == "win32":
        py_exe = root / "python" / "python.exe"
        if py_exe.exists():
            python_exe = str(py_exe)
    else:
        venv_py = root / "venv" / "bin" / "python"
        if venv_py.exists():
            python_exe = str(venv_py)

    print(f"[INSTALL] 从本地 wheels 安装依赖...")
    run([
        python_exe, "-m", "pip", "install",
        "--no-index",
        "--find-links", str(wheels_dir),
        "-r", str(requirements),
    ])


def main():
    parser = argparse.ArgumentParser(description="构建灵枢便携Python环境")
    parser.add_argument("--root", type=str, default=None, help="灵枢根目录")
    parser.add_argument("--python-version", type=str, default="3.11", help="Python版本（如 3.11）")
    parser.add_argument("--download", action="store_true", help="仅下载 wheels 包（离线模式）")
    parser.add_argument("--install", action="store_true", help="仅从本地 wheels 安装（目标机器）")
    args = parser.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    root = root.resolve()
    requirements = root / "requirements.txt"

    print("=" * 60)
    print("  灵枢便携环境构建工具")
    print("=" * 60)
    print(f"  根目录: {root}")
    print(f"  Python版本: {args.python_version}")
    print(f"  平台: {sys.platform}")
    print("=" * 60 + "\n")

    if args.install:
        install_from_wheels(root, requirements)
        return

    # 步骤1: 获取 Python 环境
    if sys.platform == "win32":
        download_embedded_python_windows(args.python_version, root)
    else:
        create_venv_unix(args.python_version, root)

    # 步骤2: 下载离线 wheels
    if args.download:
        download_wheels(root, requirements)
        print("\n[SUCCESS] 离线包已下载到 wheels/ 目录，可复制到U盘在目标机器安装")
    else:
        # 直接安装（有网络环境）
        python_exe = sys.executable
        if sys.platform == "win32":
            py_exe = root / "python" / "python.exe"
            if py_exe.exists():
                python_exe = str(py_exe)
        else:
            venv_py = root / "venv" / "bin" / "python"
            if venv_py.exists():
                python_exe = str(venv_py)

        print(f"[INSTALL] 直接安装依赖...")
        run([python_exe, "-m", "pip", "install", "-r", str(requirements)])

    print("\n[SUCCESS] 环境构建完成！")
    print(f"[NEXT] 运行启动器: {'start.bat' if sys.platform == 'win32' else './start.sh'}")


if __name__ == "__main__":
    main()
