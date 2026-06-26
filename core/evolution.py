#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢·进化卷（自我进化模块）
核心概念： SEAgent（自我进化智能体）+ AgentEvolver（智能体进化器）
通过自我反思、知识压缩、技能嫁接，实现持续自我进化与元认知提升

核心机制：
  1. 自我反思：定期评估性能、识别瓶颈、制定改进计划
  2. 技能压缩：将高频技能固化为直觉，减少推理延迟
  3. 知识嫁接：跨领域迁移，将A领域技能适配到B领域
  4. 进化记录：完整记录进化历程，支持回滚和审计
  5. 元认知：监控自身认知过程，优化决策策略

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
    """进化后的技能"""
    name: str
    version: str  # semantic version: major.minor.patch
    source_code: str  # compressed code or patch
    performance_score: float  # 0.0-1.0
    evolution_count: int  # 进化次数
    origin: str  # 'original', 'mutation', 'graft', 'crossover'
    created_at: str
    parent_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def compute_id(self) -> str:
        """计算技能唯一ID（基于源代码+版本）"""
        content = f"{self.name}:{self.version}:{self.source_code}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class ReflectionLog:
    """反思日志：记录 AI 对某个'决策节点'的反思"""
    timestamp: str
    trigger: str  # 触发反思的事件
    before_state: str  # 反思前的状态
    after_state: str  # 反思后的状态
    improvement: str  # 改进措施
    confidence: float  # 0.0-1.0，改进措施的可信度


@dataclass
class EvolutionRecord:
    """进化记录：记录一次完整的进化过程"""
    id: str
    timestamp: str
    type: str  # 'compression', 'mutation', 'graft', 'crossover', 'death'
    parent_skills: List[str]  # 父技能 IDs
    child_skill: Optional[str]  # 子技能 ID
    success: bool
    metrics: Dict[str, float]  # 进化指标
    notes: str


