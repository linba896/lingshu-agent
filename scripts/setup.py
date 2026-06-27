#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════
  灵枢 (LingShu) Agent — 离线依赖管理器
  功能：下载 / 安装 / 验证 Python 依赖包
═══════════════════════════════════════════════════════════════════════
"""

import sys
import os
import subprocess
import json
import time
import argparse
from pathlib import Path

# ─────────────────────────── rich 美化 ───────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
    from rich.table import Table
    from rich.rule import Rule
    from rich.align import Align
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def get_console():
    if RICH_AVAILABLE:
        return Console()
    class FakeConsole:
        def print(self, *args, **kwargs):
            print(*args)
        def rule(self, title=""):
            print(f"\n{'='*60} {title}")
    return FakeConsole()


console = get_console()

# ─────────────────────────── 配置 ───────────────────────────
WHEELS_DIR = Path("wheels")
PACKAGES_FILE = Path("packages.json")

# 依赖清单（按安装顺序分组）
DEPENDENCIES = {
    "core": ["pyyaml", "click", "rich", "loguru", "httpx", "psutil"],
    "vision": ["mss", "Pillow", "pytesseract"],
    "executor": ["pyautogui"],
    "hardware": ["pyserial", "pymodbus", "paho-mqtt"],
    "audio": ["sounddevice", "webrtcvad-wheels"],
    "science": ["numpy", "scipy", "scikit-learn", "joblib", "threadpoolctl", "narwhals"],
    "ml": ["torch", "transformers", "faster-whisper"],
    "memory": ["chromadb"],
    "gui": ["gradio"],
    "dev": ["pytest", "black"],
}

# PyTorch 使用 CPU 镜像加速下载
PYTORCH_INDEX = "https://download.pytorch.org/whl/cpu"


def print_banner():
    """赛博朋克风格启动 Banner"""
    if not RICH_AVAILABLE:
        print("""
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║    灵  枢    LINGSHU    AGENT    v0.3.0                               ║
║                                                                       ║
║    "灵枢在此，所唤何声？"                                            ║
║    Neural Agent  ·  Cybernetic Organism  ·  Active Learning           ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
""")
        return

    banner_text = """
[bold cyan]    ██╗     ██╗███╗   ██╗ ██████╗  ██████╗ ██╗  ██╗     ██╗   ██╗ █████╗  [/bold cyan]
[bold cyan]    ██║     ██║████╗  ██║██╔════╝ ██╔═══██╗██║  ██║     ██║   ██║██╔══██╗ [/bold cyan]
[bold blue]    ██║     ██║██╔██╗ ██║██║  ███╗██║   ██║███████║     ██║   ██║███████║ [/bold blue]
[bold blue]    ██║     ██║██║╚██╗██║██║   ██║██║   ██║██╔══██║     ╚██╗ ██╔╝██╔══██║ [/bold blue]
[bold magenta]    ███████╗██║██║ ╚████║╚██████╔╝╚██████╔╝██║  ██║      ╚████╔╝ ██║  ██║ [/bold magenta]
[bold magenta]    ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝       ╚═══╝  ╚═╝  ╚═╝ [/bold magenta]

