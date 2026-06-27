# 灵枢（LingShu）Agent — v3.0.0

> **"灵枢所辖，万物听令；心有灵犀，无远弗届。"**
> **"三千世界，一念即达；万法归宗，灵枢为枢。"**

一个完全自包含、可移植的 AI 智能体运行时环境。插上 U 盘，双击启动——无需安装、无需联网、零侵入、零痕迹。

---

## 项目定位

| 属性 | 说明 |
|------|------|
| **名称** | 灵枢（LingShu） |
| **定位** | 悬浮于操作系统之上的"数字元神" |
| **交互方式** | 语音指令 → 屏幕理解 → 键鼠执行 |
| **核心特性** | 零安装、零依赖、即插即用、全模块化 |
| **载体** | U 盘（≥32GB，推荐 64GB，USB 3.2 Gen2×2） |
| **版本** | v3.0.0（完全体） |

---

## 快速启动

### Windows
    插入 U 盘，双击 `start_gui.bat`（带 GUI 启动）或 `start.bat`（纯命令行）。

```powershell
# 或命令行启动
python core\launcher.py
```

### macOS
插入 U 盘，双击 `start.command`（或终端执行 `./start.sh`）。

```bash
# 或终端启动
python core/launcher.py
```

### Linux
```bash
./start.sh
# 或
python core/launcher.py
```

---

## 项目结构

```
lingshu-agent/
├── gui_launcher.py           # VS Code 风格 GUI 启动器（tkinter + 多面板 + 标签页 + 终端）
├── start_gui.bat             # Windows GUI 启动脚本
├── start_gui.vbs             # Windows 静默启动（无命令行窗口）
├── create_shortcut.vbs       # 创建桌面快捷方式脚本
├── start.bat                 # Windows 启动器
├── start.sh                  # Linux/macOS 启动器
├── start.command             # macOS 双击启动器
├── requirements.txt          # Python 依赖清单
├── config/
│   ├── lingshu.yaml          # 主配置（模型路径、语音设备、安全级别、权限分级）
│   ├── speaker_profiles/     # 声纹档案（JSON 加密）
│   └── auth/                 # 授权状态 + 审计日志
├── core/                     # 核心模块（17 个）
│   ├── launcher.py           # 启动器主入口（v3.0，极速启动模式 + 延迟加载）
│   ├── monitor.py            # 系统监控（CPU/内存/磁盘预警）
│   ├── asr.py                # 语音交互（VAD + Whisper ASR + NLU 意图）
│   ├── speaker.py            # 声纹验证（MFCC + 多用户 + 访客模式）
│   ├── auth.py               # 授权管理（3 级权限 + 弹窗授权 + 审计日志 + 撤销回滚）
│   ├── gui.py                # 可视化面板（Gradio 灵枢台 + 状态指示 + 快捷操作）
│   ├── proactive.py          # 主动服务（预测维护 + 上下文感知 + 智能日程）
│   ├── hardware.py           # 硬件控制（TCP/IP/MQTT/Modbus/Serial/DMX512 + 场景模式）
│   ├── evolution.py          # 自我进化（SEAgent + AgentEvolver，技能压缩/嫁接/自然选择）
│   ├── multi_agent.py        # 多智能体协同（视觉大师/数据管家/舞台导演/硬件控制器）
│   ├── vision.py             # 视觉理解（截图 + VLM + 元素定位 + 视觉指代解析）
│   ├── executor.py           # 执行控制（键鼠模拟 + 安全确认 + 操作回滚 + 跨分辨率）
│   ├── memory.py             # 记忆学习（录制回放 + ChromaDB 向量检索 + 强化学习反馈）
│   ├── digital_twin.py       # 数字孪生（操作预演/风险模拟/沙箱环境）
│   ├── software_learner.py   # 软件学习引擎（文件分析 + 操作录制 + 自主学习 + 权限授予）
│   ├── plugin_system.py      # 插件系统（动态加载 + 沙箱隔离 + 热重载 + 权限控制）
│   ├── update_manager.py     # 更新管理器（GitHub Releases + 原子更新 + 自动回滚）
│   ├── logger.py             # 结构化日志（异步 + 脱敏 + 日志轮转 + 上下文追踪）
│   ├── security.py           # 安全模块（AES-256 + 签名验证 + 凭据保险箱 + 输入消毒）
│   ├── backup.py             # 备份系统（全量/增量 + 自动调度 + 加密 + 验证）
│   ├── scheduler.py          # 任务调度器（定时/间隔/延迟 + 优先级 + 重试 + 依赖链）
│   └── metrics.py            # 性能监控（实时采集 + 告警 + 追踪 + 基准测试 + 报告）
├── models/                   # 本地模型文件
│   ├── asr/whisper-tiny/     # 语音识别（faster-whisper）
│   ├── nlu/qwen2.5-1.5b/     # 意图理解（Qwen2.5-1.5B-Instruct）
│   ├── vlm/qwen3-vl-8b/      # 视觉语言（Qwen3-VL-8B-Instruct）
│   └── speaker/ecapa-tdnn/   # 声纹模型（备选，轻量 MFCC 为主）
├── knowledge/                # 向量数据库（ChromaDB）+ 知识条目
├── logs/                     # 运行日志 + 截图存档
├── scripts/                  # 工具脚本
│   ├── build_portable_env.py # 构建离线便携环境（Python 嵌入版 + wheels）
│   ├── download_models.py    # 模型下载（HuggingFace/ModelScope）
│   ├── quantize_models.py    # 模型量化（INT8/INT4/FP8）
│   ├── optimize.py           # 性能优化（预热 + 缓存 + 资源监控）
│   └── port_check.py         # 端口检测 + 备用端口分配
└── tests/                    # 单元测试
    ├── test_asr.py           # 语音模块测试
    ├── test_auth.py          # 授权管理测试
    ├── test_speaker.py       # 声纹验证测试
    ├── test_executor.py      # 执行模块测试
    ├── test_vision.py        # 视觉模块测试
    ├── test_memory.py        # 记忆模块测试
    ├── test_hardware.py      # 硬件控制测试
    ├── test_digital_twin.py  # 数字孪生测试
    ├── test_evolution.py     # 进化系统测试
    ├── test_multi_agent.py   # 多智能体测试
    ├── test_plugin_system.py # 插件系统测试
    ├── test_scheduler.py     # 任务调度器测试
    ├── test_security.py      # 安全模块测试
    ├── test_backup.py        # 备份系统测试
    ├── test_metrics.py       # 性能监控测试
    └── test_update_manager.py # 更新管理器测试
```

