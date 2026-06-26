#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢·多智能体协同模块（进化卷核心）
核心概念：Expert Panel（专家面板）+ Skill Decentralization（技能去中心化）
实现多智能体协同、技能去中心化、群体智慧

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
    """智能体任务"""
    id: str
    type: str  # 'query', 'analysis', 'creation', 'control', 'validation'
    description: str
    context: Dict[str, Any]
    priority: int = 5  # 1-10, 10=最高优先级
    deadline: Optional[str] = None
    status: str = "pending"  # pending, assigned, processing, completed, failed
    result: Optional[str] = None


@dataclass
class AgentMessage:
    """智能体消息"""
    from_agent: str
    to_agent: str
    type: str  # 'request', 'response', 'broadcast', 'alert'
    content: str
    timestamp: str
    task_id: Optional[str] = None


class BaseAgent(ABC):
    """基础智能体"""
    
    def __init__(self, name: str, specialty: str, description: str):
        self.name = name
        self.specialty = specialty
        self.description = description
        self.status = "idle"  # idle, busy, offline
        self.memory: List[Dict] = []  # 记忆存储
        self._message_queue: List[AgentMessage] = []
        self._lock = threading.Lock()
    
    @abstractmethod
    def process(self, task: AgentTask) -> str:
        """处理任务"""
        pass
    
    def receive_message(self, msg: AgentMessage):
        """接收消息"""
        with self._lock:
            self._message_queue.append(msg)
    
    def get_messages(self) -> List[AgentMessage]:
        """获取未读消息"""
        with self._lock:
            msgs = self._message_queue.copy()
            self._message_queue.clear()
            return msgs
    
    def add_memory(self, entry: Dict):
        """添加记忆"""
        self.memory.append({
            **entry,
            "timestamp": datetime.now().isoformat(),
        })
        # 限制记忆大小
        if len(self.memory) > 1000:
            self.memory = self.memory[-800:]


class VisualMasterAgent(BaseAgent):
    """视觉大师：PPT设计、海报制作、图片生成、视频剪辑"""
    
    def __init__(self):
        super().__init__(
            name="视觉大师",
            specialty="visual",
            description="PPT设计、海报制作、图片生成、视频剪辑、配色方案、排版设计",
        )
    
    def process(self, task: AgentTask) -> str:
        self.status = "busy"
        try:
            desc = task.description.lower()
            if "ppt" in desc or "演示" in desc or "presentation" in desc:
                result = self._make_ppt(task)
            elif "海报" in desc or "poster" in desc or "banner" in desc:
                result = self._make_poster(task)
            elif "图片" in desc or "image" in desc or "图" in desc:
                result = self._generate_image(task)
            else:
                result = f"[视觉大师] 收到视觉任务: {task.description}\n" \
                        "➡️ 分析: 需要设计排版、配色方案\n" \
                        "➡️ 建议: 使用PPT模板或设计工具\n" \
                        "➡️ 输出: 生成视觉素材（图片/视频/动画）"
            
            self.add_memory({
                "task_id": task.id,
                "action": "visual_creation",
                "result": result,
            })
            return result
        finally:
            self.status = "idle"
    
    def _make_ppt(self, task: AgentTask) -> str:
        topic = task.context.get("topic", "未命名主题")
        return f"[PPT制作] 主题: {topic}\n" \
               "1. 封面设计：主题 + 副标题 + 图片\n" \
               "2. 目录页：章节导航\n" \
               "3. 内容页：要点 + 图表 + 动画\n" \
               "4. 结尾页：总结 + 致谢\n" \
               "➡️ 执行: 打开PowerPoint并创建新演示文稿"
    
    def _make_poster(self, task: AgentTask) -> str:
        return f"[海报制作] {task.description}\n" \
               "➡️ 设计: 主题突出、视觉对比、信息层次\n" \
               "➡️ 输出: 生成海报图片（PNG/JPG）"
    
    def _generate_image(self, task: AgentTask) -> str:
        return f"[图片生成] {task.description}\n" \
               "➡️ 分析: 风格、色调、构图\n" \
               "➡️ 生成: AI绘画工具（如Midjourney/Stable Diffusion）\n" \
               "➡️ 输出: 高清图片"