[bold green]    ╔══════════════════════════════════════════════════════════════════╗[/bold green]
[bold green]    ║  [white]灵枢在此，所唤何声？[/white]  ·  Neural Agent  ·  v0.3.0               ║[/bold green]
[bold green]    ╚══════════════════════════════════════════════════════════════════╝[/bold green]
"""
    console.print(Panel(
        Align.center(Text.from_markup(banner_text)),
        title="[bold bright_cyan]☯ LINGSHU SETUP ☯[/bold bright_cyan]",
        subtitle="[dim]离线依赖管理器 | Offline Dependency Manager[/dim]",
        border_style="bright_cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    ))


def print_status_table(installed, failed, skipped):
    """打印安装状态表格"""
    if not RICH_AVAILABLE:
        print(f"\n安装成功: {len(installed)} | 失败: {len(failed)} | 跳过: {len(skipped)}")
        return

    table = Table(
        title="📦 依赖安装状态",
        box=box.ROUNDED,
        border_style="bright_blue",
        header_style="bold bright_white",
        show_lines=True,
    )
    table.add_column("状态", justify="center", width=10)
    table.add_column("包名", style="bold")
    table.add_column("版本", style="dim")
    table.add_column("耗时", justify="right")

    for pkg, ver, t in installed:
        table.add_row(f"[green]✅ 已安装[/green]", pkg, ver or "latest", f"{t:.1f}s")
    for pkg, err in failed:
        table.add_row(f"[red]❌ 失败[/red]", pkg, "[red]" + err[:30] + "[/red]", "—")
    for pkg, reason in skipped:
        table.add_row(f"[yellow]⏭️ 跳过[/yellow]", pkg, reason, "—")

    console.print(table)


def check_installed(pkg_name):
    """检查包是否已安装，返回版本号或 None"""
    try:
        import importlib.metadata
        return importlib.metadata.version(pkg_name)
    except Exception:
        return None


def download_packages(packages, wheels_dir, use_torch_index=False):
    """下载依赖到 wheels/ 目录"""
    wheels_dir = Path(wheels_dir)
    wheels_dir.mkdir(exist_ok=True)

    if not RICH_AVAILABLE:
        print(f"\n[下载] 开始下载 {len(packages)} 个包到 {wheels_dir} ...")
        for pkg in packages:
            cmd = [sys.executable, "-m", "pip", "download", pkg, "-d", str(wheels_dir)]
            if use_torch_index and pkg in ("torch", "torchvision", "torchaudio"):
                cmd.extend(["--index-url", PYTORCH_INDEX])
            print(f"  → {pkg}")
            subprocess.run(cmd, capture_output=True)
        print("[下载] 完成")
        return

    # rich 进度条版
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=30),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]下载依赖包...", total=len(packages))
        for pkg in packages:
            progress.update(task, description=f"[cyan]下载 {pkg}...")
            cmd = [sys.executable, "-m", "pip", "download", pkg, "-d", str(wheels_dir)]
            if use_torch_index and pkg in ("torch", "torchvision", "torchaudio"):
                cmd.extend(["--index-url", PYTORCH_INDEX])
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode != 0 and "already satisfied" not in result.stdout:
                progress.console.print(f"[yellow]⚠️ {pkg} 下载可能失败: {result.stderr[:100]}[/yellow]")
            progress.advance(task)


def install_packages(packages, wheels_dir=None, upgrade=False, use_torch_index=False):
    """安装依赖，支持离线 wheels 目录"""
    installed, failed, skipped = [], [], []
    wheels_dir = Path(wheels_dir) if wheels_dir else None

    for pkg in packages:
        # 检查是否已安装
        existing = check_installed(pkg)
        if existing and not upgrade:
            skipped.append((pkg, f"已安装 v{existing}"))
            continue

        cmd = [sys.executable, "-m", "pip", "install"]
        if upgrade:
            cmd.append("--upgrade")
        if wheels_dir and wheels_dir.exists() and any(wheels_dir.iterdir()):
            cmd.extend(["--no-index", "--find-links", str(wheels_dir)])
        cmd.append(pkg)

        if use_torch_index and pkg in ("torch", "torchvision", "torchaudio"):
            cmd.extend(["--index-url", PYTORCH_INDEX])

        start = time.time()
        if RICH_AVAILABLE:
            console.print(f"[cyan]▶[/cyan] 安装 [bold]{pkg}[/bold] ...", end=" ")
        else:
            print(f"▶ 安装 {pkg} ...", end=" ")

        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        elapsed = time.time() - start

        if result.returncode == 0 or "already satisfied" in result.stdout:
            ver = check_installed(pkg) or "已安装"
            installed.append((pkg, ver, elapsed))
            if RICH_AVAILABLE:
                console.print(f"[green]✅ {ver} ({elapsed:.1f}s)[/green]")
            else:
                print(f"✅ {ver} ({elapsed:.1f}s)")
        else:
            failed.append((pkg, result.stderr[:200]))
            if RICH_AVAILABLE:
                console.print(f"[red]❌ 失败 ({elapsed:.1f}s)[/red]")
            else:
                print(f"❌ 失败 ({elapsed:.1f}s)")

    return installed, failed, skipped


def save_manifest(packages, path):
    """保存已下载的包清单"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"packages": packages, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}, f, indent=2, ensure_ascii=False)


def load_manifest(path):
    """读取包清单"""
    if not Path(path).exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("packages", [])


