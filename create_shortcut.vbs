' Create LingShu Agent desktop shortcut
' Right-click run as admin: WScript "create_shortcut.vbs"

Dim wsh, fso, desktop, shortcut, rootDir
Set wsh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

rootDir = fso.GetParentFolderName(WScript.ScriptFullName)
desktop = wsh.SpecialFolders("Desktop")

Set shortcut = wsh.CreateShortcut(desktop & "\LingShu Agent.lnk")

' Launch via WScript to minimize window
shortcut.TargetPath = "WScript.exe"
shortcut.Arguments = Chr(34) & rootDir & "\start_gui.vbs" & Chr(34)
shortcut.WorkingDirectory = rootDir
shortcut.Description = "LingShu Agent - Autonomous AI Agent System"

' Set icon if exists
iconPath = rootDir & "\icon.ico"
If fso.FileExists(iconPath) Then
    shortcut.IconLocation = iconPath
End If

shortcut.Save

MsgBox "Shortcut created on desktop!" & vbCrLf & vbCrLf & _
       "Name: LingShu Agent" & vbCrLf & _
       "Location: " & desktop, vbInformation, "Success
