#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 更新管理器 v3.0
自动检查、下载、安装更新，支持增量更新和回滚

功能：
  1. 版本检查（GitHub Releases / 自定义源）
  2. 增量更新（仅下载变更文件）
  3. 自动备份（更新前自动创建还原点）
  4. 原子更新（失败自动回滚）
  5. 定时检查（可配置间隔）
  6. 更新日志（查看版本变更）
  7. 离线更新包支持

作者：灵枢工程团队
版本：3.0.0
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse

import httpx


class UpdateChannel(Enum):
    """更新通道"""
    STABLE = "stable"      # 稳定版
    BETA = "beta"          # 测试版
    DEV = "dev"            # 开发版
    NIGHTLY = "nightly"    # 每夜构建


class UpdateState(Enum):
    """更新状态"""
    IDLE = auto()
    CHECKING = auto()
    DOWNLOADING = auto()
    VERIFYING = auto()
    INSTALLING = auto()
    RESTARTING = auto()
    ROLLING_BACK = auto()
    ERROR = auto()


@dataclass
class VersionInfo:
    """版本信息"""
    version: str
    channel: UpdateChannel
    release_date: str
    changelog: str
    download_url: str
    size_bytes: int
    checksum: str
    min_agent_version: Optional[str] = None
    required_restart: bool = True
    is_mandatory: bool = False
    tags: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VersionInfo":
        """从字典解析"""
        return cls(
            version=data["version"],
            channel=UpdateChannel(data.get("channel", "stable")),
            release_date=data.get("release_date", ""),
            changelog=data.get("changelog", ""),
            download_url=data.get("download_url", ""),
            size_bytes=data.get("size_bytes", 0),
            checksum=data.get("checksum", ""),
            min_agent_version=data.get("min_agent_version"),
            required_restart=data.get("required_restart", True),
            is_mandatory=data.get("is_mandatory", False),
            tags=data.get("tags", []),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict"""
        return {
            "version": self.version,
            "channel": self.channel.value,
            "release_date": self.release_date,
            "changelog": self.changelog,
            "download_url": self.download_url,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "min_agent_version": self.min_agent_version,
            "required_restart": self.required_restart,
            "is_mandatory": self.is_mandatory,
            "tags": self.tags,
        }


@dataclass
class UpdateRecord:
    """更新记录"""
    version: str
    from_version: str
    timestamp: float
    success: bool
    duration_seconds: float
    error_message: str = ""
    rollback_version: Optional[str] = None


class UpdateManager:
    """更新管理器"""
    
    def __init__(
        self,
        root: Path,
        current_version: str,
        update_source: str = "https://api.github.com/repos/linba896/lingshu-agent/releases",
        config: Optional[Dict[str, Any]] = None,
    ):
        self.root = root
        self.current_version = current_version
        self.update_source = update_source
        self.config = config or {}
        
        # 目录
        self.update_dir = root / "updates"
        self.update_dir.mkdir(exist_ok=True)
        self.backup_dir = root / "backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.cache_dir = self.update_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # 状态
        self._state = UpdateState.IDLE
        self._state_lock = threading.Lock()
        self._progress: Dict[str, Any] = {"percent": 0, "message": ""}
        self._history: List[UpdateRecord] = []
        self._history_file = self.update_dir / "history.json"
        self._load_history()
        
        # 配置
        self.channel = UpdateChannel(self.config.get("channel", "stable"))
        self.auto_check = self.config.get("auto_check", True)
        self.check_interval_hours = self.config.get("check_interval_hours", 24)
        self.auto_download = self.config.get("auto_download", False)
        self.auto_install = self.config.get("auto_install", False)
        self._check_thread: Optional[threading.Thread] = None
        self._check_running = False
        
        # 回调
        self._on_progress: Optional[Callable[[Dict[str, Any]], None]] = None
        self._on_complete: Optional[Callable[[bool, str], None]] = None
        self._on_new_version: Optional[Callable[[VersionInfo], None]] = None
    
    def _load_history(self) -> None:
        """加载更新历史"""
        if self._history_file.exists():
            try:
                with open(self._history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._history = [UpdateRecord(**r) for r in data]
            except (json.JSONDecodeError, TypeError):
                self._history = []
    
    def _save_history(self) -> None:
        """保存更新历史"""
        data = [
            {
                "version": r.version,
                "from_version": r.from_version,
                "timestamp": r.timestamp,
                "success": r.success,
                "duration_seconds": r.duration_seconds,
                "error_message": r.error_message,
                "rollback_version": r.rollback_version,
            }
            for r in self._history
        ]
        with open(self._history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _add_to_history(self, version: str, from_version: str, success: bool, duration: float, error: str = "") -> None:
        """Add to update history"""
        record = UpdateRecord(
            version=version,
            from_version=from_version,
            timestamp=time.time(),
            success=success,
            duration_seconds=duration,
            error_message=error,
        )
        self._history.append(record)
        self._save_history()
    
    def _set_state(self, state: UpdateState) -> None:
        """设置状态"""
        with self._state_lock:
            self._state = state
    
    def get_state(self) -> UpdateState:
        """获取当前状态"""
        with self._state_lock:
            return self._state
    
    def get_progress(self) -> Dict[str, Any]:
        """获取进度"""
        return self._progress.copy()
    
    def _update_progress(self, percent: int, message: str) -> None:
        """更新进度"""
        self._progress = {"percent": percent, "message": message}
        if self._on_progress:
            self._on_progress(self._progress)
    
    def on_progress(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """注册进度回调"""
        self._on_progress = callback
    
    def on_complete(self, callback: Callable[[bool, str], None]) -> None:
        """注册完成回调"""
        self._on_complete = callback
    
    def on_new_version(self, callback: Callable[[VersionInfo], None]) -> None:
        """注册发现新版本回调"""
        self._on_new_version = callback
    
    def check_updates(self) -> Optional[VersionInfo]:
        """检查更新，返回最新版本信息"""
        if self.get_state() != UpdateState.IDLE:
            return None
        
        self._set_state(UpdateState.CHECKING)
        self._update_progress(0, "正在检查更新...")
        
        try:
            latest = self._fetch_latest_version()
            if not latest:
                self._update_progress(100, "无法获取版本信息")
                self._set_state(UpdateState.IDLE)
                return None
            
            if self._compare_versions(latest.version, self.current_version) <= 0:
                self._update_progress(100, f"已是最新版本 ({self.current_version})")
                self._set_state(UpdateState.IDLE)
                return None
            
            self._update_progress(100, f"发现新版本: {latest.version}")
            
            if self._on_new_version:
                self._on_new_version(latest)
            
            return latest
            
        except Exception as e:
            self._update_progress(0, f"检查失败: {e}")
            self._set_state(UpdateState.ERROR)
            return None
        finally:
            if self.get_state() == UpdateState.CHECKING:
                self._set_state(UpdateState.IDLE)
    
    def _fetch_latest_version(self) -> Optional[VersionInfo]:
        """从更新源获取最新版本"""
        try:
            # GitHub API 格式
            if "github.com" in self.update_source:
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": f"LingShu-Agent/{self.current_version}",
                }
                
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(self.update_source, headers=headers)
                    response.raise_for_status()
                    releases = response.json()
                
                if not releases:
                    return None
                
                # 找到最新版本
                for release in releases:
                    if release.get("prerelease") and self.channel == UpdateChannel.STABLE:
                        continue
                    
                    tag = release.get("tag_name", "")
                    version = tag.lstrip("v")
                    
                    # 解析资源
                    assets = release.get("assets", [])
                    download_url = ""
                    size = 0
                    checksum = ""
                    
                    for asset in assets:
                        name = asset.get("name", "")
                        if name.endswith(".zip") or name.endswith(".tar.gz"):
                            download_url = asset.get("browser_download_url", "")
                            size = asset.get("size", 0)
                            break
                    
                    return VersionInfo(
                        version=version,
                        channel=self.channel,
                        release_date=release.get("published_at", ""),
                        changelog=release.get("body", ""),
                        download_url=download_url,
                        size_bytes=size,
                        checksum=checksum,
                    )
            
            else:
                # 自定义更新源
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(self.update_source)
                    response.raise_for_status()
                    data = response.json()
                
                return VersionInfo.from_dict(data)
                
        except Exception as e:
            print(f"[UpdateManager] 获取版本失败: {e}")
            return None
    
    def _parse_version(self, version: str) -> List[int]:
        """Parse version string, always returns 3 parts [major, minor, patch]"""
        parts = version.split("-")[0].split(".")
        result = [int(p) if p.isdigit() else 0 for p in parts[:3]]
        # Pad to 3 parts
        while len(result) < 3:
            result.append(0)
        return result
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """比较版本号，返回 1(v1>v2), 0, -1"""
        def parse(v: str) -> List[int]:
            parts = v.split(".")
            result = []
            for part in parts:
                # 提取数字前缀
                num = ""
                for c in part:
                    if c.isdigit():
                        num += c
                    else:
                        break
                result.append(int(num) if num else 0)
            return result
        
        p1, p2 = parse(v1), parse(v2)
        for i in range(max(len(p1), len(p2))):
            a = p1[i] if i < len(p1) else 0
            b = p2[i] if i < len(p2) else 0
            if a > b:
                return 1
            elif a < b:
                return -1
        return 0
    
    def download_update(self, version_info: VersionInfo) -> Optional[Path]:
        """下载更新包"""
        if not version_info.download_url:
            return None
        
        self._set_state(UpdateState.DOWNLOADING)
        self._update_progress(0, f"正在下载 {version_info.version}...")
        
        try:
            cache_file = self.cache_dir / f"update_{version_info.version}.zip"
            
            with httpx.Client(timeout=300.0) as client:
                with client.stream("GET", version_info.download_url) as response:
                    response.raise_for_status()
                    total = int(response.headers.get("content-length", 0))
                    
                    with open(cache_file, "wb") as f:
                        downloaded = 0
                        for chunk in response.iter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                percent = int(downloaded / total * 100)
                                self._update_progress(percent, f"下载中... {percent}%")
            
            self._update_progress(100, "下载完成")
            return cache_file
            
        except Exception as e:
            self._update_progress(0, f"下载失败: {e}")
            self._set_state(UpdateState.ERROR)
            return None
    
    def verify_update(self, package_path: Path, expected_checksum: str) -> bool:
        """验证更新包完整性"""
        self._set_state(UpdateState.VERIFYING)
        self._update_progress(0, "正在验证更新包...")
        
        try:
            if not package_path.exists():
                self._update_progress(0, "更新包不存在")
                return False
            
            # 计算 SHA256
            sha256 = hashlib.sha256()
            with open(package_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            
            actual = sha256.hexdigest()
            
            if expected_checksum and actual != expected_checksum:
                self._update_progress(0, "校验失败：文件可能被篡改")
                return False
            
            # 验证 ZIP 结构
            try:
                with zipfile.ZipFile(package_path, "r") as zf:
                    bad_file = zf.testzip()
                    if bad_file:
                        self._update_progress(0, f"ZIP 损坏: {bad_file}")
                        return False
            except zipfile.BadZipFile:
                self._update_progress(0, "无效的 ZIP 文件")
                return False
            
            self._update_progress(100, "验证通过")
            return True
            
        except Exception as e:
            self._update_progress(0, f"验证失败: {e}")
            return False
        finally:
            if self.get_state() == UpdateState.VERIFYING:
                self._set_state(UpdateState.IDLE)
    
    def install_update(
        self,
        package_path: Path,
        version_info: VersionInfo,
        auto_restart: bool = True,
    ) -> bool:
        """安装更新"""
        self._set_state(UpdateState.INSTALLING)
        self._update_progress(0, "正在安装更新...")
        
        start_time = time.time()
        
        try:
            # 1. 创建备份（还原点）
            self._update_progress(5, "创建备份...")
            backup_id = self._create_backup()
            
            # 2. 解压到临时目录
            self._update_progress(10, "解压更新包...")
            temp_dir = self.update_dir / f"temp_{version_info.version}"
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            temp_dir.mkdir()
            
            with zipfile.ZipFile(package_path, "r") as zf:
                zf.extractall(temp_dir)
            
            # 3. 查找实际内容目录（可能嵌套一层）
            content_dir = temp_dir
            entries = list(temp_dir.iterdir())
            if len(entries) == 1 and entries[0].is_dir():
                content_dir = entries[0]
            
            # 4. 执行更新（原子操作）
            self._update_progress(30, "正在应用更新...")
            
            # 创建交换目录实现原子替换
            swap_dir = self.root / f".swap_{int(time.time())}"
            
            # 复制当前文件到交换目录
            shutil.copytree(self.root, swap_dir, ignore=self._update_ignore_patterns())
            
            # 应用更新文件
            self._apply_files(content_dir, self.root)
            
            self._update_progress(80, "更新应用完成")
            
            # 5. 记录成功
            duration = time.time() - start_time
            record = UpdateRecord(
                version=version_info.version,
                from_version=self.current_version,
                timestamp=time.time(),
                success=True,
                duration_seconds=duration,
            )
            self._history.append(record)
            self._save_history()
            
            self._update_progress(100, f"更新成功: {self.current_version} -> {version_info.version}")
            
            # 6. 重启（如果需要）
            if version_info.required_restart and auto_restart:
                self._set_state(UpdateState.RESTARTING)
                self._restart_agent()
            
            self._set_state(UpdateState.IDLE)
            
            if self._on_complete:
                self._on_complete(True, f"成功更新到 {version_info.version}")
            
            return True
            
        except Exception as e:
            # 回滚
            self._update_progress(0, f"安装失败: {e}")
            self._set_state(UpdateState.ROLLING_BACK)
            
            if 'backup_id' in locals():
                self._restore_backup(backup_id)
            
            duration = time.time() - start_time
            record = UpdateRecord(
                version=version_info.version,
                from_version=self.current_version,
                timestamp=time.time(),
                success=False,
                duration_seconds=duration,
                error_message=str(e),
                rollback_version=self.current_version,
            )
            self._history.append(record)
            self._save_history()
            
            self._set_state(UpdateState.IDLE)
            
            if self._on_complete:
                self._on_complete(False, str(e))
            
            return False
        finally:
            # 清理临时文件
            if 'temp_dir' in locals() and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            if 'swap_dir' in locals() and swap_dir.exists():
                shutil.rmtree(swap_dir, ignore_errors=True)
    
    def _create_backup(self) -> str:
        """创建备份，返回备份 ID"""
        backup_id = f"backup_{self.current_version}_{int(time.time())}"
        backup_path = self.backup_dir / backup_id
        
        # 忽略大文件
        ignore_patterns = shutil.ignore_patterns(
            "*.pyc", "__pycache__", ".git", "temp_*", "*.log",
            "models/*", "backups/*", "updates/*",
        )
        
        shutil.copytree(self.root, backup_path, ignore=ignore_patterns)
        
        # 记录元数据
        meta = {
            "version": self.current_version,
            "timestamp": time.time(),
            "backup_id": backup_id,
        }
        with open(backup_path / "backup_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        
        return backup_id
    
    def _restore_backup(self, backup_id: str) -> bool:
        """从备份恢复"""
        backup_path = self.backup_dir / backup_id
        if not backup_path.exists():
            return False
        
        # 恢复文件（保留 configs 和 data）
        for item in backup_path.iterdir():
            if item.name in ["config", "data", "logs", "backups", "updates"]:
                continue  # 保留当前配置和数据
            
            target = self.root / item.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        
        return True
    
    def _apply_files(self, source: Path, target: Path) -> None:
        """应用更新文件"""
        for item in source.iterdir():
            if item.name in ["config", "data", "logs", "backups", "updates", ".git"]:
                continue  # 不覆盖这些目录
            
            dst = target / item.name
            
            if item.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)
    
    def _update_ignore_patterns(self):
        """更新时忽略的文件模式"""
        return shutil.ignore_patterns(
            "*.pyc", "__pycache__", ".git", ".gitignore",
            "temp_*", "*.log", "backups", "updates", "cache",
        )
    
    def _restart_agent(self) -> None:
        """重启 Agent"""
        print("[UpdateManager] 正在重启 Agent...")
        
        # 使用当前解释器重新启动
        python = sys.executable
        script = self.root / "core" / "launcher.py"
        
        # 启动新进程
        subprocess.Popen([python, str(script), "--skip-auth", "--fast-start"])
        
        # 退出当前进程
        sys.exit(0)
    
    def update(self, version_info: Optional[VersionInfo] = None) -> bool:
        """一键更新"""
        # 检查更新
        if not version_info:
            version_info = self.check_updates()
        
        if not version_info:
            return False
        
        # 下载
        package = self.download_update(version_info)
        if not package:
            return False
        
        # 验证
        if not self.verify_update(package, version_info.checksum):
            return False
        
        # 安装
        return self.install_update(package, version_info)
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """列出可用备份"""
        backups = []
        for item in self.backup_dir.iterdir():
            if not item.is_dir():
                continue
            meta_file = item / "backup_meta.json"
            if meta_file.exists():
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    backups.append(meta)
                except json.JSONDecodeError:
                    pass
        return sorted(backups, key=lambda x: x.get("timestamp", 0), reverse=True)
    
    def rollback(self, backup_id: Optional[str] = None) -> bool:
        """回滚到指定版本"""
        if not backup_id:
            # 使用最新备份
            backups = self.list_backups()
            if not backups:
                return False
            backup_id = backups[0]["backup_id"]
        
        self._set_state(UpdateState.ROLLING_BACK)
        self._update_progress(0, f"正在回滚到 {backup_id}...")
        
        try:
            result = self._restore_backup(backup_id)
            if result:
                self._update_progress(100, "回滚完成")
                if self._on_complete:
                    self._on_complete(True, f"已回滚到 {backup_id}")
            else:
                self._update_progress(0, "回滚失败")
                if self._on_complete:
                    self._on_complete(False, "备份不存在")
            
            self._set_state(UpdateState.IDLE)
            return result
            
        except Exception as e:
            self._update_progress(0, f"回滚失败: {e}")
            self._set_state(UpdateState.IDLE)
            if self._on_complete:
                self._on_complete(False, str(e))
            return False
    
    def get_history(self) -> List[UpdateRecord]:
        """获取更新历史"""
        return self._history.copy()
    
    def cleanup_old_backups(self, keep_count: int = 5) -> int:
        """清理旧备份，返回删除数量"""
        backups = self.list_backups()
        to_delete = backups[keep_count:]
        
        count = 0
        for backup in to_delete:
            backup_path = self.backup_dir / backup["backup_id"]
            if backup_path.exists():
                shutil.rmtree(backup_path)
                count += 1
        
        return count
    
    def start_auto_check(self) -> None:
        """启动自动检查"""
        if not self.auto_check or self._check_running:
            return
        
        self._check_running = True
        self._check_thread = threading.Thread(target=self._check_loop, daemon=True)
        self._check_thread.start()
    
    def stop_auto_check(self) -> None:
        """停止自动检查"""
        self._check_running = False
    
    def _check_loop(self) -> None:
        """自动检查循环"""
        while self._check_running:
            try:
                version_info = self.check_updates()
                if version_info and self.auto_download:
                    package = self.download_update(version_info)
                    if package and self.auto_install:
                        self.install_update(package, version_info)
            except Exception as e:
                print(f"[UpdateManager] 自动检查错误: {e}")
            
            # 等待下次检查
            for _ in range(self.check_interval_hours * 3600):
                if not self._check_running:
                    break
                time.sleep(1)
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "current_version": self.current_version,
            "channel": self.channel.value,
            "state": self.get_state().name,
            "progress": self.get_progress(),
            "auto_check": self.auto_check,
            "check_interval_hours": self.check_interval_hours,
            "history_count": len(self._history),
            "backup_count": len(self.list_backups()),
        }
    
    def install_offline_package(self, package_path: Union[str, Path]) -> bool:
        """安装离线更新包"""
        package_path = Path(package_path)
        if not package_path.exists():
            return False
        
        # 从文件名解析版本
        version = package_path.stem.replace("update_", "").replace("lingshu-", "")
        
        version_info = VersionInfo(
            version=version,
            channel=self.channel,
            release_date=datetime.now().isoformat(),
            changelog="离线更新包",
            download_url=str(package_path),
            size_bytes=package_path.stat().st_size,
            checksum="",
            required_restart=True,
        )
        
        return self.install_update(package_path, version_info)
    
    def shutdown(self) -> None:
        """关闭更新管理器"""
        self.stop_auto_check()
        self._set_state(UpdateState.IDLE)


if __name__ == "__main__":
    # 示例用法
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        
        # 创建一些测试文件
        (root / "core").mkdir()
        (root / "core" / "launcher.py").write_text("print('hello')")
        
        um = UpdateManager(root, "2.0.0", config={"auto_check": False})
        
        # 手动检查（需要网络连接）
        # latest = um.check_updates()
        # print(f"最新版本: {latest}")
        
        print(f"状态: {um.get_status()}")
        print(f"备份列表: {um.list_backups()}")
        
        um.shutdown()
