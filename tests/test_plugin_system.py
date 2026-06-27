#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 插件系统测试
覆盖：PluginManager、PluginManifest、PluginSandbox、PluginEventBus、PluginAPIGateway
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# 将项目根目录加入路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.plugin_system import (
    PluginManager,
    PluginManifest,
    PluginState,
    PluginPriority,
    PluginSandbox,
    PluginEventBus,
    PluginAPIGateway,
    PluginContext,
    PluginInterface,
    PluginSecurityError,
)


@pytest.fixture
def temp_root():
    """临时项目根目录"""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_manifest():
    """示例插件清单"""
    return PluginManifest(
        id="test.plugin",
        name="测试插件",
        version="1.0.0",
        author="测试者",
        description="用于测试的插件",
        permissions=["read_file"],
        priority=PluginPriority.NORMAL,
        tags=["test"],
    )


class TestPluginManifest:
    """测试插件清单"""

    def test_create_manifest(self, sample_manifest):
        assert sample_manifest.id == "test.plugin"
        assert sample_manifest.name == "测试插件"
        assert sample_manifest.version == "1.0.0"

    def test_manifest_to_dict(self, sample_manifest):
        d = sample_manifest.to_dict()
        assert d["id"] == "test.plugin"
        assert d["priority"] == "NORMAL"
        assert "permissions" in d

    def test_manifest_from_dict(self):
        data = {
            "id": "demo.plugin",
            "name": "演示插件",
            "version": "0.1.0",
            "author": "作者",
            "description": "演示",
            "priority": "HIGH",
        }
        m = PluginManifest.from_dict(data)
        assert m.id == "demo.plugin"
        assert m.priority == PluginPriority.HIGH


class TestPluginSandbox:
    """测试插件沙箱"""

    def test_safe_code_execution(self, temp_root):
        sandbox = PluginSandbox("test", temp_root)
        code = "result = 1 + 1\n"
        # 沙箱应允许基础运算
        result = sandbox.execute("x = 42\n")
        assert result is not None

    def test_blocked_builtins(self, temp_root):
        sandbox = PluginSandbox("test", temp_root)
        # eval 和 exec 应在被禁列表中
        assert "eval" in sandbox.BLOCKED_BUILTINS
        assert "exec" in sandbox.BLOCKED_BUILTINS
        assert "open" in sandbox.BLOCKED_BUILTINS

    def test_allowed_modules(self, temp_root):
        sandbox = PluginSandbox("test", temp_root)
        assert "json" in sandbox.ALLOWED_MODULES
        assert "datetime" in sandbox.ALLOWED_MODULES

    def test_syntax_error(self, temp_root):
        sandbox = PluginSandbox("test", temp_root)
        with pytest.raises(PluginSecurityError):
            sandbox.execute("def broken(  # 不完整代码")


class TestPluginEventBus:
    """测试事件总线"""

    def test_subscribe_and_publish(self):
        bus = PluginEventBus()
        events = []

        def handler(data, source):
            events.append((data, source))

        bus.subscribe("test.event", handler)
        count = bus.publish("test.event", {"msg": "hello"}, source="test")

        assert count == 1
        assert len(events) == 1
        assert events[0][0]["msg"] == "hello"
        assert events[0][1] == "test"

    def test_unsubscribe(self):
        bus = PluginEventBus()
        events = []

        def handler(data, source):
            events.append(data)

        bus.subscribe("test.event", handler)
        bus.unsubscribe("test.event", handler)
        count = bus.publish("test.event", {"msg": "hello"})

        assert count == 0
        assert len(events) == 0

    def test_multiple_subscribers(self):
        bus = PluginEventBus()
        results = []

        def h1(data, source):
            results.append("h1")

        def h2(data, source):
            results.append("h2")

        bus.subscribe("multi", h1)
        bus.subscribe("multi", h2)
        count = bus.publish("multi", {})

        assert count == 2
        assert sorted(results) == ["h1", "h2"]