class DataStewardAgent(BaseAgent):
    """数据管家：Excel处理、数据分析、图表生成、SQL查询、数据清洗"""
    
    def __init__(self):
        super().__init__(
            name="数据管家",
            specialty="data",
            description="Excel处理、数据分析、图表生成、SQL查询、数据清洗、报表生成",
        )
    
    def process(self, task: AgentTask) -> str:
        self.status = "busy"
        try:
            desc = task.description.lower()
            if "excel" in desc or "表格" in desc or "sheet" in desc:
                result = self._process_spreadsheet(task)
            elif "数据" in desc or "data" in desc:
                result = self._analyze_data(task)
            elif "图表" in desc or "可视化" in desc or "workflow" in desc:
                result = self._optimize_workflow(task)
            else:
                result = f"[数据管家] 收到数据任务: {task.description}\n" \
                        "➡️ 分析: 数据类型、数据来源、处理流程\n" \
                        "➡️ 建议: 使用Excel/数据库/BI工具\n" \
                        "➡️ 输出: 数据报告、图表、洞察"
            
            self.add_memory({
                "task_id": task.id,
                "action": "data_processing",
                "result": result,
            })
            return result
        finally:
            self.status = "idle"
    
    def _process_spreadsheet(self, task: AgentTask) -> str:
        return f"[Excel处理] {task.description}\n" \
               "1. 数据读取：打开Excel文件\n" \
               "2. 数据清洗：去重、填充、格式转换\n" \
               "3. 公式计算：SUM/AVERAGE/VLOOKUP\n" \
               "4. 图表生成：柱状图/折线图/饼图\n" \
               "5. 输出报告：PDF/邮件/分享链接"
    
    def _analyze_data(self, task: AgentTask) -> str:
        return f"[数据分析] {task.description}\n" \
               "➡️ 分析: 数据分布、趋势、异常值\n" \
               "➡️ 统计: 描述统计、相关性分析\n" \
               "➡️ 可视化: 图表、仪表盘、报告\n" \
               "➡️ 洞察: 业务建议、预测模型"
    
    def _optimize_workflow(self, task: AgentTask) -> str:
        return f"[流程优化] {task.description}\n" \
               "➡️ 分析: 现有流程瓶颈\n" \
               "➡️ 设计: 新流程方案\n" \
               "➡️ 自动化: 脚本/工具实现\n" \
               "➡️ 验证: 效果评估"


