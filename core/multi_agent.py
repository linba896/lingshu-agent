#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢·多智能体协调器（进化卷三）
核心概念：Expert Panel（专家面板）+ Skill Decentralization（技能去中心化）
实现多智能体协同处理复杂任务
"""

import json
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable


@dataclass
class AgentTask:
    """任务描述"""
    id: str
    type: str  # 'query', 'analysis', 'creation', 'control', 'validation'
    description: str
    context: Dict[str, Any]
    priority: int = 5  # 1-10, 10最高
    deadline: Optional[str] = None
    status: str = "pending"  # pending, assigned, processing, completed, failed
    result: Optional[str] = None


@dataclass
class AgentMessage:
    """智能体间消息"""
    from_agent: str
    to_agent: str
    type: str  # 'request', 'response', 'broadcast', 'alert'
    content: str
    timestamp: str
    task_id: Optional[str] = None


class BaseAgent(ABC):
    """所有专家智能体的基类"""
    
    def __init__(self, name: str, specialty: str, description: str):
        self.name = name
        self.specialty = specialty
        self.description = description
        self.status = "idle"  # idle, busy, offline
        self.memory: List[Dict] = []  # 工作记忆
        self._message_queue: List[AgentMessage] = []
        self._lock = threading.Lock()
    
    @abstractmethod
    def process(self, task: AgentTask) -> str:
        """处理任务，返回结果"""
        pass
    
    def receive_message(self, msg: AgentMessage):
        """接收来自其他智能体的消息"""
        with self._lock:
            self._message_queue.append(msg)
    
    def get_messages(self) -> List[AgentMessage]:
        """获取待处理消息"""
        with self._lock:
            msgs = self._message_queue.copy()
            self._message_queue.clear()
            return msgs
    
    def add_memory(self, entry: Dict):
        """添加记忆条目"""
        self.memory.append({
            **entry,
            "timestamp": datetime.now().isoformat(),
        })
        # 限制记忆大小
        if len(self.memory) > 1000:
            self.memory = self.memory[-800:]


class VisualMasterAgent(BaseAgent):
    """视觉大师：负责视觉创作、设计、审美"""
    
    def __init__(self):
        super().__init__(
            name="视觉大师",
            specialty="visual",
            description="负责视觉生成、海报设计、PPT制作、图片优化",
        )
    
    def process(self, task: AgentTask) -> str:
        self.status = "busy"
        try:
            desc = task.description.lower()
            if "ppt" in desc or "幻灯片" in desc or "presentation" in desc:
                result = self._make_ppt(task)
            elif "海报" in desc or "poster" in desc or "banner" in desc:
                result = self._make_poster(task)
            elif "图片" in desc or "image" in desc or "图" in desc:
                result = self._generate_image(task)
            else:
                result = f"[视觉大师] 收到视觉任务: {task.description}\n" \
                        "→ 分析视觉需求 → 构思构图 → 生成视觉方案\n" \
                        "→ 输出: 视觉设计草图已生成（模拟）"
            
            self.add_memory({
                "task_id": task.id,
                "action": "visual_creation",
                "result": result,
            })
            return result
        finally:
            self.status = "idle"
    
    def _make_ppt(self, task: AgentTask) -> str:
        topic = task.context.get("topic", "未指定主题")
        return f"[PPT制作] 主题: {topic}\n" \
               "1. 设计封面页（主标题 + 副标题 + 视觉焦点）\n" \
               "2. 目录页（结构化大纲）\n" \
               "3. 内容页（图表 + 要点）\n" \
               "4. 总结页\n" \
               "→ 输出: PPT 结构方案已生成，待填充具体内容"
    
    def _make_poster(self, task: AgentTask) -> str:
        return f"[海报设计] {task.description}\n" \
               "→ 选择配色方案 → 设计排版 → 添加视觉元素 → 输出高清海报"
    
    def _generate_image(self, task: AgentTask) -> str:
        return f"[图像生成] {task.description}\n" \
               "→ 分析描述 → 生成提示词 → 调用图像模型 → 输出图像"


class DataStewardAgent(BaseAgent):
    """数据管家：负责数据治理、表格管理、流程优化"""
    
    def __init__(self):
        super().__init__(
            name="数据管家",
            specialty="data",
            description="负责数据整理、表格优化、流程自动化、数据质量检查",
        )
    
    def process(self, task: AgentTask) -> str:
        self.status = "busy"
        try:
            desc = task.description.lower()
            if "表格" in desc or "excel" in desc or "sheet" in desc:
                result = self._process_spreadsheet(task)
            elif "数据" in desc or "data" in desc:
                result = self._analyze_data(task)
            elif "流程" in desc or "workflow" in desc or "自动化" in desc:
                result = self._optimize_workflow(task)
            else:
                result = f"[数据管家] 收到数据处理任务: {task.description}\n" \
                        "→ 数据清洗 → 结构化整理 → 质量验证 → 输出标准化数据"
            
            self.add_memory({
                "task_id": task.id,
                "action": "data_processing",
                "result": result,
            })
            return result
        finally:
            self.status = "idle"
    
    def _process_spreadsheet(self, task: AgentTask) -> str:
        return f"[表格处理] {task.description}\n" \
               "1. 读取数据源\n" \
               "2. 数据清洗（去重、格式标准化）\n" \
               "3. 公式计算与验证\n" \
               "4. 条件格式与可视化\n" \
               "5. 输出优化后的表格"
    
    def _analyze_data(self, task: AgentTask) -> str:
        return f"[数据分析] {task.description}\n" \
               "→ 统计描述 → 趋势分析 → 异常检测 → 生成分析报告"
    
    def _optimize_workflow(self, task: AgentTask) -> str:
        return f"[流程优化] {task.description}\n" \
               "→ 现状分析 → 瓶颈识别 → 自动化方案 → 效率提升报告"


class StageDirectorAgent(BaseAgent):
    """舞台导演：负责酒店/舞台场景控制、灯光编排、氛围调度"""
    
    def __init__(self, hardware_controller=None):
        super().__init__(
            name="舞台导演",
            specialty="stage",
            description="负责舞台场景设计、灯光编排、氛围控制、演出调度",
        )
        self.hardware = hardware_controller
    
    def process(self, task: AgentTask) -> str:
        self.status = "busy"
        try:
            desc = task.description.lower()
            if "灯光" in desc or "lighting" in desc or "dmx" in desc:
                result = self._design_lighting(task)
            elif "场景" in desc or "scene" in desc or "氛围" in desc:
                result = self._setup_scene(task)
            elif "演出" in desc or "show" in desc or "performance" in desc:
                result = self._plan_show(task)
            else:
                result = f"[舞台导演] 收到舞台任务: {task.description}\n" \
                        "→ 分析场景需求 → 设计灯光方案 → 编排节奏 → 输出控制指令"
            
            self.add_memory({
                "task_id": task.id,
                "action": "stage_control",
                "result": result,
            })
            return result
        finally:
            self.status = "idle"
    
    def _design_lighting(self, task: AgentTask) -> str:
        # 实际中应调用 hardware controller 发送 DMX 指令
        cues = [
            {"time": 0, "channel": 1, "value": 255, "desc": "主光全开"},
            {"time": 5, "channel": 2, "value": 180, "desc": "侧光暖色"},
            {"time": 10, "channel": 3, "value": 200, "desc": "背光冷色"},
        ]
        if self.hardware:
            for cue in cues:
                self.hardware.send_dmx({cue["channel"]: cue["value"]})
        
        return f"[灯光设计] {task.description}\n" + "\n".join(
            f"  T+{c['time']}s: Ch{c['channel']}={c['value']} ({c['desc']})" for c in cues
        ) + "\n→ 灯光方案已生成并发送至控制器"
    
    def _setup_scene(self, task: AgentTask) -> str:
        scene_type = task.context.get("scene_type", "general")
        return f"[场景设置] 类型: {scene_type}\n" \
               "→ 灯光预设加载 → 音响设备检查 → 环境传感器校准 → 场景就绪"
    
    def _plan_show(self, task: AgentTask) -> str:
        return f"[演出编排] {task.description}\n" \
               "1. 开场：渐亮 → 音乐起\n" \
               "2. 发展：灯光变化配合情节\n" \
               "3. 高潮：全亮 + 特效\n" \
               "4. 结尾：渐暗 → 谢幕"


class HardwareControllerAgent(BaseAgent):
    """硬件控制器：负责设备管理、协议转换、紧急控制"""
    
    def __init__(self, hardware_controller=None):
        super().__init__(
            name="硬件控制器",
            specialty="hardware",
            description="负责设备状态监控、协议管理、紧急停止、安全控制",
        )
        self.hardware = hardware_controller
        self.emergency_status = False
    
    def process(self, task: AgentTask) -> str:
        self.status = "busy"
        try:
            desc = task.description.lower()
            if "紧急" in desc or "emergency" in desc or "停止" in desc:
                result = self._emergency_stop(task)
            elif "设备" in desc or "device" in desc or "状态" in desc:
                result = self._check_devices(task)
            elif "协议" in desc or "protocol" in desc or "连接" in desc:
                result = self._manage_protocol(task)
            else:
                result = f"[硬件控制器] 收到硬件任务: {task.description}\n" \
                        "→ 设备识别 → 协议匹配 → 指令发送 → 状态确认"
            
            self.add_memory({
                "task_id": task.id,
                "action": "hardware_control",
                "result": result,
            })
            return result
        finally:
            self.status = "idle"
    
    def _emergency_stop(self, task: AgentTask) -> str:
        self.emergency_status = True
        if self.hardware:
            self.hardware.emergency_stop()
        return "🚨 [紧急停止] 所有硬件输出已切断！\n" \
               "→ 灯光: 关闭\n" \
               "→ 音响: 静音\n" \
               "→ 电机: 停止\n" \
               "→ 系统进入安全状态"
    
    def _check_devices(self, task: AgentTask) -> str:
        if self.hardware:
            protocols = self.hardware.get_available_protocols()
            scene = self.hardware.get_scene()
            return f"[设备状态] 当前场景: {scene}\n" \
                   f"可用协议: {', '.join(protocols)}\n" \
                   "所有设备运行正常"
        return "[设备状态] 硬件控制器未连接"
    
    def _manage_protocol(self, task: AgentTask) -> str:
        protocol = task.context.get("protocol", "TCP")
        return f"[协议管理] 协议: {protocol}\n" \
               "→ 连接建立 → 心跳检测 → 指令测试 → 连接稳定"


class MultiAgentCoordinator:
    """
    多智能体协调器：Expert Panel 的核心调度器
    负责任务分发、智能体间通信、结果汇总
    """
    
    def __init__(self, root: Path, config: Optional[Dict] = None, hardware_controller=None):
        self.root = root
        self.config = config or {}
        self.agents: Dict[str, BaseAgent] = {}
        self.task_history: List[AgentTask] = []
        self.message_bus: List[AgentMessage] = []
        self._lock = threading.Lock()
        
        # 注册默认专家
        self.register_agent(VisualMasterAgent())
        self.register_agent(DataStewardAgent())
        self.register_agent(StageDirectorAgent(hardware_controller))
        self.register_agent(HardwareControllerAgent(hardware_controller))
    
    def register_agent(self, agent: BaseAgent):
        """注册专家智能体"""
        self.agents[agent.name] = agent
    
    def unregister_agent(self, name: str):
        """注销专家"""
        if name in self.agents:
            del self.agents[name]
    
    def dispatch(self, task: AgentTask) -> Dict[str, str]:
        """
        任务分发：根据任务类型选择最合适的专家
        返回: {agent_name: result}
        """
        # 任务路由映射
        routing_map = {
            "visual": ["视觉大师"],
            "data": ["数据管家"],
            "stage": ["舞台导演", "硬件控制器"],
            "hardware": ["硬件控制器"],
            "query": ["数据管家", "视觉大师"],  # 查询类可多专家
            "analysis": ["数据管家"],
            "creation": ["视觉大师"],
            "control": ["硬件控制器", "舞台导演"],
            "validation": ["数据管家"],  # 验证由数据管家负责
        }
        
        candidates = routing_map.get(task.type, list(self.agents.keys()))
        results = {}
        
        for agent_name in candidates:
            if agent_name in self.agents:
                agent = self.agents[agent_name]
                if agent.status == "idle":
                    try:
                        result = agent.process(task)
                        results[agent_name] = result
                        
                        # 发送完成消息
                        msg = AgentMessage(
                            from_agent=agent_name,
                            to_agent="coordinator",
                            type="response",
                            content=f"任务 {task.id} 完成",
                            timestamp=datetime.now().isoformat(),
                            task_id=task.id,
                        )
                        with self._lock:
                            self.message_bus.append(msg)
                    except Exception as e:
                        results[agent_name] = f"[ERROR] {agent_name} 处理失败: {e}"
                else:
                    results[agent_name] = f"[BUSY] {agent_name} 正忙，任务排队"
        
        task.status = "completed" if results else "failed"
        self.task_history.append(task)
        return results
    
    def collaborate(self, task_description: str, involved_agents: List[str], context: Dict) -> Dict[str, str]:
        """
        多智能体协作：多个专家共同完成一个复杂任务
        """
        task = AgentTask(
            id=f"collab_{int(time.time())}_{hash(task_description) % 10000}",
            type="query",
            description=task_description,
            context=context,
            priority=8,
        )
        
        results = {}
        # 第一阶段：各自专家处理
        for name in involved_agents:
            if name in self.agents:
                agent = self.agents[name]
                sub_task = AgentTask(
                    id=f"{task.id}_{name}",
                    type=agent.specialty,
                    description=f"[协作任务] {task_description}",
                    context=context,
                    priority=8,
                )
                results[name] = agent.process(sub_task)
        
        # 第二阶段：结果汇总（实际中可由 LLM 进行智能汇总）
        summary = f"## 协作任务结果汇总\n\n原始需求: {task_description}\n\n"
        for name, result in results.items():
            summary += f"### {name}\n{result}\n\n"
        
        results["_summary"] = summary
        return results
    
    def broadcast(self, from_agent: str, content: str, task_id: Optional[str] = None):
        """广播消息给所有智能体"""
        msg = AgentMessage(
            from_agent=from_agent,
            to_agent="broadcast",
            type="broadcast",
            content=content,
            timestamp=datetime.now().isoformat(),
            task_id=task_id,
        )
        with self._lock:
            self.message_bus.append(msg)
        for agent in self.agents.values():
            agent.receive_message(msg)
    
    def get_system_status(self) -> Dict:
        """获取所有智能体状态"""
        return {
            "agents": {
                name: {
                    "specialty": agent.specialty,
                    "status": agent.status,
                    "memory_size": len(agent.memory),
                    "pending_messages": len(agent._message_queue),
                }
                for name, agent in self.agents.items()
            },
            "total_tasks": len(self.task_history),
            "completed_tasks": len([t for t in self.task_history if t.status == "completed"]),
            "message_bus_size": len(self.message_bus),
        }
    
    def save_state(self):
        """保存协调器状态"""
        state_file = self.root / "config" / "multi_agent_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "agents": {name: {
                "specialty": a.specialty,
                "status": a.status,
                "memory_count": len(a.memory),
            } for name, a in self.agents.items()},
            "task_count": len(self.task_history),
            "saved_at": datetime.now().isoformat(),
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)


# 便捷接口：用户可以直接调用的函数

def quick_visual_task(coordinator: MultiAgentCoordinator, description: str, context: Dict = None) -> str:
    """快速视觉任务"""
    task = AgentTask(
        id=f"quick_{int(time.time())}",
        type="visual",
        description=description,
        context=context or {},
        priority=7,
    )
    results = coordinator.dispatch(task)
    return results.get("视觉大师", "视觉专家未响应")


def quick_data_task(coordinator: MultiAgentCoordinator, description: str, context: Dict = None) -> str:
    """快速数据任务"""
    task = AgentTask(
        id=f"quick_{int(time.time())}",
        type="data",
        description=description,
        context=context or {},
        priority=7,
    )
    results = coordinator.dispatch(task)
    return results.get("数据管家", "数据专家未响应")


def quick_stage_task(coordinator: MultiAgentCoordinator, description: str, context: Dict = None) -> str:
    """快速舞台任务"""
    task = AgentTask(
        id=f"quick_{int(time.time())}",
        type="stage",
        description=description,
        context=context or {},
        priority=9,
    )
    results = coordinator.dispatch(task)
    return results.get("舞台导演", "舞台专家未响应")


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        coord = MultiAgentCoordinator(Path(tmpdir))
        
        # 测试单任务分发
        print("=" * 60)
        print("测试: 视觉任务")
        print("=" * 60)
        result = quick_visual_task(coord, "制作一个关于AI的PPT")
        print(result)
        
        print("\n" + "=" * 60)
        print("测试: 数据任务")
        print("=" * 60)
        result = quick_data_task(coord, "分析销售数据表格")
        print(result)
        
        print("\n" + "=" * 60)
        print("测试: 多智能体协作")
        print("=" * 60)
        results = coord.collaborate(
            "设计一场科技发布会舞台",
            ["视觉大师", "舞台导演", "硬件控制器"],
            {"venue": "酒店宴会厅", "audience": 200},
        )
        print(results.get("_summary", "无汇总"))
        
        print("\n" + "=" * 60)
        print("系统状态")
        print("=" * 60)
        print(json.dumps(coord.get_system_status(), ensure_ascii=False, indent=2))
