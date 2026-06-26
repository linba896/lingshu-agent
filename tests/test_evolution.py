#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 进化系统测试

测试覆盖：
  1. AgentEvolver 初始化与种群管理
  2. 技能变异（mutate）
  3. 技能交叉（crossover）
  4. 技能嫁接（graft）
  5. 技能压缩（compress）
  6. 适应度计算
  7. 锦标赛选择
  8. 进化一代（evolve_generation）
  9. SEAgent 反思与进化
  10. 进化统计

运行：
  pytest tests/test_evolution.py -v
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestAgentEvolver:
    """测试智能体进化器"""

    def _make_evolver(self, max_pop=10):
        from core.evolution import AgentEvolver
        with tempfile.TemporaryDirectory() as tmpdir:
            return AgentEvolver(Path(tmpdir), max_population=max_pop)

    def test_init(self):
        """初始化空种群"""
        evolver = self._make_evolver()
        assert len(evolver.population) == 0
        assert evolver.max_population == 10

    def test_add_skill(self):
        """添加技能到种群"""
        from core.evolution import EvolvedSkill
        evolver = self._make_evolver()
        skill = EvolvedSkill(
            name="click_skill",
            version="1.0.0",
            source_code="def click(): pass",
            performance_score=0.8,
            evolution_count=1,
            origin="original",
            created_at="2026-01-01T00:00:00",
        )
        evolver.population.append(skill)
        assert len(evolver.population) == 1

    def test_fitness(self):
        """适应度计算"""
        from core.evolution import EvolvedSkill
        evolver = self._make_evolver()
        skill = EvolvedSkill(
            name="test",
            version="1.0.0",
            source_code="pass",
            performance_score=0.9,
            evolution_count=5,
            origin="original",
            created_at="2026-01-01T00:00:00",
        )
        fitness = evolver._compute_fitness(skill)
        assert fitness > 0
        assert fitness <= 1.0

    def test_mutate(self):
        """技能变异"""
        from core.evolution import EvolvedSkill
        evolver = self._make_evolver()
        parent = EvolvedSkill(
            name="click",
            version="1.0.0",
            source_code="def click(): pass",
            performance_score=0.8,
            evolution_count=1,
            origin="original",
            created_at="2026-01-01T00:00:00",
        )
        child = evolver.mutate(parent)
        assert child.name == "click"
        assert child.version != "1.0.0"  # 版本号递增
        assert child.origin == "mutation"
        assert child.evolution_count == 2

    def test_crossover(self):
        """技能交叉"""
        from core.evolution import EvolvedSkill
        evolver = self._make_evolver()
        p1 = EvolvedSkill(
            name="click",
            version="1.0.0",
            source_code="def click(): pass",
            performance_score=0.7,
            evolution_count=1,
            origin="original",
            created_at="2026-01-01T00:00:00",
        )
        p2 = EvolvedSkill(
            name="click",
            version="1.1.0",
            source_code="def click(): return True",
            performance_score=0.9,
            evolution_count=2,
            origin="mutation",
            created_at="2026-01-02T00:00:00",
        )
        child = evolver.crossover(p1, p2)
        assert child is not None
        assert child.name == "click"
        assert child.origin == "crossover"

    def test_crossover_different_names(self):
        """不同名称技能不能交叉"""
        from core.evolution import EvolvedSkill
        evolver = self._make_evolver()
        p1 = EvolvedSkill(
            name="click", version="1.0.0", source_code="pass",
            performance_score=0.8, evolution_count=1,
            origin="original", created_at="2026-01-01T00:00:00",
        )
        p2 = EvolvedSkill(
            name="scroll", version="1.0.0", source_code="pass",
            performance_score=0.8, evolution_count=1,
            origin="original", created_at="2026-01-01T00:00:00",
        )
        child = evolver.crossover(p1, p2)
        assert child is None

    def test_graft(self):
        """技能嫁接"""
        from core.evolution import EvolvedSkill
        evolver = self._make_evolver()
        base = EvolvedSkill(
            name="click", version="1.0.0", source_code="def click(): pass",
            performance_score=0.8, evolution_count=1,
            origin="original", created_at="2026-01-01T00:00:00",
        )
        donor = EvolvedSkill(
            name="type", version="1.0.0", source_code="def type(): pass",
            performance_score=0.7, evolution_count=1,
            origin="original", created_at="2026-01-01T00:00:00",
        )
        child = evolver.graft(base, donor)
        assert child is not None
        assert "grafted" in child.name
        assert child.origin == "graft"

    def test_compress(self):
        """技能压缩"""
        from core.evolution import EvolvedSkill
        evolver = self._make_evolver()
        skill = EvolvedSkill(
            name="click", version="1.0.0",
            source_code="# comment\ndef click():\n    pass\n",
            performance_score=0.8, evolution_count=1,
            origin="original", created_at="2026-01-01T00:00:00",
        )
        compressed = evolver.compress(skill)
        assert compressed.origin == "compression"
        assert len(compressed.source_code) < len(skill.source_code)

    def test_bump_version(self):
        """版本号递增"""
        evolver = self._make_evolver()
        assert evolver._bump_version("1.0.0", "patch") == "1.0.1"
        assert evolver._bump_version("1.0.0", "minor") == "1.1.0"
        assert evolver._bump_version("1.0.0", "major") == "2.0.0"

    def test_evolve_generation(self):
        """进化一代"""
        from core.evolution import EvolvedSkill
        evolver = self._make_evolver(max_pop=5)
        # 添加初始技能
        for i in range(3):
            skill = EvolvedSkill(
                name=f"skill_{i}",
                version="1.0.0",
                source_code=f"def skill_{i}(): pass",
                performance_score=0.5 + i * 0.1,
                evolution_count=1,
                origin="original",
                created_at="2026-01-01T00:00:00",
            )
            evolver.population.append(skill)

        records = evolver.evolve_generation(n_mutations=2, n_crossovers=1)
        assert len(records) > 0
        # 种群不应超过上限
        assert len(evolver.population) <= 5

    def test_select_parents(self):
        """锦标赛选择"""
        from core.evolution import EvolvedSkill
        evolver = self._make_evolver()
        for i in range(5):
            skill = EvolvedSkill(
                name=f"s{i}", version="1.0.0", source_code="pass",
                performance_score=0.5 + i * 0.1, evolution_count=1,
                origin="original", created_at="2026-01-01T00:00:00",
            )
            evolver.population.append(skill)

        parents = evolver.select_parents(n=2)
        assert len(parents) == 2