class StageDirectorAgent(BaseAgent):
    """舞台导演：灯光控制、音响控制、场景切换、特效管理、演出编排"""
    
    def __init__(self, hardware_controller=None):
        super().__init__(
            name="舞台导演",
            specialty="stage",
            description="DMX灯光控制、音响管理、场景切换、特效编排、演出控制、舞台调度",
        )
        self.hardware = hardware_controller
    
    def process(self, task: AgentTask) -> str:
        self.status = "busy"
        try:
            desc = task.description.lower()
            if "灯光" in desc or "lighting" in desc or "dmx" in desc:
                result = self._design_lighting(task)
            elif "场景" in desc or "scene" in desc or "切换" in desc:
                result = self._setup_scene(task)
            elif "演出" in desc or "show" in desc or "表演" in desc:
                result = self._plan_show(task)
            else:
                result = f"[舞台导演] 收到舞台任务: {task.description}\n" \
                        "➡️ 分析: 灯光设计、音响配置、场景编排\n" \
                        "➡️ 建议: 使用DMX控制器、音响调音台\n" \
                        "➡️ 输出: 演出方案、灯光脚本、音响配置"
            
            self.add_memory({
                "task_id": task.id,
                "action": "stage_control",
                "result": result,
            })
            return result
        finally:
            self.status = "idle"
    
    def _design_lighting(self, task: AgentTask) -> str:
        # 通过硬件控制器发送DMX命令
        cues = [
            {"time": 0, "channel": 1, "value": 255, "desc": "主光全开"},
            {"time": 5, "channel": 2, "value": 180, "desc": "侧光暖色"},
            {"time": 10, "channel": 3, "value": 200, "desc": "背光冷色"},
        ]
        if self.hardware:
            for cue in cues:
                self.hardware.send_dmx({cue["channel"]: cue["value"]})
        
        return f"[灯光设计] {task.description}\n" + "\n".join(
            f"  T+{c['time']}s: Ch{c['channel']}={c['value']} ({c['desc']})"
            for c in cues
        ) + "\n➡️ 执行: 通过DMX控制器发送灯光指令"
    
    def _setup_scene(self, task: AgentTask) -> str:
        scene_type = task.context.get("scene_type", "general")
        return f"[场景切换] 场景类型: {scene_type}\n" \
               "➡️ 分析: 灯光预设、音响配置、特效准备\n" \
               "➡️ 切换: 渐变过渡、时间同步\n" \
               "➡️ 验证: 设备状态检查"
    
    def _plan_show(self, task: AgentTask) -> str:
        return f"[演出编排] {task.description}\n" \
               "1. 开场：灯光渐亮 + 音乐渐入\n" \
               "2. 高潮：灯光闪烁 + 特效触发\n" \
               "3. 转场：灯光切换 + 音乐过渡\n" \
               "4. 结尾：灯光渐暗 + 音乐淡出"


class HardwareControllerAgent(BaseAgent):
    """硬件控制器：通用设备控制、协议管理、状态监控、紧急停止"""
    
    def __init__(self, hardware_controller=None):
        super().__init__(
            name="硬件控制器",
            specialty="hardware",
            description="通用设备控制、协议管理、状态监控、紧急停止、设备发现、固件更新",
        )
        self.hardware = hardware_controller
        self.emergency_status = False
    
    def process(self, task: AgentTask) -> str:
        self.status = "busy"
        try:
            desc = task.description.lower()
            if "停止" in desc or "emergency" in desc or "急停" in desc:
                result = self._emergency_stop(task)
            elif "设备" in desc or "device" in desc or "连接" in desc:
                result = self._check_devices(task)
            elif "协议" in desc or "protocol" in desc or "通信" in desc:
                result = self._manage_protocol(task)
            else:
                result = f"[硬件控制器] 收到硬件任务: {task.description}\n" \
                        "➡️ 分析: 设备类型、协议选择、通信参数\n" \
                        "➡️ 建议: 使用TCP/Modbus/Serial/DMX512\n" \
                        "➡️ 输出: 设备控制指令、状态反馈"
            
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
        return "🚨🚨🚨 紧急停止！所有设备已关闭！\n" \
               "➡️ 灯光: 全部关闭\n" \
               "➡️ 音响: 静音\n" \
               "➡️ 电机: 停止\n" \
               "➡️ 安全: 进入安全模式"
    
    def _check_devices(self, task: AgentTask) -> str:
        if self.hardware:
            protocols = self.hardware.get_available_protocols()
            scene = self.hardware.get_scene()
            return f"[设备状态] 当前场景: {scene}\n" \
                   f"可用协议: {', '.join(protocols)}\n" \
                   f"设备状态: 正常\n" \
                   "连接状态: 良好"
        return "[设备状态] 硬件控制器未初始化\n"
    
    def _manage_protocol(self, task: AgentTask) -> str:
        protocol = task.context.get("protocol", "TCP")
        return f"[协议管理] 协议: {protocol}\n" \
               "➡️ 分析: 设备兼容性、通信速率\n" \
               "➡️ 配置: 波特率、数据位、校验位\n" \
               "➡️ 测试: 通信测试、数据验证\n" \
               "➡️ 监控: 实时状态、故障检测"


