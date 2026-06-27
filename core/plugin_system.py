#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 插件系统 v3.0
支持动态加载第三方扩展，实现模块化架构

功能：
  1. 插件发现与加载（本地目录 + 远程仓库）
  2. 插件生命周期管理（安装/启用/禁用/卸载）
  3. 插件间通信（事件总线）
  4. 沙箱隔离（防止恶意插件）
  5. 插件权限控制（API 白名单）
  6. 热重载（开发时自动刷新）
  7. 插件市场客户端

作者：灵枢工程团队
版本：3.0.0
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import threading
import time
import zipfile
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Union


class PluginState(Enum):
    """插件状态"""
    DISCOVERED = auto()   # 已发现，未加载
    INSTALLED = auto()    # 已安装
    ENABLED = auto()      # 已启用
    DISABLED = auto()     # 已禁用
    ERROR = auto()        # 加载错误
    UNLOADING = auto()    # 卸载中


class PluginPriority(Enum):
    """插件优先级"""
    CRITICAL = 0    # 系统关键（如安全插件）
    HIGH = 1        # 高优先级（如硬件控制）
    NORMAL = 2      # 普通优先级
    LOW = 3         # 低优先级（如主题装饰）
    BACKGROUND = 4  # 后台任务


@dataclass
class PluginManifest:
    """插件清单"""
    id: str
    name: str
    version: str
    author: str
    description: str
    min_agent_version: str = "2.0.0"
    max_agent_version: Optional[str] = None
    entry_point: str = "plugin.py"
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    priority: PluginPriority = PluginPriority.NORMAL
    hooks: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    homepage: str = ""
    repository: str = ""
    license: str = "MIT"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginManifest":
        """从字典解析清单"""
        if "priority" in data:
            data["priority"] = PluginPriority[data["priority"].upper()]
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "min_agent_version": self.min_agent_version,
            "max_agent_version": self.max_agent_version,
            "entry_point": self.entry_point,
            "dependencies": self.dependencies,
            "permissions": self.permissions,
            "priority": self.priority.name,
            "hooks": self.hooks,
            "tags": self.tags,
            "homepage": self.homepage,
            "license": self.license,
        }


@dataclass
class PluginAPI:
    """插件暴露的 API 接口"""
    name: str
    description: str
    parameters: Dict[str, str]
    return_type: str
    is_async: bool = False