class TestSEAgent:
    """测试自我进化智能体"""

    def _make_seagent(self):
        from core.evolution import SEAgent
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config = {
                "evolution_dir": "config/evolution",
                "max_population": 10,
                "reflection_interval_hours": 1,
            }
            return SEAgent(root, config)

    def test_reflect(self):
        """自我反思"""
        agent = self._make_seagent()
        log = agent.reflect("performance_drop", "high latency")
        assert log.trigger == "performance_drop"
        assert log.before_state == "high latency"
        assert log.improvement != ""
        assert 0 <= log.confidence <= 1.0

    def test_should_evolve(self):
        """进化触发检查"""
        agent = self._make_seagent()
        assert agent.should_evolve() is True  # 首次无 last_reflection

    def test_get_stats_empty(self):
        """空种群统计"""
        agent = self._make_seagent()
        stats = agent.get_evolution_stats()
        assert stats["status"] == "no_population"

    def test_get_stats_with_population(self):
        """有种群时的统计"""
        from core.evolution import EvolvedSkill
        agent = self._make_seagent()
        skill = EvolvedSkill(
            name="test", version="1.0.0", source_code="pass",
            performance_score=0.8, evolution_count=1,
            origin="original", created_at="2026-01-01T00:00:00",
        )
        agent.evolver.population.append(skill)

        stats = agent.get_evolution_stats()
        assert stats["population_size"] == 1
        assert stats["max_population"] == 10
        assert stats["best_skill"] == "test"

    def test_get_best_skill(self):
        """获取最佳技能"""
        from core.evolution import EvolvedSkill
        agent = self._make_seagent()
        s1 = EvolvedSkill(
            name="low", version="1.0.0", source_code="pass",
            performance_score=0.3, evolution_count=1,
            origin="original", created_at="2026-01-01T00:00:00",
        )
        s2 = EvolvedSkill(
            name="high", version="1.0.0", source_code="pass",
            performance_score=0.9, evolution_count=1,
            origin="original", created_at="2026-01-01T00:00:00",
        )
        agent.evolver.population = [s1, s2]
        best = agent.get_best_skill("high")
        assert best is not None
        assert best.name == "high"

        best_none = agent.get_best_skill("nonexistent")
        assert best_none is None


import pytest

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