class TestPluginAPIGateway:
    """测试 API 网关"""

    def test_register_and_call_api(self):
        gateway = PluginAPIGateway()

        def hello_api(name="world"):
            return f"hello, {name}"

        gateway.register_api("test", "hello", hello_api)
        result = gateway.call_api("test", "hello", name="lingshu")
        assert result == "hello, lingshu"

    def test_unregister_plugin(self):
        gateway = PluginAPIGateway()
        gateway.register_api("p1", "api1", lambda: 1)
        gateway.unregister_plugin_apis("p1")
        assert gateway.list_apis("p1") == {"p1": []}

    def test_list_apis(self):
        gateway = PluginAPIGateway()
        gateway.register_api("p1", "api1", lambda: 1)
        gateway.register_api("p1", "api2", lambda: 2)
        apis = gateway.list_apis("p1")
        assert len(apis["p1"]) == 2


class TestPluginManager:
    """测试插件管理器"""

    def test_init_creates_directories(self, temp_root):
        manager = PluginManager(temp_root)
        assert (temp_root / "plugins" / "enabled").exists()
        assert (temp_root / "plugins" / "disabled").exists()
        assert (temp_root / "plugins" / ".cache").exists()

    def test_discover_empty(self, temp_root):
        manager = PluginManager(temp_root)
        manifests = manager.discover()
        assert manifests == []

    def test_discover_with_manifest(self, temp_root):
        manager = PluginManager(temp_root)
        # 创建模拟插件
        plugin_dir = temp_root / "plugins" / "enabled" / "demo.plugin"
        plugin_dir.mkdir(parents=True)
        manifest = {
            "id": "demo.plugin",
            "name": "演示插件",
            "version": "1.0.0",
            "author": "测试",
            "description": "演示",
        }
        (plugin_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        manifests = manager.discover()
        assert len(manifests) == 1
        assert manifests[0].id == "demo.plugin"

    def test_get_state(self, temp_root):
        manager = PluginManager(temp_root)
        assert manager.get_state("nonexistent") == PluginState.DISCOVERED

    def test_list_plugins_empty(self, temp_root):
        manager = PluginManager(temp_root)
        assert manager.list_plugins() == []

    def test_enable_nonexistent(self, temp_root):
        manager = PluginManager(temp_root)
        assert manager.enable("nonexistent") == False

    def test_disable_nonexistent(self, temp_root):
        manager = PluginManager(temp_root)
        assert manager.disable("nonexistent") == False

    def test_unload_nonexistent(self, temp_root):
        manager = PluginManager(temp_root)
        assert manager.unload("nonexistent") == False

    def test_plugin_context_paths(self, temp_root):
        manager = PluginManager(temp_root)
        ctx = manager.context
        assert ctx.get_config_path("test") == temp_root / "config" / "plugins" / "test.json"
        assert ctx.get_data_path("test") == temp_root / "data" / "plugins" / "test"
        assert ctx.get_temp_path("test") == temp_root / "temp" / "plugins" / "test"


class TestPluginInterface:
    """测试插件接口基类"""

    def test_lifecycle(self, sample_manifest):
        class DummyPlugin(PluginInterface):
            def on_load(self):
                return True

        ctx = PluginContext(
            agent_root=Path("."),
            config_dir=Path("."),
            data_dir=Path("."),
            temp_dir=Path("."),
            logger=None,
            event_bus=PluginEventBus(),
            api_gateway=PluginAPIGateway(),
        )
        plugin = DummyPlugin(sample_manifest, ctx)
        assert plugin.on_load() == True
        assert plugin.on_enable() == True
        assert plugin.on_disable() == True
        assert plugin._enabled == False

    def test_api_default(self, sample_manifest):
        class DummyPlugin(PluginInterface):
            pass

        ctx = PluginContext(
            agent_root=Path("."),
            config_dir=Path("."),
            data_dir=Path("."),
            temp_dir=Path("."),
            logger=None,
            event_bus=PluginEventBus(),
            api_gateway=PluginAPIGateway(),
        )
        plugin = DummyPlugin(sample_manifest, ctx)
        assert plugin.get_api() == []

        with pytest.raises(NotImplementedError):
            plugin.call_api("unknown")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