---

## 开发路线图

| 阶段 | 任务 | 核心模块 | 状态 |
|------|------|----------|------|
| **Phase 1** | 载体搭建：U 盘环境、启动脚本、离线依赖 | `launcher.py`, `monitor.py`, `build_portable_env.py` | ✅ 已完成 |
| **Phase 2** | 语音模块：ASR + NLU + VAD + 唤醒词 | `asr.py` (VADRecorder + WhisperASR + NLUProcessor) | ✅ 已完成 |
| **Phase 2.5** | 增补卷：声纹锁 + 授权控制 + GUI + 硬件 | `speaker.py`, `auth.py`, `gui.py`, `hardware.py` | ✅ 已完成 |
| **Phase 3** | 进化卷：主动服务 + 自我进化 + 多智能体 | `proactive.py`, `evolution.py`, `multi_agent.py` | ✅ 已完成 |
| **Phase 4** | 视觉模块：屏幕截图 + VLM + 视觉任务理解 | `vision.py` (mss/Pillow + Qwen3-VL-8B + 降级 OCR) | ✅ 已完成 |
| **Phase 5** | 执行模块：键鼠模拟 + 安全确认 + 操作回滚 | `executor.py` (pyautogui + 3 级安全 + undo/redo) | ✅ 已完成 |
| **Phase 6** | 记忆学习：录制回放 + 向量库 + 知识积累 | `memory.py` (ChromaDB + sentence-transformers + RL) | ✅ 已完成 |
| **Phase 8** | 数字孪生：操作预演 + 风险模拟 + 沙箱环境 | `digital_twin.py` (风险评分 + 效果预测 + 报告) | ✅ 已完成 |
| **Phase 9** | 软件学习：文件分析 + 操作录制 + 自主学习 | `software_learner.py` (文件树 + 操作序列 + 权限开关) | ✅ 已完成 |
| **Phase 10** | 插件系统：动态扩展 + 沙箱隔离 + 热重载 | `plugin_system.py` (manifest + sandbox + event bus) | ✅ 已完成 |
| **Phase 11** | 基础设施：日志 + 安全 + 备份 + 调度 + 监控 | `logger.py`, `security.py`, `backup.py`, `scheduler.py`, `metrics.py` | ✅ 已完成 |

