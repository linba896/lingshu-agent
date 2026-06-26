#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 记忆模块测试

测试覆盖：
  1. MemoryModule 初始化
  2. 知识存储与检索
  3. 操作录制
  4. 强化学习反馈（分数更新）
  5. 记忆清理与限制
  6. 统计查询

运行：
  pytest tests/test_memory.py -v
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestMemoryModule:
    """测试记忆学习引擎"""

    def _make_memory(self, tmpdir=None, max_entries=100):
        from core.memory import MemoryModule
        if tmpdir is None:
            tmpdir = tempfile.mkdtemp()
        root = Path(tmpdir)
        config = {
            "db_path": str(root / "vector_db"),
            "records_path": str(root / "records"),
            "knowledge_path": str(root / "entries.json"),
            "max_entries": max_entries,
            "similarity_threshold": 0.5,
        }
        return MemoryModule(config, root=root)

    def test_init(self):
        """测试初始化"""
        memory = self._make_memory()
        assert memory is not None
        stats = memory.get_stats()
        assert stats["total_entries"] == 0

    def test_store_and_search(self):
        """存储和检索"""
        memory = self._make_memory()
        mid = memory.store_knowledge("Python 是一种编程语言", tags=["编程"])
        assert mid is not None
        assert len(mid) > 0

        # 简单检索（降级模式）
        results = memory.search("Python 编程", top_k=5)
        assert len(results) >= 1
        assert results[0]["memory_type"] == "knowledge"

    def test_store_conversation(self):
        """存储对话"""
        memory = self._make_memory()
        mid = memory.store_conversation("你好", "你好！我是灵枢。")
        assert mid is not None
        entries = memory.list_memories(memory_type="conversation")
        assert len(entries) >= 1

    def test_feedback(self):
        """强化学习反馈"""
        memory = self._make_memory()
        mid = memory.store_knowledge("测试知识")
        entry_before = memory.get_memory(mid)
        score_before = entry_before["score"]

        memory.feedback(mid, success=True, feedback_text="很有用")
        entry_after = memory.get_memory(mid)
        assert entry_after["score"] > score_before

        memory.feedback(mid, success=False, feedback_text="不准确")
        entry_final = memory.get_memory(mid)
        assert entry_final["score"] < entry_after["score"]

    def test_delete_memory(self):
        """删除记忆"""
        memory = self._make_memory()
        mid = memory.store_knowledge("临时知识")
        assert memory.get_memory(mid) is not None

        ok = memory.delete_memory(mid)
        assert ok is True
        assert memory.get_memory(mid) is None

    def test_trim_entries(self):
        """记忆数量限制"""
        memory = self._make_memory(max_entries=3)
        for i in range(5):
            memory.store_knowledge(f"知识 {i}")

        memory._trim_entries()
        stats = memory.get_stats()
        assert stats["total_entries"] <= 3

    def test_get_stats(self):
        """统计信息"""
        memory = self._make_memory()
        memory.store_knowledge("A", tags=["t1"])
        memory.store_knowledge("B", tags=["t2"])
        memory.store_conversation("Hi", "Hello")

        stats = memory.get_stats()
        assert stats["total_entries"] == 3
        assert "knowledge" in stats["type_distribution"]
        assert "conversation" in stats["type_distribution"]

    def test_record_sequence(self):
        """录制操作序列"""
        memory = self._make_memory()
        actions = [
            {"action_type": "click", "x": 100, "y": 200},
            {"action_type": "type", "text": "hello"},
        ]
        rid = memory.store_action_record("测试序列", actions)
        assert rid is not None

        records = memory.list_records()
        assert len(records) == 1
        assert records[0]["sequence_name"] == "测试序列"
        assert records[0]["action_count"] == 2

    def test_context_injection(self):
        """上下文注入"""
        memory = self._make_memory()
        memory.store_knowledge("Python 函数使用 def 关键字定义")
        memory.store_knowledge("JavaScript 函数使用 function 关键字")

        context = memory.get_context("如何定义 Python 函数", top_k=2)
        assert "Python" in context or "def" in context


import pytest

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
