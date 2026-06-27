' ============================================================
' 灵枢启动台 — 创建桌面快捷方式
' 用途：为 start_gui.vbs 创建带图标的桌面快捷方式
' ============================================================

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

Dim rootDir, desktopDir, shortcutPath, iconPath
rootDir = fso.GetParentFolderName(WScript.ScriptFullName)
desktopDir = WshShell.SpecialFolders("Desktop")

' 创建桌面快捷方式
shortcutPath = desktopDir & "\灵枢启动台.lnk"

Set shortcut = WshShell.CreateShortcut(shortcutPath)
shortcut.TargetPath = rootDir & "\start_gui.vbs"
shortcut.WorkingDirectory = rootDir
shortcut.IconLocation = "%SystemRoot%\System32\shell32.dll,14"
shortcut.Description = "☯ 灵枢 Agent 启动台 — 双击启动"
shortcut.WindowStyle = 7  ' 最小化运行

On Error Resume Next
shortcut.Save

If Err.Number = 0 Then
    WshShell.Popup "✅ 桌面快捷方式已创建！" & vbCrLf & vbCrLf & "快捷方式路径：" & shortcutPath, 3, "☯ 灵枢启动台", 64
Else
    WshShell.Popup "❌ 创建快捷方式失败：" & Err.Description, 5, "☯ 灵枢启动台", 16
End If

On Error GoTo 0
Set shortcut = Nothing
Set WshShell = Nothing
Set fso = Nothing
