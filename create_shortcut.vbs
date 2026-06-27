Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

RootPath = fso.GetParentFolderName(WScript.ScriptFullName)
If Right(RootPath, 1) <> "\" Then
    RootPath = RootPath & "\"
End If

' Delete old shortcut if exists
DesktopPath = WshShell.SpecialFolders("Desktop")
LinkPath = DesktopPath & "\LingShu Agent.lnk"
If fso.FileExists(LinkPath) Then
    fso.DeleteFile(LinkPath)
End If

' Create shortcut with English paths (avoids Chinese encoding issues)
Set oLink = WshShell.CreateShortcut(LinkPath)

' Use English path wrapper to avoid Windows Chinese path bugs
oLink.TargetPath = "D:\LingShuStart.bat"
oLink.WorkingDirectory = "D:\"
oLink.IconLocation = "D:\icon.ico"
oLink.Description = "LingShu Agent - AI Digital Avatar"
oLink.WindowStyle = 1
oLink.Save

WScript.Echo "Shortcut created!"
