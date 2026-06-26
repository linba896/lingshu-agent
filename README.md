# 灵枢（LingShu）Agent — 超级电脑元神

> **"灵枢在此，主上何令？"**

一个完全自包含、可移植的AI智能体运行时环境。插上U盘，双击启动——无需安装、无需联网、零侵入、零痕迹。

---

## 项目定位

| 属性 | 说明 |
|------|------|
| **名称** | 灵枢（LingShu） |
| **定位** | 悬浮于操作系统之上的"数字元神" |
| **交互方式** | 语音指令 → 屏幕理解 → 键鼠执行 |
| **核心特性** | 零安装、零依赖、即插即用 |
| **载体** | U盘（≥32GB，推荐64GB，USB 3.2 Gen2×2） |

---

## 快速启动

### Windows
插入U盘，双击 `start.bat`。

### macOS
插入U盘，双击 `start.command`（或终端执行 `./start.sh`）。

### Linux
```bash
./start.sh
```

---

## 项目结构

```
lingshu-agent/
├── start.bat              # Windows 启动器
├── start.sh               # Linux/macOS 启动器
├── start.command          # macOS 双击启动器
├── requirements.txt       # Python 依赖清单
├── config/
│   └── lingshu.yaml       # 主配置（模型路径、语音设备、安全级别）
├── core/                  # 核心模块
│   ├── launcher.py        # 启动器主入口
│   ├── asr.py             # 语音交互模块（ASR + NLU）
│   ├── vision.py          # 屏幕理解模块（VLM）
│   ├── executor.py        # 执行控制模块（键鼠模拟）
│   └── memory.py          # 学习与记忆模块（向量库）
├── models/                # 本地模型文件目录
│   ├── asr/               # 语音识别模型（Whisper-tiny 等）
│   ├── nlu/               # 意图理解模型（Qwen2.5-1.5B LoRA）
│   └── vlm/               # 视觉模型（Qwen3-VL-8B 等）
├── knowledge/             # 向量数据库（ChromaDB / SQLite-vec）
├── logs/                  # 运行日志
├── scripts/               # 工具脚本
│   ├── build_portable_env.py   # 构建离线便携环境
│   └── download_models.py      # 模型下载与量化脚本
└── tests/                 # 单元测试
```

---

## 开发路线图

| 阶段 | 任务 | 周期 | 状态 |
|------|------|------|------|
| **Phase 1** | 载体搭建：U盘环境、启动脚本、离线依赖 | 1-2周 | 🚧 进行中 |
| **Phase 2** | 语音模块：ASR + 意图理解 | 2-3周 | ⏳ 待启动 |
| **Phase 3** | 视觉模块：屏幕截图 + VLM | 3-4周 | ⏳ 待启动 |
| **Phase 4** | 执行模块：键鼠模拟 + 安全确认 | 2-3周 | ⏳ 待启动 |
| **Phase 5** | 学习模块：录制回放 + 向量库 | 3-4周 | ⏳ 待启动 |
| **Phase 6** | 联调优化：量化压缩 + 速度优化 | 2-3周 | ⏳ 待启动 |

---

## 技术栈

| 模块 | 技术选型 | 模型/工具 |
|------|----------|-----------|
| 语音转文字 | ASR | Whisper-tiny / WeNet |
| 意图理解 | LLM + LoRA | Qwen2.5-1.5B / Phi-3 Mini |
| 屏幕理解 | VLM | Qwen3-VL-8B-Instruct |
| 键鼠执行 | 跨平台自动化 | pyauto-desktop / askui |
| 记忆存储 | 向量数据库 | ChromaDB / SQLite-vec |
| 知识录制 | 操作记录 | OpenAdapt 范式 |

---

## 免责声明

本项目仅供学习研究和技术探索。自动执行键鼠操作可能涉及系统安全风险，请在隔离环境或虚拟机中充分测试后再于生产环境使用。敏感操作均内置"不动根本咒"人工确认机制。

---

## 许可证

待定（参考上游依赖组件：Qwen3-VL Apache-2.0、UI-TARS 开源协议等）。

---

*项目代号：灵枢（LingShu）*  
*架构文档：《灵枢·造物志》*  
*启动时间：2026-06-26*
