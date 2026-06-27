' 启动灵枢 Agent — 绕过 Windows Store Python 沙箱
' 自动检测可用的 Python 解释器

Dim wsh, fso, pythonExe, scriptPath, rootDir
Set wsh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' 定位项目根目录
rootDir = fso.GetParentFolderName(WScript.ScriptFullName)

' 候选 Python 路径（按优先级）
Dim candidates(5)
candidates(0) = rootDir & "\python\pythonw.exe"
candidates(1) = rootDir & "\python\python.exe"

' Kimi 托管 Python 运行时
candidates(2) = wsh.ExpandEnvironmentStrings("%USERPROFILE%") & _
    "\AppData\Roaming\kimi-desktop\daimon-share\daimon\runtime\python\.venv\Scripts\pythonw.exe"
candidates(3) = wsh.ExpandEnvironmentStrings("%USERPROFILE%") & _
    "\AppData\Roaming\kimi-desktop\daimon-share\daimon\runtime\python\.venv\Scripts\python.exe"

' 标准安装 Python
candidates(4) = "C:\Python312\pythonw.exe"
candidates(5) = "pythonw"

pythonExe = ""
For Each cand In candidates
    If fso.FileExists(cand) Then
        pythonExe = cand
        Exit For
    End If
Next

' 如果没找到，尝试 pythonw 命令
If pythonExe = "" Then
    Dim exec
    On Error Resume Next
    Set exec = wsh.Exec("pythonw --version")
    If Err.Number = 0 Then
        pythonExe = "pythonw"
    Else
        Set exec = wsh.Exec("python --version")
        If Err.Number = 0 Then
            pythonExe = "python"
        End If
    End If
    On Error GoTo 0
End If

' 如果还是找不到，报错
If pythonExe = "" Then
    MsgBox "无法找到可用的 Python 解释器！" & vbCrLf & vbCrLf & _
           "请安装 Python 3.9-3.12 标准版（非 Windows Store 版）" & vbCrLf & _
           "或下载便携版 Python 放在项目目录的 python/ 文件夹中。", _
           vbCritical, "灵枢启动失败"
    WScript.Quit 1
End If

' 启动 GUI 启动器
scriptPath = rootDir & "\gui_launcher.py"

' 使用 WScript.Shell 启动，隐藏窗口
Dim cmd
cmd = "cmd /c """ & pythonExe & """ """ & scriptPath & """"""

wsh.Run cmd, 1, False
