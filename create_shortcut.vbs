' 创建灵枢 Agent 桌面快捷方式
' 右键管理员运行：WScript "create_shortcut.vbs"

Dim wsh, fso, desktop, shortcut, rootDir
Set wsh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

rootDir = fso.GetParentFolderName(WScript.ScriptFullName)
desktop = wsh.SpecialFolders("Desktop")

Set shortcut = wsh.CreateShortcut(desktop & "\灵枢 Agent ☯.lnk")

' 使用 WScript 启动，最小化窗口
shortcut.TargetPath = "WScript.exe"
shortcut.Arguments = Chr(34) & rootDir & "\start_gui.vbs" & Chr(34)
shortcut.WorkingDirectory = rootDir
shortcut.Description = "灵枢 Agent — 自主智能体系统"

' 尝试设置图标（如果存在）
iconPath = rootDir & "\icon.ico"
If fso.FileExists(iconPath) Then
    shortcut.IconLocation = iconPath
End If

shortcut.Save

MsgBox "快捷方式已创建到桌面！" & vbCrLf & vbCrLf & _
       "名称：灵枢 Agent ☯" & vbCrLf & _
       "位置：" & desktop, vbInformation, "创建成功"