---

## 技术栈

| 模块 | 技术选型 | 模型/工具 |
|------|----------|-----------|
| 语音转文字 | ASR | faster-whisper / Whisper-tiny (VAD + 流式录音) |
| 意图理解 | LLM + 规则回退 | Qwen2.5-1.5B-Instruct / 正则解析 |
| 声纹验证 | MFCC + 余弦相似度 | librosa + scikit-learn（轻量无需商用 SDK） |
| 屏幕理解 | VLM | Qwen3-VL-8B-Instruct (INT8/INT4 量化) |
| 键鼠执行 | 跨平台自动化 | pyautogui (FAILSAFE + 跨分辨率缩放) |
| 记忆存储 | 向量数据库 | ChromaDB + sentence-transformers (all-MiniLM-L6-v2) |
| 知识录制 | 操作记录 | 自定义操作序列 + 回放引擎 |
| 硬件控制 | 多协议 | TCP/IP + MQTT + Modbus + Serial + DMX512 |
| 自我进化 | 遗传算法 | 技能压缩/嫁接/突变/交叉 + 自然选择 |
| 多智能体 | 专家面板 | 视觉大师/数据管家/舞台导演/硬件控制器 |
| GUI 面板 | Web 界面 | Gradio 4.x (Dark 主题 + 实时日志 + 授权弹窗) |
| 数字孪生 | 风险模拟 | 操作预演 + 风险评分 + 替代方案 |
| 软件学习 | 自主学习 | 文件分析 + 操作录制 + 权限授予 |
| 插件系统 | 动态扩展 | Manifest + 沙箱 + 事件总线 + API 网关 |
| 日志系统 | 结构化记录 | 异步 + 脱敏 + 轮转 + 上下文追踪 |
| 安全模块 | 加密/签名 | AES-256 + HMAC + 凭据保险箱 + 输入消毒 |
| 备份系统 | 灾难恢复 | 全量/增量 + 自动调度 + 加密 + 验证 |
| 任务调度 | 定时执行 | Cron/间隔/延迟 + 优先级 + 重试 + 依赖链 |
| 性能监控 | 实时采集 | 系统指标 + 告警 + 分布式追踪 + 基准测试 |

---

## 核心架构

```
┌─────────────────────────────────────────────────────┐
│                   灵枢 Agent v3.0.0                  │
├─────────────────────────────────────────────────────┤
│  基础设施: logger → security → backup → scheduler → metrics │
├─────────────────────────────────────────────────────┤
│  扩展层: plugin_system (动态加载 + 沙箱 + 热重载)     │
│  更新层: update_manager (检查 + 下载 + 原子更新)     │
├─────────────────────────────────────────────────────┤
│  入口层: launcher.py (极速启动 + 延迟加载 + 生命周期)  │
│  GUI 层: gui_launcher.py (VS Code 风格 + 多面板)     │
├─────────────────────────────────────────────────────┤
│  感知层: voice (ASR+VAD) → vision (VLM+OCR)        │
│          ↓                    ↓                      │
│  理解层: speaker (声纹) → auth (权限) → nlu (意图) │
├─────────────────────────────────────────────────────┤
│  决策层: proactive (主动) → multi_agent (多智能体)  │
│          ↓                    ↓                      │
│  进化层: evolution (SEAgent + AgentEvolver)        │
├─────────────────────────────────────────────────────┤
│  执行层: executor (键鼠+安全+回滚) → hardware (硬件) │
│  模拟层: digital_twin (预演 + 风险 + 沙箱)          │
│  学习层: software_learner (文件分析 + 自主学习)    │
├─────────────────────────────────────────────────────┤
│  记忆层: memory (录制+向量+检索) → gui (Gradio面板)│
└─────────────────────────────────────────────────────┘
```