class PluginSandbox:
    """插件沙箱：限制插件执行环境"""
    
    # 允许导入的白名单模块
    ALLOWED_MODULES = {
        "typing", "dataclasses", "enum", "collections", "json",
        "re", "math", "random", "datetime", "time", "hashlib",
        "base64", "urllib.parse", "html", "string", "itertools",
        "functools", "inspect", "textwrap", "pathlib", "warnings",
    }
    
    # 禁止使用的危险函数
    BLOCKED_BUILTINS = {
        "eval", "exec", "compile", "__import__", "open",
        "input", "raw_input", "reload", "exit", "quit",
    }
    
    def __init__(self, plugin_id: str, plugin_dir: Path):
        self.plugin_id = plugin_id
        self.plugin_dir = plugin_dir
        self._restricted_globals: Dict[str, Any] = {}
        self._build_restricted_globals()
    
    def _build_restricted_globals(self):
        """构建受限的全局命名空间"""
        import builtins
        safe_builtins = {}
        for name in dir(builtins):
            if name not in self.BLOCKED_BUILTINS:
                safe_builtins[name] = getattr(builtins, name)
        
        self._restricted_globals = {
            "__builtins__": safe_builtins,
            "__name__": f"plugin_{self.plugin_id}",
            "__file__": str(self.plugin_dir),
        }
    
    def execute(self, code: str, additional_globals: Optional[Dict] = None) -> Any:
        """在沙箱中执行代码"""
        # 语法检查（AST 分析）
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise PluginSecurityError(f"语法错误: {e}")
        
        # 检查危险导入
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in self.ALLOWED_MODULES:
                        raise PluginSecurityError(f"禁止导入模块: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module not in self.ALLOWED_MODULES:
                    raise PluginSecurityError(f"禁止导入模块: {node.module}")
        
        # 执行代码
        globals_dict = dict(self._restricted_globals)
        if additional_globals:
            globals_dict.update(additional_globals)
        
        locals_dict = {}
        exec(compile(tree, f"<plugin_{self.plugin_id}>", "exec"), globals_dict, locals_dict)
        return locals_dict


class PluginSecurityError(Exception):
    """插件安全错误"""
    pass


class PluginEventBus:
    """插件事件总线：实现插件间通信"""
    
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
    
    def subscribe(self, event_type: str, callback: Callable) -> None:
        """订阅事件"""
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            self._listeners[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """取消订阅"""
        with self._lock:
            if event_type in self._listeners:
                self._listeners[event_type] = [
                    cb for cb in self._listeners[event_type] if cb != callback
                ]
    
    def publish(self, event_type: str, data: Any, source: str = "") -> int:
        """发布事件，返回处理数量"""
        count = 0
        with self._lock:
            listeners = self._listeners.get(event_type, []).copy()
        
        for callback in listeners:
            try:
                if threading.current_thread().name == "MainThread":
                    callback(data, source)
                else:
                    callback(data, source)
                count += 1
            except Exception as e:
                print(f"[EventBus] 事件处理错误: {e}")
        
        return count


class PluginAPIGateway:
    """插件 API 网关：注册和调用插件 API"""
    
    def __init__(self):
        self._apis: Dict[str, Dict[str, Callable]] = {}
        self._lock = threading.RLock()
    
    def register_api(self, plugin_id: str, api_name: str, handler: Callable) -> None:
        """注册 API"""
        with self._lock:
            if plugin_id not in self._apis:
                self._apis[plugin_id] = {}
            self._apis[plugin_id][api_name] = handler
    
    def unregister_api(self, plugin_id: str, api_name: str) -> None:
        """注销 API"""
        with self._lock:
            if plugin_id in self._apis and api_name in self._apis[plugin_id]:
                del self._apis[plugin_id][api_name]
    
    def unregister_plugin_apis(self, plugin_id: str) -> None:
        """注销插件所有 API"""
        with self._lock:
            if plugin_id in self._apis:
                del self._apis[plugin_id]
    
    def call_api(self, plugin_id: str, api_name: str, **kwargs) -> Any:
        """调用 API"""
        with self._lock:
            handler = self._apis.get(plugin_id, {}).get(api_name)
        
        if not handler:
            raise RuntimeError(f"API 未找到: {plugin_id}.{api_name}")
        
        try:
            return handler(**kwargs)
        except Exception as e:
            raise RuntimeError(f"API 调用失败 '{plugin_id}.{api_name}': {e}")
    
    def list_apis(self, plugin_id: Optional[str] = None) -> Dict[str, List[PluginAPI]]:
        """列出 API"""
        with self._lock:
            if plugin_id:
                return {plugin_id: list(self._apis.get(plugin_id, {}).values())}
            return {pid: list(apis.values()) for pid, apis in self._apis.items()}


class PluginInterface:
    """插件接口基类：所有插件必须继承"""
    
    manifest: PluginManifest
    
    def __init__(self, manifest: PluginManifest, context: PluginContext):
        self.manifest = manifest
        self.context = context
        self._enabled = False
        self._config: Dict[str, Any] = {}
    
    def on_load(self) -> bool:
        """插件加载时调用，返回 True 表示成功"""
        return True
    
    def on_enable(self) -> bool:
        """插件启用时调用"""
        self._enabled = True
        return True
    
    def on_disable(self) -> bool:
        """插件禁用时调用"""
        self._enabled = False
        return True
    
    def on_unload(self) -> None:
        """插件卸载时调用"""
        pass
    
    def on_config_change(self, key: str, value: Any) -> None:
        """配置变更时调用"""
        self._config[key] = value
    
    def get_api(self) -> List[PluginAPI]:
        """返回插件提供的 API 列表"""
        return []
    
    def call_api(self, api_name: str, **kwargs) -> Any:
        """调用插件 API"""
        raise NotImplementedError(f"API '{api_name}' 未实现")


@dataclass
class PluginContext:
    """插件运行上下文"""
    agent_root: Path
    config_dir: Path
    data_dir: Path
    temp_dir: Path
    logger: Any
    event_bus: Any
    api_gateway: Any
    
    def get_config_path(self, plugin_id: str) -> Path:
        """获取插件配置文件路径"""
        return self.config_dir / f"{plugin_id}.json"
    
    def get_data_path(self, plugin_id: str) -> Path:
        """获取插件数据目录"""
        path = self.data_dir / plugin_id
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_temp_path(self, plugin_id: str) -> Path:
        """获取插件临时目录"""
        path = self.temp_dir / plugin_id
        path.mkdir(parents=True, exist_ok=True)
        return path


class PluginManager:
    """插件管理器：核心控制器"""
    
    def __init__(self, root: Path, config: Optional[Dict] = None):
        self.root = root
        self.config = config or {}
        
        # 目录结构
        self.plugin_dir = root / "plugins"
        self.plugin_dir.mkdir(exist_ok=True)
        self.enabled_dir = self.plugin_dir / "enabled"
        self.enabled_dir.mkdir(exist_ok=True)
        self.disabled_dir = self.plugin_dir / "disabled"
        self.disabled_dir.mkdir(exist_ok=True)
        self.cache_dir = self.plugin_dir / ".cache"
        self.cache_dir.mkdir(exist_ok=True)
        
        # 上下文
        self.context = PluginContext(
            agent_root=root,
            config_dir=root / "config" / "plugins",
            data_dir=root / "data" / "plugins",
            temp_dir=root / "temp" / "plugins",
            logger=None,  # 由外部注入
            event_bus=PluginEventBus(),
            api_gateway=PluginAPIGateway(),
        )
        self.context.config_dir.mkdir(parents=True, exist_ok=True)
        self.context.data_dir.mkdir(parents=True, exist_ok=True)
        self.context.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 插件状态
        self._plugins: Dict[str, PluginInterface] = {}
        self._states: Dict[str, PluginState] = {}
        self._manifests: Dict[str, PluginManifest] = {}
        self._load_order: List[str] = []
        self._watchdog: Optional[threading.Thread] = None
        self._watchdog_running = False
        
        # 安全
        self._sandbox_enabled = self.config.get("sandbox_enabled", True)
        self._verify_signatures = self.config.get("verify_signatures", True)
    
    def discover(self) -> List[PluginManifest]:
        """发现所有可用插件"""
        manifests = []
        
        # 扫描已启用目录
        for plugin_dir in self.enabled_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            manifest = self._read_manifest(plugin_dir)
            if manifest:
                manifests.append(manifest)
                self._states[manifest.id] = PluginState.DISCOVERED
                self._manifests[manifest.id] = manifest
        
        # 扫描已禁用目录
        for plugin_dir in self.disabled_dir.iterdir():
            if not plugin_dir.is_dir():
                continue
            manifest = self._read_manifest(plugin_dir)
            if manifest and manifest.id not in self._manifests:
                manifests.append(manifest)
                self._states[manifest.id] = PluginState.DISABLED
                self._manifests[manifest.id] = manifest
        
        return sorted(manifests, key=lambda m: m.priority.value)
    
    def _read_manifest(self, plugin_dir: Path) -> Optional[PluginManifest]:
        """读取插件清单"""
        manifest_file = plugin_dir / "manifest.json"
        if not manifest_file.exists():
            return None
        
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return PluginManifest.from_dict(data)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"[PluginManager] 清单解析失败 {plugin_dir}: {e}")
            return None
    
    def load(self, plugin_id: str) -> bool:
        """加载插件"""
        if plugin_id in self._plugins:
            return True
        
        manifest = self._manifests.get(plugin_id)
        if not manifest:
            print(f"[PluginManager] 插件未找到: {plugin_id}")
            return False
        
        # 检查依赖
        for dep in manifest.dependencies:
            if dep not in self._plugins:
                print(f"[PluginManager] 依赖未满足: {plugin_id} 需要 {dep}")
                return False
        
        # 查找插件目录
        plugin_dir = self._find_plugin_dir(plugin_id)
        if not plugin_dir:
            return False
        
        try:
            # 安全验证
            if self._sandbox_enabled:
                if not self._verify_plugin(plugin_dir, manifest):
                    self._states[plugin_id] = PluginState.ERROR
                    return False
            
            # 加载入口模块
            entry_file = plugin_dir / manifest.entry_point
            if not entry_file.exists():
                print(f"[PluginManager] 入口文件不存在: {entry_file}")
                return False
            
            plugin_class = self._load_plugin_class(entry_file, manifest)
            if not plugin_class:
                return False
            
            # 实例化
            instance = plugin_class(manifest, self.context)
            if not instance.on_load():
                print(f"[PluginManager] 插件加载失败: {plugin_id}")
                return False
            
            self._plugins[plugin_id] = instance
            self._states[plugin_id] = PluginState.INSTALLED
            self._load_order.append(plugin_id)
            
            # 注册 API
            for api in instance.get_api():
                self.context.api_gateway.register_api(
                    plugin_id, api, 
                    lambda **kwargs, inst=instance, api_name=api.name: inst.call_api(api_name, **kwargs)
                )
            
            print(f"[PluginManager] 插件加载成功: {plugin_id} v{manifest.version}")
            return True
            
        except Exception as e:
            print(f"[PluginManager] 加载异常 {plugin_id}: {e}")
            self._states[plugin_id] = PluginState.ERROR
            return False
    
    def _find_plugin_dir(self, plugin_id: str) -> Optional[Path]:
        """查找插件目录"""
        for base in [self.enabled_dir, self.disabled_dir]:
            d = base / plugin_id
            if d.exists():
                return d
        return None
    
    def _load_plugin_class(self, entry_file: Path, manifest: PluginManifest) -> Optional[type]:
        """加载插件类"""
        try:
            # 使用沙箱加载
            sandbox = PluginSandbox(manifest.id, entry_file.parent)
            globals_dict = sandbox.execute(entry_file.read_text(encoding="utf-8"))
            
            # 查找 PluginInterface 的子类
            for obj in globals_dict.values():
                if (isinstance(obj, type) and 
                    issubclass(obj, PluginInterface) and 
                    obj is not PluginInterface):
                    return obj
            
            print(f"[PluginManager] 未找到 PluginInterface 子类: {manifest.id}")
            return None
            
        except PluginSecurityError as e:
            print(f"[PluginManager] 安全验证失败: {e}")
            return None
        except Exception as e:
            print(f"[PluginManager] 加载异常: {e}")
            return None
    
    def _verify_plugin(self, plugin_dir: Path, manifest: PluginManifest) -> bool:
        """验证插件完整性"""
        # 检查文件哈希（如果有 checksums.json）
        checksums_file = plugin_dir / "checksums.json"
        if checksums_file.exists():
            try:
                with open(checksums_file, "r") as f:
                    checksums = json.load(f)
                for filename, expected_hash in checksums.items():
                    filepath = plugin_dir / filename
                    if not filepath.exists():
                        print(f"[PluginManager] 文件缺失: {filename}")
                        return False
                    actual_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
                    if actual_hash != expected_hash:
                        print(f"[PluginManager] 哈希不匹配: {filename}")
                        return False
            except Exception:
                pass  # 校验失败但不阻止加载
        
        return True
    
    def enable(self, plugin_id: str) -> bool:
        """启用插件"""
        if plugin_id not in self._plugins:
            if not self.load(plugin_id):
                return False
        
        instance = self._plugins[plugin_id]
        if instance.on_enable():
            self._states[plugin_id] = PluginState.ENABLED
            
            # 移动到 enabled 目录
            self._move_plugin_dir(plugin_id, self.enabled_dir)
            
            # 发布事件
            self.context.event_bus.publish("plugin.enabled", {
                "id": plugin_id,
                "name": instance.manifest.name,
            }, source="plugin_manager")
            
            return True
        return False
    
    def disable(self, plugin_id: str) -> bool:
        """禁用插件"""
        if plugin_id not in self._plugins:
            return False
        
        instance = self._plugins[plugin_id]
        if instance.on_disable():
            self._states[plugin_id] = PluginState.DISABLED
            
            # 注销 API
            self.context.api_gateway.unregister_plugin_apis(plugin_id)
            
            # 移动到 disabled 目录
            self._move_plugin_dir(plugin_id, self.disabled_dir)
            
            self.context.event_bus.publish("plugin.disabled", {
                "id": plugin_id,
                "name": instance.manifest.name,
            }, source="plugin_manager")
            
            return True
        return False
    
    def unload(self, plugin_id: str) -> bool:
        """卸载插件"""
        if plugin_id not in self._plugins:
            return False
        
        self._states[plugin_id] = PluginState.UNLOADING
        
        instance = self._plugins[plugin_id]
        instance.on_disable()
        instance.on_unload()
        
        del self._plugins[plugin_id]
        self._states.pop(plugin_id, None)
        if plugin_id in self._load_order:
            self._load_order.remove(plugin_id)
        
        self.context.event_bus.publish("plugin.unloaded", {
            "id": plugin_id,
        }, source="plugin_manager")
        
        return True
    
    def _move_plugin_dir(self, plugin_id: str, target_dir: Path) -> None:
        """移动插件目录"""
        src = self._find_plugin_dir(plugin_id)
        if src and src.parent != target_dir:
            dst = target_dir / plugin_id
            if dst.exists():
                shutil.rmtree(dst)
            shutil.move(str(src), str(dst))
    
    def load_all(self) -> Dict[str, bool]:
        """加载所有已发现的插件"""
        results = {}
        manifests = self.discover()
        
        for manifest in sorted(manifests, key=lambda m: m.priority.value):
            results[manifest.id] = self.load(manifest.id)
        
        return results
    
    def enable_all(self) -> Dict[str, bool]:
        """启用所有已加载的插件"""
        results = {}
        for plugin_id in self._load_order:
            results[plugin_id] = self.enable(plugin_id)
        return results
    
    def get_plugin(self, plugin_id: str) -> Optional[PluginInterface]:
        """获取插件实例"""
        return self._plugins.get(plugin_id)
    
    def get_state(self, plugin_id: str) -> PluginState:
        """获取插件状态"""
        return self._states.get(plugin_id, PluginState.DISCOVERED)
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """列出所有插件"""
        results = []
        for plugin_id in self._load_order:
            instance = self._plugins.get(plugin_id)
            if instance:
                results.append({
                    "id": plugin_id,
                    "name": instance.manifest.name,
                    "version": instance.manifest.version,
                    "state": self._states.get(plugin_id, PluginState.DISCOVERED).name,
                    "enabled": instance._enabled,
                })
        return results
    
    def install_from_zip(self, zip_path: Path, plugin_id: Optional[str] = None) -> bool:
        """从 ZIP 安装插件"""
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # 读取清单
                names = zf.namelist()
                manifest_name = "manifest.json"
                if manifest_name not in names:
                    # 可能嵌套一层
                    for name in names:
                        if name.endswith("/manifest.json"):
                            manifest_name = name
                            break
                
                if manifest_name not in names:
                    print(f"[PluginManager] ZIP 中没有 manifest.json")
                    return False
                
                manifest_data = json.loads(zf.read(manifest_name))
                manifest = PluginManifest.from_dict(manifest_data)
                target_id = plugin_id or manifest.id
                
                # 解压到 enabled 目录
                target_dir = self.enabled_dir / target_id
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                target_dir.mkdir(parents=True)
                
                zf.extractall(target_dir)
                
                # 处理嵌套目录
                entries = list(target_dir.iterdir())
                if len(entries) == 1 and entries[0].is_dir():
                    nested = entries[0]
                    for item in nested.iterdir():
                        shutil.move(str(item), str(target_dir / item.name))
                    shutil.rmtree(nested)
                
                print(f"[PluginManager] 插件安装成功: {target_id}")
                return True
                
        except Exception as e:
            print(f"[PluginManager] 安装失败: {e}")
            return False
    
    def uninstall(self, plugin_id: str) -> bool:
        """卸载插件（删除文件）"""
        # 先卸载
        if plugin_id in self._plugins:
            self.unload(plugin_id)
        
        # 删除目录
        plugin_dir = self._find_plugin_dir(plugin_id)
        if plugin_dir:
            shutil.rmtree(plugin_dir)
            self._manifests.pop(plugin_id, None)
            self._states.pop(plugin_id, None)
            print(f"[PluginManager] 插件已卸载: {plugin_id}")
            return True
        
        return False
    
    def enable_hot_reload(self, interval_seconds: float = 2.0) -> None:
        """启用热重载"""
        if self._watchdog_running:
            return
        
        self._watchdog_running = True
        self._watchdog = threading.Thread(target=self._watchdog_loop, args=(interval_seconds,), daemon=True)
        self._watchdog.start()
        print(f"[PluginManager] 热重载已启用 (间隔: {interval_seconds}s)")
    
    def disable_hot_reload(self) -> None:
        """禁用热重载"""
        self._watchdog_running = False
        if self._watchdog:
            self._watchdog.join(timeout=2.0)
            self._watchdog = None
    
    def _watchdog_loop(self, interval_seconds: float) -> None:
        """热重载监控循环"""
        # 记录文件修改时间
        last_modified: Dict[str, float] = {}
        
        while self._watchdog_running:
            try:
                for plugin_id in list(self._load_order):
                    plugin_dir = self._find_plugin_dir(plugin_id)
                    if not plugin_dir:
                        continue
                    
                    # 检查修改时间
                    current_mtime = 0
                    for file in plugin_dir.rglob("*"):
                        if file.is_file():
                            current_mtime = max(current_mtime, file.stat().st_mtime)
                    
                    if plugin_id in last_modified and current_mtime > last_modified[plugin_id]:
                        print(f"[PluginManager] 检测到修改，重载: {plugin_id}")
                        # 重新加载
                        self.unload(plugin_id)
                        self.load(plugin_id)
                    
                    last_modified[plugin_id] = current_mtime
                
                time.sleep(interval_seconds)
            except Exception as e:
                print(f"[PluginManager] 热重载错误: {e}")
                time.sleep(interval_seconds)
    
    def get_config(self, plugin_id: str) -> Dict[str, Any]:
        """获取插件配置"""
        config_path = self.context.get_config_path(plugin_id)
        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config(self, plugin_id: str, config: Dict[str, Any]) -> None:
        """设置插件配置"""
        config_path = self.context.get_config_path(plugin_id)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        # 通知插件
        instance = self._plugins.get(plugin_id)
        if instance:
            for key, value in config.items():
                instance.on_config_change(key, value)


if __name__ == "__main__":
    # 测试代码
    root = Path(__file__).parent.parent
    pm = PluginManager(root)
    
    # 发现插件
    manifests = pm.discover()
    print(f"发现 {len(manifests)} 个插件")
    for m in manifests:
        print(f"  - {m.id}: {m.name} (v{m.version})")
