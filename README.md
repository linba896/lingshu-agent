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

**推荐：使用GUI启动器（紫色黑洞动画界面）**

1. 插入 U 盘，双击桌面上的 **LingShu Agent** 快捷方式（或运行 `start_gui.bat`）
2. 欣赏 3 秒紫色黑洞动画启动画面
3. 进入主界面后，点击 **LAUNCH AGENT** 启动灵枢

**功能按钮：**
- **LAUNCH AGENT** — 启动灵枢核心
- **LEARNING ENGINE** — 让灵枢学习并掌握任何软件（Photoshop、VS Code、Excel 等）
- **SETTINGS** — 配置语音、安全、模块参数
- **DOCUMENTATION** — 打开 README 文档
- **ABOUT** — 关于灵枢

**系统托盘：** 关闭窗口后灵枢最小化到系统托盘，右键图标可显示/退出

**纯命令行启动：**
```powershell
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

## 图标定制

灵枢启动器支持自定义图标：

1. 将你的图标图片放入 `assets/icon_source.jpg`（或 .png）
2. 运行 `python generate_icon.py` 生成 `icon.ico`
3. 运行 `create_shortcut.vbs` 更新桌面快捷方式

当前默认图标是一个紫色黑洞漩涡，启动时会显示旋转动画效果。

---