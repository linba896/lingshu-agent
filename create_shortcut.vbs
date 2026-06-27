Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

RootPath = fso.GetParentFolderName(WScript.ScriptFullName)
If Right(RootPath, 1) <> "\" Then
    RootPath = RootPath & "\"
End If

DesktopPath = WshShell.SpecialFolders("Desktop")
LinkPath = DesktopPath & "\LingShu Agent.lnk"

Set oLink = WshShell.CreateShortcut(LinkPath)
oLink.TargetPath = RootPath & "start_gui.bat"
oLink.WorkingDirectory = RootPath
oLink.IconLocation = RootPath & "icon.ico"
oLink.Description = "LingShu Agent - AI Digital Avatar"
oLink.WindowStyle = 1
oLink.Save

WScript.Echo "Shortcut created!"
