' ============================================================
' 灵枢启动台 — 双击启动脚本（无黑窗口）
' 用途：Windows 双击直接打开 GUI，不显示命令行
' ============================================================

Set WshShell = CreateObject("WScript.Shell")

' 获取脚本所在目录（项目根目录）
Dim rootDir
rootDir = WshShell.CurrentDirectory

' 查找 Python 解释器
Dim pythonExe
pythonExe = ""

' 1. 优先使用 Kimi 托管 Python
If pythonExe = "" Then
    If WshShell.ExpandEnvironmentStrings("%KIMI_PYTHON%") <> "%KIMI_PYTHON%" Then
        pythonExe = WshShell.ExpandEnvironmentStrings("%KIMI_PYTHON%")
    End If
End If

' 2. 检查同目录 python/
If pythonExe = "" Then
    Dim fso
    Set fso = CreateObject("Scripting.FileSystemObject")
    If fso.FileExists(rootDir & "\python\python.exe") Then
        pythonExe = rootDir & "\python\python.exe"
    End If
End If

' 3. 检查常见 Python 安装路径
If pythonExe = "" Then
    If fso.FileExists(WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\python.exe") Then
        pythonExe = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%") & "\Programs\Python\Python312\python.exe"
    End If
End If

' 4. 回退到 PATH 中的 python
If pythonExe = "" Then
    pythonExe = "python"
End If

' 设置环境变量
WshShell.Environment("PROCESS")("PYTHONPATH") = rootDir

' 启动 GUI（0 = 隐藏窗口，不显示命令行）
WshShell.Run """" & pythonExe & """ """ & rootDir & "\gui_launcher.py""", 0, False

' 清理
Set WshShell = Nothing
Set fso = Nothing