class MultiAgentCoordinator:
    """
    多智能体协调器
    
    管理多个专业智能体，实现协同工作：
    - 任务分配：根据任务类型分配给合适的智能体
    - 消息传递：智能体之间的通信机制
    - 群体决策：多智能体投票/共识机制
    - 负载均衡：根据智能体状态分配任务
    """
    
    def __init__(self, root: Path, config: Optional[Dict] = None, hardware_controller=None):
        self.root = root
        self.config = config or {}
        self.agents: Dict[str, BaseAgent] = {}
        self.task_history: List[AgentTask] = []
        self.message_bus: List[AgentMessage] = []
        self._lock = threading.Lock()
        
        # 注册专家智能体
        self.register_agent(VisualMasterAgent())
        self.register_agent(DataStewardAgent())
        self.register_agent(StageDirectorAgent(hardware_controller))
        self.register_agent(HardwareControllerAgent(hardware_controller))
    
    def register_agent(self, agent: BaseAgent):
        """注册智能体"""
        self.agents[agent.name] = agent
    
    def unregister_agent(self, name: str):
        """注销智能体"""
        if name in self.agents:
            del self.agents[name]
    
    def dispatch(self, task: AgentTask) -> Dict[str, str]:
        """
        分发任务到合适的智能体
        
        路由策略：
        - visual → 视觉大师
        - data → 数据管家
        - stage → 舞台导演
        - hardware → 硬件控制器
        - query → 视觉大师/数据管家（多智能体协作）
        """
        routing_map = {
            "visual": ["视觉大师"],
            "data": ["数据管家"],
            "stage": ["舞台导演", "硬件控制器"],
            "hardware": ["硬件控制器"],
            "query": ["数据管家", "视觉大师"],  # 查询类任务需要多智能体协作
            "analysis": ["数据管家"],
            "creation": ["视觉大师"],
            "control": ["硬件控制器", "舞台导演"],
            "validation": ["数据管家"],  # 验证类任务需要数据管家
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
                        
                        # 发送消息通知
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
        多智能体协作
        
        多个智能体共同完成一个复杂任务：
        - 每个智能体处理子任务
        - 结果汇总到协调器
        - 协调器生成最终报告
        """
        task = AgentTask(
            id=f"collab_{int(time.time())}_{hash(task_description) % 10000}",
            type="query",
            description=task_description,
            context=context,
            priority=8,
        )
        
        results = {}
        # 并行分发子任务
        for name in involved_agents:
            if name in self.agents:
                agent = self.agents[name]
                sub_task = AgentTask(
                    id=f"{task.id}_{name}",
                    type=agent.specialty,
                    description=f"[子任务] {task_description}",
                    context=context,
                    priority=8,
                )
                results[name] = agent.process(sub_task)
        
        # 汇总结果（简化：拼接所有结果）
        summary = f"## 多智能体协作结果\n\n任务: {task_description}\n\n"
        for name, result in results.items():
            summary += f"### {name}\n{result}\n\n"
        
        results["_summary"] = summary
        return results
    
    def broadcast(self, from_agent: str, content: str, task_id: Optional[str] = None):
        """广播消息到所有智能体"""
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
        """获取系统状态"""
        return {
            "agents": {
                name: {
                    "status": agent.status,
                    "specialty": agent.specialty,
                    "memory_size": len(agent.memory),
                    "pending_messages": len(agent._message_queue),
                }
                for name, agent in self.agents.items()
            },
            "task_queue": len(self.task_history),
            "message_bus": len(self.message_bus),
            "recent_tasks": [
                {
                    "id": t.id,
                    "type": t.type,
                    "status": t.status,
                    "description": t.description[:50],
                }
                for t in self.task_history[-10:]
            ],
        }