---

## 命令行交互（CLI）

启动后输入 `help` 查看所有命令：

| 命令 | 功能 |
|------|------|
| `status` | 查看系统状态 |
| `auth` / `revoke` | 授权 / 撤销授权 |
| `speaker` | 声纹管理（注册/验证/列表/删除） |
| `scene` | 切换硬件场景（computer/stage/hotel/meeting） |
| `listen` / `voice` / `text` | 语音录制 / 启动监听 / 停止监听 |
| `stt <秒>` | 录制 N 秒并转文字 |
| `nlu <文本>` | 测试意图理解 |
| `screenshot` | 截图保存到 logs/ |
| `look [问题]` | 截图 + VLM 分析屏幕 |
| `vision info` | 查看视觉模块状态 |
| `exec <操作>` | 执行键鼠操作（click/move/type/scroll/hotkey/shell） |
| `undo` / `redo` | 撤销 / 重做 |
| `exec status` / `exec history` | 执行模块状态 / 操作历史 |
| `memory <子命令>` | 记忆管理（search/store/list/record/replay/stats） |
| `software <子命令>` | 软件学习引擎（analyze/learn/record/permissions） |
| `twin <子命令>` | 数字孪生（simulate/verify/batch/report） |
| `plugin <子命令>` | 插件管理（list/load/enable/disable/uninstall） |
| `backup <子命令>` | 备份管理（create/restore/list/verify） |
| `schedule <子命令>` | 任务调度（add/remove/list/pause/resume） |
| `metrics <子命令>` | 性能监控（status/report/alerts） |
| `update <子命令>` | 更新管理（check/download/install/rollback） |
| `modules` | 查看已加载模块状态 |
| `config` | 查看当前配置 |
| `help` / `quit` | 帮助 / 退出 |

---

## 配置说明（config/lingshu.yaml）

```yaml
app:
  version: "3.0.0"
  log_level: INFO

plugin:
  enabled: true
  sandbox: true
  hot_reload: true
  max_plugins: 20

update:
  channel: stable  # stable / beta / dev / nightly
  auto_check: true
  check_interval_hours: 24
  auto_download: false
  auto_install: false

backup:
  auto_enabled: true
  interval_hours: 24
  max_backups: 10
  max_age_days: 30
  encrypt: true

scheduler:
  max_workers: 4
  persistence: true

metrics:
  enabled: true
  collection_interval: 5
  alert_thresholds:
    cpu_percent: { warning: 70, critical: 90 }
    memory_percent: { warning: 75, critical: 90 }
    disk_percent: { warning: 80, critical: 95 }

security:
  encryption: AES-256-GCM
  hash_algorithm: SHA-256
  max_auth_attempts: 5
  lockout_duration: 300

auth:
  permission_levels:
    level_1: [open, click, scroll, type, query]      # 基础权限
    level_2: [close, delete_file, modify_system_settings]  # 中级（需声纹）
    level_3: [format_disk, payment, network_config]   # 高级（需声纹+人脸）

speaker:
  verify_mode: strict   # strict / guest / off
  max_users: 10

gui:
  framework: gradio
  port: 7860
  theme: dark

proactive:
  enabled: true
  quiet_hours: [23, 7]  # 23:00-07:00 不推送建议

evolution:
  enabled: true
  reflection_interval: 3600  # 每小时反思一次

hardware:
  default_scene: computer
  protocols:
    tcp: { enabled: true }
    mqtt: { enabled: true, broker: "localhost", port: 1883 }
    modbus: { enabled: true }
    serial: { enabled: true }
    dmx512: { enabled: false }
```

---

## 安装依赖

### 有网络环境（开发/准备）

