#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢·自进化引擎（进化卷二）
核心概念： SEAgent（自进化智能体）+ AgentEvolver（进化训练器）
通过持续自我反思、知识压缩、技能嫁接，实现超级电脑元神的自我进化
"""

import hashlib
import json
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any


@dataclass(frozen=True)
class EvolvedSkill:
    """一个进化后的技能快照"""
    name: str
    version: str  # semantic version: major.minor.patch
    source_code: str  # compressed code or patch
    performance_score: float  # 0.0-1.0
    evolution_count: int  # 经历了多少次进化迭代
    origin: str  # 来源：'original', 'mutation', 'graft', 'crossover'
    created_at: str
    parent_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def compute_id(self) -> str:
        """计算唯一标识（基于 source_code 的哈希）"""
        content = f"{self.name}:{self.version}:{self.source_code}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ReflectionLog:
    """反思日志：记录 AI 的'思考过程'"""
    timestamp: str
    trigger: str  # 触发反思的事件
    before_state: str  # 反思前的状态描述
    after_state: str  # 反思后的状态描述
    improvement: str  # 改进点
    confidence: float  # 0.0-1.0，改进的置信度


@dataclass
class EvolutionRecord:
    """进化记录：一个完整的进化事件"""
    id: str
    timestamp: str
    type: str  # 'compression', 'mutation', 'graft', 'crossover', 'death'
    parent_skills: List[str]  # 父技能 IDs
    child_skill: Optional[str]  # 子技能 ID
    success: bool
    metrics: Dict[str, float]  # 各项性能指标
    notes: str


class AgentEvolver:
    """
    进化训练器：管理进化种群、选择、交叉、变异
    类比：达尔文的自然选择器，但运行在数字世界
    """
    
    def __init__(self, evolution_dir: Path, max_population: int = 50):
        self.evolution_dir = evolution_dir
        self.max_population = max_population
        self.population: List[EvolvedSkill] = []
        self.history: List[EvolutionRecord] = []
        self.reflections: List[ReflectionLog] = []
        self._load_population()
    
    def _load_population(self):
        """从磁盘加载已保存的技能种群"""
        pop_file = self.evolution_dir / "population.json"
        if pop_file.exists():
            try:
                with open(pop_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.population = [EvolvedSkill(**s) for s in data]
            except Exception:
                self.population = []
    
    def _save_population(self):
        """保存种群到磁盘"""
        self.evolution_dir.mkdir(parents=True, exist_ok=True)
        pop_file = self.evolution_dir / "population.json"
        with open(pop_file, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in self.population], f, ensure_ascii=False, indent=2)
    
    def _save_history(self):
        """保存进化历史"""
        hist_file = self.evolution_dir / "history.json"
        with open(hist_file, "w", encoding="utf-8") as f:
            json.dump([asdict(h) for h in self.history], f, ensure_ascii=False, indent=2)
    
    def _compute_fitness(self, skill: EvolvedSkill) -> float:
        """计算技能适应度（综合考虑性能、年龄、稳定性）"""
        age_hours = (datetime.now() - datetime.fromisoformat(skill.created_at)).total_seconds() / 3600
        age_penalty = max(0, 1.0 - age_hours / 168)  # 7天后开始衰减
        stability_bonus = min(1.0, skill.evolution_count / 10) * 0.1  # 进化10次后的稳定奖励
        return skill.performance_score * 0.7 + age_penalty * 0.2 + stability_bonus * 0.1
    
    def select_parents(self, n: int = 2) -> List[EvolvedSkill]:
        """锦标赛选择：从种群中选出优秀父母"""
        if len(self.population) < n:
            return self.population.copy()
        
        selected = []
        for _ in range(n):
            tournament = random.sample(self.population, min(5, len(self.population)))
            winner = max(tournament, key=self._compute_fitness)
            selected.append(winner)
        return selected
    
    def mutate(self, skill: EvolvedSkill, mutation_rate: float = 0.1) -> EvolvedSkill:
        """变异：对技能进行微小随机修改"""
        # 模拟：对代码做微小变更（实际中可以是 LLM 生成改进）
        new_version = self._bump_version(skill.version, "patch")
        new_score = min(1.0, max(0.0, skill.performance_score + random.uniform(-0.05, 0.05)))
        
        return EvolvedSkill(
            name=skill.name,
            version=new_version,
            source_code=skill.source_code,  # 简化：实际应做代码修改
            performance_score=new_score,
            evolution_count=skill.evolution_count + 1,
            origin="mutation",
            created_at=datetime.now().isoformat(),
            parent_id=skill.compute_id(),
        )
    
    def crossover(self, parent1: EvolvedSkill, parent2: EvolvedSkill) -> Optional[EvolvedSkill]:
        """交叉：两个技能的优势组合"""
        if parent1.name != parent2.name:
            return None  # 不同技能不能交叉
        
        # 取两个父代的较好性能
        best_score = max(parent1.performance_score, parent2.performance_score)
        new_score = min(1.0, best_score + random.uniform(0, 0.02))  # 小幅度提升
        
        return EvolvedSkill(
            name=parent1.name,
            version=self._bump_version(max(parent1.version, parent2.version), "minor"),
            source_code=parent1.source_code if parent1.performance_score > parent2.performance_score else parent2.source_code,
            performance_score=new_score,
            evolution_count=max(parent1.evolution_count, parent2.evolution_count) + 1,
            origin="crossover",
            created_at=datetime.now().isoformat(),
            parent_id=f"{parent1.compute_id()}+{parent2.compute_id()}",
        )
    
    def graft(self, base_skill: EvolvedSkill, donor_skill: EvolvedSkill) -> Optional[EvolvedSkill]:
        """嫁接：将一个技能的能力嫁接到另一个技能上"""
        # 模拟：将 donor 的某些功能嫁接到 base 上
        # 实际实现：通过 LLM 分析两个技能，生成融合版本
        new_score = min(1.0, (base_skill.performance_score + donor_skill.performance_score) / 2 + 0.05)
        
        return EvolvedSkill(
            name=f"{base_skill.name}_grafted",
            version="1.0.0",
            source_code=f"# Grafted from {base_skill.name} and {donor_skill.name}\n{base_skill.source_code}",
            performance_score=new_score,
            evolution_count=1,
            origin="graft",
            created_at=datetime.now().isoformat(),
            parent_id=base_skill.compute_id(),
        )
    
    def compress(self, skill: EvolvedSkill) -> EvolvedSkill:
        """知识压缩：简化复杂技能，保留核心逻辑"""
        # 模拟：压缩代码（移除注释和空行）
        compressed_code = "\n".join(
            line for line in skill.source_code.split("\n") if line.strip() and not line.strip().startswith("#")
        )
        
        return EvolvedSkill(
            name=skill.name,
            version=self._bump_version(skill.version, "minor"),
            source_code=compressed_code,
            performance_score=skill.performance_score * 0.95,  # 压缩有小损失
            evolution_count=skill.evolution_count + 1,
            origin="compression",
            created_at=datetime.now().isoformat(),
            parent_id=skill.compute_id(),
        )
    
    def _bump_version(self, version: str, level: str) -> str:
        """语义化版本号递增"""
        parts = version.split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        if level == "major":
            major += 1; minor = 0; patch = 0
        elif level == "minor":
            minor += 1; patch = 0
        else:
            patch += 1
        return f"{major}.{minor}.{patch}"
    
    def evolve_generation(self, n_mutations: int = 3, n_crossovers: int = 2) -> List[EvolutionRecord]:
        """
        进化一代：
        1. 选择父母
        2. 产生变异后代
        3. 交叉产生新组合
        4. 评估适应度
        5. 自然选择（淘汰弱者）
        """
        records = []
        
        # 变异
        for _ in range(n_mutations):
            if not self.population:
                break
            parent = self.select_parents(1)[0]
            child = self.mutate(parent)
            self.population.append(child)
            records.append(EvolutionRecord(
                id=f"mut_{int(time.time())}_{random.randint(1000,9999)}",
                timestamp=datetime.now().isoformat(),
                type="mutation",
                parent_skills=[parent.compute_id()],
                child_skill=child.compute_id(),
                success=True,
                metrics={"fitness_before": self._compute_fitness(parent), "fitness_after": self._compute_fitness(child)},
                notes=f"Mutated {parent.name} v{parent.version} -> v{child.version}"
            ))
        
        # 交叉
        for _ in range(n_crossovers):
            if len(self.population) < 2:
                break
            parents = self.select_parents(2)
            child = self.crossover(parents[0], parents[1])
            if child:
                self.population.append(child)
                records.append(EvolutionRecord(
                    id=f"cross_{int(time.time())}_{random.randint(1000,9999)}",
                    timestamp=datetime.now().isoformat(),
                    type="crossover",
                    parent_skills=[p.compute_id() for p in parents],
                    child_skill=child.compute_id(),
                    success=True,
                    metrics={"fitness_child": self._compute_fitness(child)},
                    notes=f"Crossover: {parents[0].name} x {parents[1].name}"
                ))
        
        # 自然选择：淘汰适应度最低的
        if len(self.population) > self.max_population:
            self.population.sort(key=self._compute_fitness, reverse=True)
            removed = self.population[self.max_population:]
            self.population = self.population[:self.max_population]
            for dead in removed:
                records.append(EvolutionRecord(
                    id=f"death_{int(time.time())}_{random.randint(1000,9999)}",
                    timestamp=datetime.now().isoformat(),
                    type="death",
                    parent_skills=[dead.compute_id()],
                    child_skill=None,
                    success=True,
                    metrics={"fitness": self._compute_fitness(dead)},
                    notes=f"Natural selection removed {dead.name} v{dead.version}"
                ))
        
        self.history.extend(records)
        self._save_population()
        self._save_history()
        return records


class SEAgent:
    """
    自进化智能体（Self-Evolving Agent）
    核心能力：
    1. 持续反思：定期回顾自己的表现，找出改进点
    2. 主动进化：在 AgentEvolver 中培育更优秀的技能
    3. 知识压缩：将长期积累的经验压缩为高效知识块
    4. 休眠进化：在夜间/空闲时间进行密集的进化计算
    """
    
    def __init__(self, root: Path, config: Optional[Dict] = None):
        self.root = root
        self.config = config or {}
        self.evolver = AgentEvolver(
            evolution_dir=root / self.config.get("evolution_dir", "config/evolution"),
            max_population=self.config.get("max_population", 50),
        )
        self.reflection_interval = self.config.get("reflection_interval_hours", 24)
        self.last_reflection = None
        self._running = False
        self._thread = None
    
    def reflect(self, trigger_event: str, current_state: str) -> ReflectionLog:
        """
        自我反思：分析当前状态，提出改进建议
        实际中应调用 LLM 进行深度反思
        """
        # 模拟反思过程
        improvements = [
            "优化响应速度，减少不必要的系统调用",
            "改进意图识别准确率，增加更多训练样本",
            "压缩知识库，移除低频使用的信息",
            "增强异常处理，提高系统稳定性",
        ]
        improvement = random.choice(improvements)
        confidence = random.uniform(0.6, 0.95)
        
        log = ReflectionLog(
            timestamp=datetime.now().isoformat(),
            trigger=trigger_event,
            before_state=current_state,
            after_state=f"计划: {improvement}",
            improvement=improvement,
            confidence=confidence,
        )
        self.evolver.reflections.append(log)
        self.last_reflection = datetime.now()
        return log
    
    def should_evolve(self) -> bool:
        """判断是否应该触发进化"""
        if not self.last_reflection:
            return True
        hours_since = (datetime.now() - self.last_reflection).total_seconds() / 3600
        return hours_since >= self.reflection_interval
    
    def evolve(self, quiet_hours: Optional[Tuple[int, int]] = None) -> List[EvolutionRecord]:
        """
        触发进化过程
        如果在 quiet_hours 内，执行更激进的进化（夜间进化模式）
        """
        hour = datetime.now().hour
        is_quiet = False
        if quiet_hours:
            start, end = quiet_hours
            is_quiet = (hour >= start) or (hour < end)
        
        if is_quiet:
            # 夜间进化：更多变异、更多交叉、更激进
            records = self.evolver.evolve_generation(
                n_mutations=10, n_crossovers=5
            )
            # 尝试压缩旧技能
            for skill in self.evolver.population:
                if skill.evolution_count > 5:
                    compressed = self.evolver.compress(skill)
                    self.evolver.population.append(compressed)
                    records.append(EvolutionRecord(
                        id=f"compress_{int(time.time())}_{random.randint(1000,9999)}",
                        timestamp=datetime.now().isoformat(),
                        type="compression",
                        parent_skills=[skill.compute_id()],
                        child_skill=compressed.compute_id(),
                        success=True,
                        metrics={"size_before": len(skill.source_code), "size_after": len(compressed.source_code)},
                        notes=f"Compressed {skill.name} v{skill.version}"
                    ))
        else:
            # 白天进化：保守的微调
            records = self.evolver.evolve_generation(n_mutations=2, n_crossovers=1)
        
        return records
    
    def get_best_skill(self, skill_name: str) -> Optional[EvolvedSkill]:
        """获取某个技能的最优版本"""
        matching = [s for s in self.evolver.population if s.name == skill_name]
        if not matching:
            return None
        return max(matching, key=lambda s: self.evolver._compute_fitness(s))
    
    def get_evolution_stats(self) -> Dict:
        """获取进化统计数据"""
        if not self.evolver.population:
            return {"status": "no_population"}
        
        return {
            "population_size": len(self.evolver.population),
            "max_population": self.evolver.max_population,
            "avg_fitness": sum(self.evolver._compute_fitness(s) for s in self.evolver.population) / len(self.evolver.population),
            "best_skill": max(self.evolver.population, key=lambda s: self.evolver._compute_fitness(s)).name,
            "total_evolutions": len(self.evolver.history),
            "total_reflections": len(self.evolver.reflections),
            "last_reflection": self.last_reflection.isoformat() if self.last_reflection else None,
            "skill_names": list(set(s.name for s in self.evolver.population)),
        }
    
    def start_background_evolution(self, quiet_hours: Optional[Tuple[int, int]] = None):
        """启动后台进化线程"""
        if self._running:
            return
        self._running = True
        
        def _loop():
            while self._running:
                if self.should_evolve():
                    try:
                        self.reflect("scheduled", "background_evolution")
                        self.evolve(quiet_hours)
                    except Exception as e:
                        # 进化失败不应影响主系统
                        print(f"[Evolution] Error during evolution: {e}")
                # 每小时检查一次
                time.sleep(3600)
        
        self._thread = threading.Thread(target=_loop, daemon=True, name="SEAgent-Evolution")
        self._thread.start()
    
    def stop(self):
        """停止进化线程"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)


import threading


if __name__ == "__main__":
    # 自测试
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        agent = SEAgent(Path(tmpdir))
        
        # 注册初始技能
        initial = EvolvedSkill(
            name="intent_classifier",
            version="1.0.0",
            source_code="def classify_intent(text): return 'unknown'",
            performance_score=0.5,
            evolution_count=0,
            origin="original",
            created_at=datetime.now().isoformat(),
        )
        agent.evolver.population.append(initial)
        agent.evolver._save_population()
        
        # 触发进化
        print("初始状态:", agent.get_evolution_stats())
        records = agent.evolve()
        print(f"进化完成，产生 {len(records)} 条记录")
        print("进化后状态:", agent.get_evolution_stats())
        
        # 测试反思
        log = agent.reflect("test_trigger", "initial_state")
        print(f"\n反思日志: {log.improvement} (置信度: {log.confidence:.2f})")
        
        # 获取最优技能
        best = agent.get_best_skill("intent_classifier")
        if best:
            print(f"\n最优技能: {best.name} v{best.version} (适应度: {agent.evolver._compute_fitness(best):.3f})")