class AgentEvolver:
    """
    智能体进化器
    
    管理技能种群，通过自然选择实现持续进化：
    - 技能压缩：将高频技能固化为直觉
    - 技能突变：随机修改技能参数，探索新能力
    - 技能嫁接：跨领域迁移，组合不同技能
    - 自然选择：淘汰低效技能，保留优秀技能
    """
    
    def __init__(self, evolution_dir: Path, max_population: int = 50):
        self.evolution_dir = evolution_dir
        self.max_population = max_population
        self.population: List[EvolvedSkill] = []
        self.history: List[EvolutionRecord] = []
        self.reflections: List[ReflectionLog] = []
        self._load_population()
    
    def _load_population(self):
        """从目录加载技能种群"""
        pop_file = self.evolution_dir / "population.json"
        if pop_file.exists():
            try:
                with open(pop_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.population = [EvolvedSkill(**s) for s in data]
            except Exception:
                self.population = []
    
    def _save_population(self):
        """保存技能种群到文件"""
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
        """计算技能适应度"""
        # 综合考虑：性能、稳定性、使用频率、复杂度
        age_hours = (datetime.now() - datetime.fromisoformat(skill.created_at)).total_seconds() / 3600
        age_penalty = max(0, 1.0 - age_hours / 168)  # 168小时=1周衰减
        stability_bonus = min(1.0, skill.evolution_count / 10) * 0.1  # 进化10次以上有稳定性奖励
        return skill.performance_score * 0.7 + age_penalty * 0.2 + stability_bonus * 0.1
    
    def select_parents(self, n: int = 2) -> List[EvolvedSkill]:
        """选择父技能（锦标赛选择）"""
        if len(self.population) < n:
            return self.population.copy()
        
        selected = []
        for _ in range(n):
            tournament = random.sample(self.population, min(5, len(self.population)))
            winner = max(tournament, key=self._compute_fitness)
            selected.append(winner)
        return selected
    
    def mutate(self, skill: EvolvedSkill, mutation_rate: float = 0.1) -> EvolvedSkill:
        """变异：对技能进行随机微调"""
        # 模拟技能参数微调（实际实现需修改 LLM 提示词或权重）
        new_version = self._bump_version(skill.version, "patch")
        new_score = min(1.0, max(0.0, skill.performance_score + random.uniform(-0.05, 0.05)))
        
        return EvolvedSkill(
            name=skill.name,
            version=new_version,
            source_code=skill.source_code,  # 模拟技能代码微调
           performance_score=new_score,
            evolution_count=skill.evolution_count + 1,
            origin="mutation",
            created_at=datetime.now().isoformat(),
            parent_id=skill.compute_id(),
        )
    
    def crossover(self, parent1: EvolvedSkill, parent2: EvolvedSkill) -> Optional[EvolvedSkill]:
        """交叉：两个技能的组合"""
        if parent1.name != parent2.name:
            return None  # 不同技能不能交叉
        
        # 模拟技能组合（实际实现需合并两个 LLM 提示词）
        best_score = max(parent1.performance_score, parent2.performance_score)
        new_score = min(1.0, best_score + random.uniform(0, 0.02))  # 轻微提升
        
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
        """嫁接：将 donor 的技能嫁接到 base 上"""
        # 模拟技能嫁接（实际实现需合并两个技能的提示词）
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
        """压缩：将技能压缩为更简洁的形式"""
        # 模拟技能压缩（实际实现需使用 LLM 压缩提示词）
        compressed_code = f"# Compressed version of {skill.name}\n" + "\n".join(
            line for line in skill.source_code.split("\n") if line.strip() and not line.strip().startswith("#")
        )
        
        return EvolvedSkill(
            name=skill.name,
            version=self._bump_version(skill.version, "minor"),
            source_code=compressed_code,
            performance_score=skill.performance_score * 0.95,  # 压缩可能略有性能损失
            evolution_count=skill.evolution_count + 1,
            origin="compression",
            created_at=datetime.now().isoformat(),
            parent_id=skill.compute_id(),
        )
    
    def _bump_version(self, version: str, level: str) -> str:
        """版本号递增"""
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
        进化一代
        
        流程：
        1. 选择父技能（锦标赛选择）
        2. 变异生成新技能
        3. 交叉生成新技能
        4. 评估适应度
        5. 自然选择（淘汰低效技能）
        6. 压缩高频技能
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
        
        # 自然选择（淘汰低效技能）
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
    自我进化智能体（Self-Evolving Agent）
    
    核心功能：
    1. 自我反思：定期评估性能、识别瓶颈、制定改进计划
    2. 主动进化：在安静时段自动执行技能进化
    3. 知识压缩：将高频技能固化为直觉，减少推理延迟
    4. 进化记录：完整记录进化历程，支持回滚和审计
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
        自我反思
        
        触发条件：
        - 定期触发（每24小时）
        - 性能下降时（错误率>5%）
        - 用户反馈时（好评/差评）
        - 新技能学习时（知识膨胀）
        
        反思内容：
        - 过去一段时间的表现回顾
        - 识别瓶颈和错误模式
        - 制定改进计划（技能优化、知识压缩、参数调整）
        """
        # 模拟反思过程（实际实现需使用 LLM 生成反思内容）
        improvements = [
            "优化响应速度：减少 LLM 推理延迟",
            "提升准确率：增加上下文理解能力",
            "知识压缩：将高频技能固化为直觉",
            "技能嫁接：跨领域迁移通用技能",
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
        """检查是否应该进化"""
        if not self.last_reflection:
            return True
        hours_since = (datetime.now() - self.last_reflection).total_seconds() / 3600
        return hours_since >= self.reflection_interval
    
    def evolve(self, quiet_hours: Optional[Tuple[int, int]] = None) -> List[EvolutionRecord]:
        """
        执行进化
        
        在安静时段执行进化：
        - 变异：随机调整技能参数
        - 交叉：组合两个技能
        - 选择：淘汰低效技能
        - 压缩：将高频技能压缩为直觉
        """
        hour = datetime.now().hour
        is_quiet = False
        if quiet_hours:
            start, end = quiet_hours
            is_quiet = (hour >= start) or (hour < end)
        
        if is_quiet:
            # 安静时段：大量进化（变异、交叉、压缩）
            records = self.evolver.evolve_generation(
                n_mutations=10, n_crossovers=5
            )
            # 压缩高频技能
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
            # 非安静时段：少量进化（仅变异）
            records = self.evolver.evolve_generation(n_mutations=2, n_crossovers=1)
        
        return records
    
    def get_best_skill(self, skill_name: str) -> Optional[EvolvedSkill]:
        """获取指定技能的最佳版本"""
        matching = [s for s in self.evolver.population if s.name == skill_name]
        if not matching:
            return None
        return max(matching, key=lambda s: self.evolver._compute_fitness(s))
    
    def get_evolution_stats(self) -> Dict:
        """获取进化统计信息"""
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
                        print(f"[SEAgent] 进化失败: {e}")
                # 每小时检查一次
                time.sleep(3600)
        
        self._thread = threading.Thread(target=_loop, daemon=True, name="SEAgent-Evolution")
        self._thread.start()
        print("[SEAgent] 🧬 后台进化线程已启动")

    def stop(self):
        """停止后台进化"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        print("[SEAgent] 后台进化线程已停止")