def main():
    parser = argparse.ArgumentParser(
        description="灵枢 Agent 离线依赖管理器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/setup.py download              # 下载所有依赖到 wheels/
  python scripts/setup.py download --group ml   # 仅下载 ML 相关包
  python scripts/setup.py install               # 离线安装 wheels/ 中的包
  python scripts/setup.py install --online      # 在线安装（不依赖 wheels）
  python scripts/setup.py status                # 检查当前依赖状态
        """
    )
    parser.add_argument("action", choices=["download", "install", "status"], help="操作类型")
    parser.add_argument("--group", choices=list(DEPENDENCIES.keys()), help="仅操作指定分组")
    parser.add_argument("--upgrade", action="store_true", help="强制升级已安装包")
    parser.add_argument("--online", action="store_true", help="在线安装模式（不使用 wheels）")
    parser.add_argument("--wheels-dir", default="wheels", help="wheels 目录路径 (默认: wheels)")
    parser.add_argument("--no-banner", action="store_true", help="隐藏启动画面")
    args = parser.parse_args()

    if not args.no_banner:
        print_banner()

    # 确定目标包列表
    if args.group:
        target_packages = list(DEPENDENCIES[args.group])
        group_label = f"分组 [{args.group}]"
    else:
        target_packages = []
        for grp in DEPENDENCIES.values():
            target_packages.extend(grp)
        target_packages = list(dict.fromkeys(target_packages))  # 去重
        group_label = "全部依赖"

    wheels_dir = Path(args.wheels_dir)

    # ─────────────────────────── download ───────────────────────────
    if args.action == "download":
        console.print(Rule(f"[bold bright_cyan]📥 下载 {group_label} ({len(target_packages)} 个包)[/bold bright_cyan]", style="bright_cyan"))
        
        # 先下载常规包
        normal_pkgs = [p for p in target_packages if p not in ("torch", "torchvision", "torchaudio")]
        if normal_pkgs:
            download_packages(normal_pkgs, wheels_dir, use_torch_index=False)
        
        # torch 系列单独使用 CPU 镜像
        torch_pkgs = [p for p in target_packages if p in ("torch", "torchvision", "torchaudio")]
        if torch_pkgs:
            console.print(f"[yellow]⚡ 使用 PyTorch CPU 镜像下载: {', '.join(torch_pkgs)}[/yellow]")
            download_packages(torch_pkgs, wheels_dir, use_torch_index=True)
        
        save_manifest(target_packages, wheels_dir / "manifest.json")
        console.print(f"[green]\n✅ 下载完成！ wheels 目录: {wheels_dir.absolute()}[/green]")
        console.print(f"[dim]   共 {len(list(wheels_dir.glob('*.whl')))} 个 wheel 文件[/dim]")

    # ─────────────────────────── install ───────────────────────────
    elif args.action == "install":
        console.print(Rule(f"[bold bright_green]🔧 安装 {group_label} ({len(target_packages)} 个包)[/bold bright_green]", style="bright_green"))
        
        use_offline = (not args.online) and wheels_dir.exists() and any(wheels_dir.iterdir())
        if use_offline:
            console.print(f"[dim]📂 使用离线 wheels 目录: {wheels_dir.absolute()}[/dim]")
        else:
            console.print(f"[dim]🌐 使用在线安装模式[/dim]")
        
        # 安装顺序：先 core，再其他（torch 放最后，因为最大）
        ordered = []
        for key in ["core", "vision", "executor", "hardware", "audio", "science", "memory", "gui", "dev", "ml"]:
            if args.group and key != args.group:
                continue
            ordered.extend([p for p in DEPENDENCIES.get(key, []) if p in target_packages])
        ordered = list(dict.fromkeys(ordered))

        installed, failed, skipped = install_packages(
            ordered,
            wheels_dir if use_offline else None,
            upgrade=args.upgrade,
            use_torch_index=True
        )

        console.print("")
        print_status_table(installed, failed, skipped)

        total = len(installed) + len(failed) + len(skipped)
        if failed:
            console.print(f"\n[red bold]⚠️ {len(failed)}/{total} 个包安装失败，请检查网络或 wheels 完整性[/red bold]")
            sys.exit(1)
        else:
            console.print(f"\n[green bold]🎉 {len(installed)}/{total} 个包安装成功！灵枢 Agent 已就绪。[/green bold]")

    # ─────────────────────────── status ───────────────────────────
    elif args.action == "status":
        console.print(Rule(f"[bold bright_yellow]📋 依赖状态检查 ({len(target_packages)} 个包)[/bold bright_yellow]", style="bright_yellow"))
        
        table = Table(box=box.ROUNDED, border_style="bright_yellow", show_lines=True)
        table.add_column("分组", style="bold cyan")
        table.add_column("包名", style="bold")
        table.add_column("状态", justify="center")
        table.add_column("版本", style="dim")

        for group_name, pkgs in DEPENDENCIES.items():
            if args.group and group_name != args.group:
                continue
            for i, pkg in enumerate(pkgs):
                ver = check_installed(pkg)
                if ver:
                    status = "[green]✅ 已安装[/green]"
                    ver_str = ver
                else:
                    status = "[red]❌ 未安装[/red]"
                    ver_str = "—"
                grp = group_name if i == 0 else ""
                table.add_row(grp, pkg, status, ver_str)
        
        console.print(table)


if __name__ == "__main__":
    main()
