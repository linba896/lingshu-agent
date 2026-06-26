#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 多智能体协同测试

测试覆盖：
  1. MultiAgentCoordinator 初始化
  2. 专家智能体注册/注销
  3. 任务分发（dispatch）
  4. 多智能体协作（collaborate）
  5. 广播消息（broadcast）
  6. 系统状态查询

运行：
  pytest tests/test_multi_agent.py -v
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestMultiAgentCoordinator:
    """测试多智能体协调器"""

    def _make_coordinator(self):
        from core.multi_agent import MultiAgentCoordinator
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            return MultiAgentCoordinator(root, config={}, hardware_controller=None)

    def test_init(self):
        """协调器初始化带 4 个专家"""
        coord = self._make_coordinator()
        status = coord.get_system_status()
        assert status["agents_count"] == 4
        assert "视觉大师" in status["agent_names"]
        assert "数据管家" in status["agent_names"]
        assert "舞台导演" in status["agent_names"]
        assert "硬件控制器" in status["agent_names"]

    def test_dispatch_visual(self):
        """分发视觉任务"""
        coord = self._make_coordinator()
        from core.multi_agent import AgentTask
        task = AgentTask(
            id="t1",
            type="visual",
            description="制作海报",
            context={"topic": "AI"},
        )
        results = coord.dispatch(task)
        assert "视觉大师" in results
        assert "PPT" in results["视觉大师"] or "海报" in results["视觉大师"]

    def test_dispatch_data(self):
        """分发数据任务"""
        coord = self._make_coordinator()
        from core.multi_agent import AgentTask
        task = AgentTask(
            id="t2",
            type="data",
            description="分析Excel",
            context={"file": "report.xlsx"},
        )
        results = coord.dispatch(task)
        assert "数据管家" in results

    def test_dispatch_unknown(self):
        """未知类型任务分发到所有"""
        coord = self._make_coordinator()
        from core.multi_agent import AgentTask
        task = AgentTask(
            id="t3",
            type="unknown",
            description="随便做点什么",
            context={},
        )
        results = coord.dispatch(task)
        # 未知类型会尝试所有智能体
        assert len(results) > 0

    def test_collaborate(self):
        """多智能体协作"""
        coord = self._make_coordinator()
        results = coord.collaborate(
            task_description="制作年会PPT并数据分析",
            involved_agents=["视觉大师", "数据管家"],
            context={"topic": "2026年会"},
        )
        assert "视觉大师" in results
        assert "数据管家" in results
        assert "_summary" in results

    def test_broadcast(self):
        """广播消息"""
        coord = self._make_coordinator()
        coord.broadcast("coordinator", "系统即将维护", task_id="maint_001")
        status = coord.get_system_status()
        assert status["message_bus_count"] >= 1

    def test_unregister_agent(self):
        """注销智能体"""
        coord = self._make_coordinator()
        coord.unregister_agent("舞台导演")
        status = coord.get_system_status()
        assert "舞台导演" not in status["agent_names"]
        assert status["agents_count"] == 3

    def test_task_history(self):
        """任务历史记录"""
        coord = self._make_coordinator()
        from core.multi_agent import AgentTask
        task = AgentTask(
            id="t_hist",
            type="visual",
            description="测试",
            context={},
        )
        coord.dispatch(task)
        status = coord.get_system_status()
        assert status["task_queue"] >= 1


import pytest

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
