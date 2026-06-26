#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 记忆学习模块（Phase 6 记忆引擎）
功能：操作录制 + 向量存储 + 知识检索与复用 + 强化学习反馈

设计理念（镜花缘）：
  1. 一切经历皆为记忆：操作、对话、视觉、知识，全部保存
  2. 向量化存储：语义检索，超越关键词匹配
  3. 录制回放：完整操作序列可录制、保存、复现
  4. 强化学习：根据执行反馈更新记忆权重（成功+1，失败-1）
  5. 上下文感知：当前任务自动检索相关历史记忆

记忆类型：
  action_record    — 操作序列（键鼠操作）
  voice_command    — 语音指令及意图
  vision_result    — 视觉分析结果
  knowledge        — 结构化知识（FAQ、配置、规则）
  conversation     — 对话记录
  feedback         — 用户反馈（好评/差评）

存储后端：
  - ChromaDB（主）：向量存储 + 语义检索
  - JSON 文件（降级）：纯文本存储，无向量检索

依赖：
  - chromadb>=0.5.0（向量数据库）
  - sentence-transformers>=2.5.0（生成嵌入，可选）

"""

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


@dataclass
class MemoryEntry:
    """记忆条目"""
    memory_id: str
    memory_type: str            # action_record, voice_command, vision_result, knowledge, conversation, feedback
    content: str                # 文本内容（人类可读）
    embedding: Optional[List[float]] = None  # 向量嵌入
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: float = 1.0          # 记忆权重（强化学习调整）
    access_count: int = 0       # 被检索次数

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["timestamp"] = datetime.fromtimestamp(self.timestamp).isoformat() if self.timestamp else None
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> "MemoryEntry":
        entry = cls(
            memory_id=data.get("memory_id", str(uuid.uuid4())),
            memory_type=data.get("memory_type", "unknown"),
            content=data.get("content", ""),
            embedding=data.get("embedding"),
            timestamp=data.get("timestamp", 0.0),
            metadata=data.get("metadata", {}),
            score=data.get("score", 1.0),
            access_count=data.get("access_count", 0),
        )
        if isinstance(entry.timestamp, str):
            try:
                entry.timestamp = datetime.fromisoformat(entry.timestamp).timestamp()
            except ValueError:
                entry.timestamp = 0.0
        return entry


@dataclass
class ActionRecord:
    """操作录制条目"""
    record_id: str
    sequence_name: str
    actions: List[Dict]           # 操作序列（JSON 格式）
    context: Dict[str, Any]     # 执行上下文（屏幕状态、语音指令等）
    success_rate: float = 0.0   # 成功率（0-1）
    replay_count: int = 0       # 回放次数
    created_at: float = 0.0
    last_replayed: Optional[float] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "ActionRecord":
        return cls(**data)


class MemoryModule:
    """
    记忆学习引擎

    核心职责：
      1. 记忆存储：所有操作、知识、对话持久化
      2. 向量检索：语义搜索，找到最相关的历史经验
      3. 录制回放：完整操作序列可录制、复现、编辑
      4. 强化学习：根据执行结果更新记忆权重
      5. 上下文注入：当前任务自动检索相关记忆，注入决策
    """

    def __init__(self, memory_config: Dict, root: Path, executor=None):
        self.config = memory_config or {}
        self.root = root
        self.executor = executor

        # 路径配置
        self.db_path = root / self.config.get("db_path", "knowledge/vector_db")
        self.records_path = root / self.config.get("records_path", "knowledge/action_records")
        self.knowledge_path = root / self.config.get("knowledge_path", "knowledge/entries.json")
        self.max_entries = self.config.get("max_entries", 10000)
        self.similarity_threshold = self.config.get("similarity_threshold", 0.75)

        # 后端状态
        self._chroma_client = None
        self._chroma_collection = None
        self._embedding_model = None
        self._entries: Dict[str, MemoryEntry] = {}
        self._records: Dict[str, ActionRecord] = {}

        # 初始化
        self._init_chromadb()
        self._load_entries()
        self._load_records()

    # ==================== 后端初始化 ====================

    def _init_chromadb(self):
        """初始化 ChromaDB 向量数据库"""
        try:
            import chromadb
            self._chroma_client = chromadb.PersistentClient(path=str(self.db_path))
            self._chroma_collection = self._chroma_client.get_or_create_collection(
                name="lingshu_memory",
                metadata={"hnsw:space": "cosine"},
            )
            print(f"[Memory] ✅ ChromaDB 已初始化: {self.db_path}")
        except ImportError:
            print("[Memory] ⚠️ ChromaDB 未安装，降级为 JSON 文件存储")
            self._chroma_client = None

    def _init_embedding_model(self):
        """懒加载嵌入模型"""
        if self._embedding_model is not None:
            return True
        try:
            from sentence_transformers import SentenceTransformer
            model_name = self.config.get("embedding_model", "all-MiniLM-L6-v2")
            self._embedding_model = SentenceTransformer(model_name)
            print(f"[Memory] ✅ 嵌入模型已加载: {model_name}")
            return True
        except ImportError:
            print("[Memory] ⚠️ sentence-transformers 未安装，使用简单文本匹配")
            return False

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """获取文本嵌入向量"""
        if not self._init_embedding_model():
            return None
        try:
            embedding = self._embedding_model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            print(f"[Memory] 嵌入生成失败: {e}")
            return None

    # ==================== 加载/保存 ====================

    def _load_entries(self):
        """从 JSON 加载记忆条目"""
        if self.knowledge_path.exists():
            try:
                with open(self.knowledge_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data:
                    entry = MemoryEntry.from_dict(item)
                    self._entries[entry.memory_id] = entry
                print(f"[Memory] 已加载 {len(self._entries)} 条记忆")
            except Exception as e:
                print(f"[Memory] 加载记忆失败: {e}")

    def _save_entries(self):
        """保存记忆条目到 JSON"""
        self.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = [e.to_dict() for e in self._entries.values()]
            with open(self.knowledge_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Memory] 保存记忆失败: {e}")

    def _load_records(self):
        """加载操作录制"""
        if self.records_path.exists():
            for file in self.records_path.glob("*.json"):
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    record = ActionRecord.from_dict(data)
                    self._records[record.record_id] = record
                except Exception as e:
                    print(f"[Memory] 加载录制失败 {file}: {e}")
            print(f"[Memory] 已加载 {len(self._records)} 个操作录制")

    def _save_record(self, record: ActionRecord):
        """保存操作录制"""
        self.records_path.mkdir(parents=True, exist_ok=True)
        file_path = self.records_path / f"{record.record_id}.json"
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Memory] 保存录制失败: {e}")

    # ==================== 核心存储 ====================

    def store(
        self,
        content: str,
        memory_type: str = "knowledge",
        metadata: Optional[Dict] = None,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """
        存储记忆

        Args:
            content: 文本内容
            memory_type: 记忆类型
            metadata: 元数据
            embedding: 预计算嵌入（None 则自动计算）

        Returns:
            memory_id: 记忆 ID
        """
        memory_id = str(uuid.uuid4())

        # 生成嵌入
        if embedding is None:
            embedding = self._get_embedding(content)

        entry = MemoryEntry(
            memory_id=memory_id,
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            timestamp=time.time(),
            metadata=metadata or {},
            score=1.0,
            access_count=0,
        )

        self._entries[memory_id] = entry

        # 存储到 ChromaDB
        if self._chroma_collection and embedding:
            try:
                self._chroma_collection.add(
                    ids=[memory_id],
                    embeddings=[embedding],
                    documents=[content],
                    metadatas=[{
                        "memory_type": memory_type,
                        "timestamp": entry.timestamp,
                        **(metadata or {}),
                    }],
                )
            except Exception as e:
                print(f"[Memory] ChromaDB 存储失败: {e}")

        # 保存到 JSON
        self._save_entries()

        # 限制条目数量
        self._trim_entries()

        print(f"[Memory] 💾 记忆已存储 [{memory_type}] {content[:50]}...")
        return memory_id

    def store_action_record(
        self,
        sequence_name: str,
        actions: List[Dict],
        context: Optional[Dict] = None,
        success: bool = True,
    ) -> str:
        """
        存储操作录制

        Args:
            sequence_name: 录制名称
            actions: 操作序列（JSON 格式）
            context: 执行上下文
            success: 是否成功

        Returns:
            record_id: 录制 ID
        """
        record_id = str(uuid.uuid4())
        record = ActionRecord(
            record_id=record_id,
            sequence_name=sequence_name,
            actions=actions,
            context=context or {},
            success_rate=1.0 if success else 0.0,
            replay_count=0,
            created_at=time.time(),
        )
        self._records[record_id] = record
        self._save_record(record)

        # 同时存储为记忆（用于检索）
        content = f"操作录制: {sequence_name}\n" + json.dumps(actions, ensure_ascii=False, indent=2)[:500]
        self.store(content, memory_type="action_record", metadata={"record_id": record_id, "success": success})

        print(f"[Memory] 📼 操作录制已保存: {sequence_name} ({len(actions)} 个操作)")
        return record_id

    # ==================== 检索 ====================

    def search(self, query: str, memory_type: Optional[str] = None, top_k: int = 5) -> List[Dict]:
        """
        语义检索记忆

        Args:
            query: 查询文本
            memory_type: 过滤记忆类型（None=全部）
            top_k: 返回数量

        Returns:
            匹配的记忆列表（含相似度分数）
        """
        results = []

        # 1. ChromaDB 向量检索
        if self._chroma_collection:
            try:
                embedding = self._get_embedding(query)
                if embedding:
                    where = {"memory_type": memory_type} if memory_type else None
                    chroma_results = self._chroma_collection.query(
                        query_embeddings=[embedding],
                        n_results=min(top_k * 2, 50),
                        where=where,
                    )

                    for i, memory_id in enumerate(chroma_results["ids"][0]):
                        distance = chroma_results["distances"][0][i]
                        similarity = 1.0 - distance  # cosine distance -> similarity
                        if similarity >= self.similarity_threshold:
                            entry = self._entries.get(memory_id)
                            if entry:
                                entry.access_count += 1
                                results.append({
                                    "memory_id": memory_id,
                                    "memory_type": entry.memory_type,
                                    "content": entry.content,
                                    "similarity": similarity,
                                    "score": entry.score,
                                    "metadata": entry.metadata,
                                    "timestamp": datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                                })
            except Exception as e:
                print(f"[Memory] ChromaDB 检索失败: {e}")

        # 2. 降级：简单文本匹配（ChromaDB 不可用时）
        if not results and self._entries:
            query_lower = query.lower()
            for entry in self._entries.values():
                if memory_type and entry.memory_type != memory_type:
                    continue
                # 简单匹配：关键词重叠
                entry_words = set(entry.content.lower().split())
                query_words = set(query_lower.split())
                overlap = len(entry_words & query_words)
                if overlap > 0:
                    similarity = overlap / len(query_words) if query_words else 0
                    if similarity >= 0.3:  # 较低阈值
                        entry.access_count += 1
                        results.append({
                            "memory_id": entry.memory_id,
                            "memory_type": entry.memory_type,
                            "content": entry.content,
                            "similarity": similarity,
                            "score": entry.score,
                            "metadata": entry.metadata,
                            "timestamp": datetime.fromtimestamp(entry.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                        })

        # 排序：相似度 * 分数
        results.sort(key=lambda x: x["similarity"] * x["score"], reverse=True)
        return results[:top_k]

    def get_context(self, current_task: str, memory_type: Optional[str] = None, top_k: int = 3) -> str:
        """
        获取相关上下文（用于当前任务决策）

        返回格式化的上下文文本，可注入 LLM 提示词。
        """
        results = self.search(current_task, memory_type=memory_type, top_k=top_k)
        if not results:
            return ""

        context_parts = ["## 相关历史记忆"]
        for i, r in enumerate(results, 1):
            context_parts.append(f"{i}. [{r['memory_type']}] {r['content'][:200]}... (相似度: {r['similarity']:.2f})")

        return "\n".join(context_parts)

    # ==================== 录制回放 ====================

    def get_record(self, record_id: str) -> Optional[ActionRecord]:
        """获取操作录制"""
        return self._records.get(record_id)

    def list_records(self) -> List[Dict]:
        """列出所有操作录制"""
        return [
            {
                "record_id": r.record_id,
                "sequence_name": r.sequence_name,
                "action_count": len(r.actions),
                "success_rate": r.success_rate,
                "replay_count": r.replay_count,
                "created_at": datetime.fromtimestamp(r.created_at).strftime("%Y-%m-%d %H:%M:%S"),
            }
            for r in self._records.values()
        ]

    def replay_record(self, record_id: str, executor=None, auto_confirm: bool = False) -> bool:
        """
        回放操作录制

        Args:
            record_id: 录制 ID
            executor: 执行模块（None 则使用 self.executor）
            auto_confirm: 是否自动确认（跳过安全确认）

        Returns:
            是否成功回放
        """
        record = self._records.get(record_id)
        if not record:
            print(f"[Memory] ❌ 录制不存在: {record_id}")
            return False

        exec_module = executor or self.executor
        if not exec_module:
            print("[Memory] ❌ 无执行模块，无法回放")
            return False

        from core.executor import ExecutorAction, ActionType

        print(f"[Memory] ▶️ 回放操作录制: {record.sequence_name} ({len(record.actions)} 个操作)")

        actions = []
        for a in record.actions:
            action_type_str = a.get("action_type", "")
            try:
                action_type = ActionType[action_type_str]
            except KeyError:
                print(f"[Memory] ⚠️ 未知操作类型: {action_type_str}")
                continue

            actions.append(ExecutorAction(
                action_type=action_type,
                params=a.get("params", {}),
                timestamp=time.time(),
                description=a.get("description", f"回放: {action_type_str}"),
            ))

        success_count, fail_count = exec_module.execute_sequence(
            actions,
            sequence_name=f"replay_{record.sequence_name}",
            auto_confirm=auto_confirm,
        )

        success = fail_count == 0
        record.replay_count += 1
        record.last_replayed = time.time()
        # 更新成功率（指数移动平均）
        alpha = 0.3
        record.success_rate = (1 - alpha) * record.success_rate + alpha * (1.0 if success else 0.0)
        self._save_record(record)

        print(f"[Memory] ✅ 回放完成: 成功 {success_count}, 失败 {fail_count}, 成功率: {record.success_rate:.1%}")
        return success

    def delete_record(self, record_id: str) -> bool:
        """删除操作录制"""
        if record_id in self._records:
            del self._records[record_id]
            file_path = self.records_path / f"{record_id}.json"
            if file_path.exists():
                file_path.unlink()
            return True
        return False

    # ==================== 强化学习反馈 ====================

    def feedback(self, memory_id: str, success: bool, feedback_text: Optional[str] = None):
        """
        更新记忆权重（强化学习）

        Args:
            memory_id: 记忆 ID
            success: 是否成功
            feedback_text: 用户反馈文本（可选）
        """
        entry = self._entries.get(memory_id)
        if not entry:
            print(f"[Memory] ⚠️ 记忆不存在: {memory_id}")
            return

        # 更新分数（成功 +0.1，失败 -0.2）
        if success:
            entry.score = min(2.0, entry.score + 0.1)
        else:
            entry.score = max(0.1, entry.score - 0.2)

        # 存储反馈
        if feedback_text:
            self.store(
                content=feedback_text,
                memory_type="feedback",
                metadata={"target_memory": memory_id, "success": success},
            )

        # 更新 ChromaDB
        if self._chroma_collection:
            try:
                self._chroma_collection.update(
                    ids=[memory_id],
                    metadatas=[{"score": entry.score, **entry.metadata}],
                )
            except Exception as e:
                print(f"[Memory] ChromaDB 更新失败: {e}")

        self._save_entries()
        print(f"[Memory] 📊 记忆反馈 [{memory_id}]: {'✅' if success else '❌'} 分数: {entry.score:.2f}")

    # ==================== 便捷方法 ====================

    def store_knowledge(self, content: str, tags: Optional[List[str]] = None) -> str:
        """存储知识"""
        return self.store(content, memory_type="knowledge", metadata={"tags": tags or []})

    def store_conversation(self, user_message: str, assistant_response: str, metadata: Optional[Dict] = None) -> str:
        """存储对话"""
        content = f"用户: {user_message}\n灵枢: {assistant_response}"
        return self.store(content, memory_type="conversation", metadata=metadata)

    def store_feedback(self, content: str, success: bool, target_memory_id: Optional[str] = None) -> str:
        """存储用户反馈"""
        return self.store(
            content=content,
            memory_type="feedback",
            metadata={"success": success, "target_memory": target_memory_id},
        )

    def get_memory(self, memory_id: str) -> Optional[Dict]:
        """获取记忆详情"""
        entry = self._entries.get(memory_id)
        if entry:
            return entry.to_dict()
        return None

    def delete_memory(self, memory_id: str) -> bool:
        """删除记忆"""
        if memory_id in self._entries:
            del self._entries[memory_id]
            self._save_entries()

            if self._chroma_collection:
                try:
                    self._chroma_collection.delete(ids=[memory_id])
                except Exception as e:
                    print(f"[Memory] ChromaDB 删除失败: {e}")
            return True
        return False

    def list_memories(self, memory_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """列出记忆"""
        entries = self._entries.values()
        if memory_type:
            entries = [e for e in entries if e.memory_type == memory_type]
        entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)
        return [e.to_dict() for e in entries[:limit]]

    def get_stats(self) -> Dict:
        """获取记忆统计"""
        types = {}
        for e in self._entries.values():
            types[e.memory_type] = types.get(e.memory_type, 0) + 1

        return {
            "total_entries": len(self._entries),
            "total_records": len(self._records),
            "type_distribution": types,
            "avg_score": sum(e.score for e in self._entries.values()) / len(self._entries) if self._entries else 0,
            "chromadb_ready": self._chroma_client is not None,
            "embedding_ready": self._embedding_model is not None,
        }

    # ==================== 内部工具 ====================

    def _trim_entries(self):
        """限制条目数量，删除低分旧条目"""
        if len(self._entries) <= self.max_entries:
            return

        # 按分数 * 时间加权排序，删除低分旧条目
        entries_list = list(self._entries.values())
        entries_list.sort(key=lambda e: e.score * (1 + e.access_count * 0.1), reverse=True)
        keep_ids = {e.memory_id for e in entries_list[:self.max_entries]}

        removed = 0
        for mid in list(self._entries.keys()):
            if mid not in keep_ids:
                del self._entries[mid]
                if self._chroma_collection:
                    try:
                        self._chroma_collection.delete(ids=[mid])
                    except Exception:
                        pass
                removed += 1

        if removed > 0:
            self._save_entries()
            print(f"[Memory] 🗑️ 清理了 {removed} 条低分旧记忆")