```bash
pip install -r requirements.txt

# 下载模型（国内用 ModelScope）
python scripts/download_models.py --model vlm --name qwen3-vl-8b --source modelscope

# 量化模型（减小体积）
python scripts/quantize_models.py --model-type nlu --quant-type int8 \
  --model-path models/nlu/qwen2.5-1.5b --output-path models/nlu/qwen2.5-1.5b-int8
```

### 离线环境（目标机器）

```bash
# 在有网络环境预先下载 wheels
python scripts/build_portable_env.py --root . --download

# 复制到 U 盘，在目标机器安装
python scripts/build_portable_env.py --root . --install
```

---

## 运行测试

```bash
pytest tests/ -v

# 或单独运行模块测试
pytest tests/test_asr.py -v
pytest tests/test_auth.py -v
pytest tests/test_executor.py -v
pytest tests/test_vision.py -v
pytest tests/test_memory.py -v
pytest tests/test_speaker.py -v
pytest tests/test_hardware.py -v
pytest tests/test_digital_twin.py -v
pytest tests/test_evolution.py -v
pytest tests/test_multi_agent.py -v
pytest tests/test_plugin_system.py -v
pytest tests/test_scheduler.py -v
pytest tests/test_security.py -v
pytest tests/test_backup.py -v
pytest tests/test_metrics.py -v
pytest tests/test_update_manager.py -v
```

---

## 安全机制（不动根本咒）

1. **首次授权**：启动时弹窗授权，生成加密状态文件到 U 盘
2. **三级权限**：
   - Level 1（基础）：文件浏览、网页搜索、程序启动
   - Level 2（中级）：文件修改、系统设置、程序控制（需声纹验证）
   - Level 3（高级）：格式化、支付、网络配置（需声纹+人脸双重验证）
3. **操作确认**：敏感操作弹窗/语音确认，30 秒超时自动取消
4. **操作回滚**：鼠标移动可撤销、键盘输入可删除、点击不可逆提示
5. **审计日志**：所有操作记录到 `config/auth/audit_log.jsonl`，不可篡改
6. **紧急停止**：Ctrl+C 或语音指令"停止"立即终止，FARLS 安全（鼠标移角落）
7. **访客模式**：未授权时仅允许基础操作
8. **插件沙箱**：第三方插件运行在受限环境，禁止危险操作
9. **输入消毒**：自动过滤 SQL 注入、XSS、命令注入等攻击
10. **凭据保险箱**：AES-256 加密存储敏感信息，支持密钥轮换
11. **自动备份**：更新前自动创建还原点，支持一键回滚
12. **性能告警**：CPU/内存/磁盘异常时自动告警，防止资源耗尽
13. **审计日志**：所有操作记录到结构化日志，支持查询和追踪

---

## 开发计划（未来）

| 版本 | 目标 | 功能 |
|------|------|------|
| v0.4.0 | 数字孪生 | 沙箱环境、预演模式、操作模拟 |
| v0.5.0 | 情感计算 | 情绪识别、语音语调分析、情感反馈 |
| v0.6.0 | 自适应学习 | 自动操作序列学习、强化学习优化 |
| v1.0.0 | 生产就绪 | 全平台测试、性能优化、安全审计 |
| v2.0.0 | 生态扩展 | 插件市场、社区贡献、第三方集成 |
| **v3.0.0** | **完全体** | **数字孪生 + 软件学习 + 插件系统 + 基础设施** |

---

## 免责声明

本项目仅供学习研究和技术探索。自动执行键鼠操作可能涉及系统安全风险，请在隔离环境或虚拟机中充分测试后再于生产环境使用。敏感操作均内置"不动根本咒"人工确认机制。使用硬件控制（MQTT/Modbus/DMX512）时请注意人身安全，演出场景务必配置紧急停止按钮。

---

## 许可证

待定（参考上游依赖组件：Qwen3-VL Apache-2.0、Whisper MIT、UI-TARS 开源协议等）。

---

*项目代号：灵枢（LingShu）*  
*架构文档：《灵枢·造物志》（白皮书 + 增补卷 + 进化卷）*  
*启动时间：2026-06-26*  
*当前版本：v3.0.0*
