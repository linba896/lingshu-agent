' Launch LingShu Agent - bypass Windows Store Python sandbox
' Auto-detect available Python interpreter

Dim wsh, fso, pythonExe, scriptPath, rootDir
Set wsh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

' Locate project root directory
rootDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Candidate Python paths (priority order)
Dim candidates(5)
candidates(0) = rootDir & "\python\pythonw.exe"
candidates(1) = rootDir & "\python\python.exe"

' Kimi managed Python runtime
candidates(2) = wsh.ExpandEnvironmentStrings("%USERPROFILE%") & _
    "\AppData\Roaming\kimi-desktop\daimon-share\daimon\runtime\python\.venv\Scripts\pythonw.exe"
candidates(3) = wsh.ExpandEnvironmentStrings("%USERPROFILE%") & _
    "\AppData\Roaming\kimi-desktop\daimon-share\daimon\runtime\python\.venv\Scripts\python.exe"

' Standard Python installation
candidates(4) = "C:\Python312\pythonw.exe"
candidates(5) = "pythonw"

pythonExe = ""
For Each cand In candidates
    If fso.FileExists(cand) Then
        pythonExe = cand
        Exit For
    End If
Next

' If not found, try pythonw command
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

' Still not found, show error
If pythonExe = "" Then
    MsgBox "Cannot find available Python interpreter!" & vbCrLf & vbCrLf & _
           "Please install Python 3.9-3.12 standard edition (not Windows Store)" & vbCrLf & _
           "Or download portable Python and place in python/ folder.", _
           vbCritical, "LingShu Launch Failed"
    WScript.Quit 1
End If

' Launch GUI launcher
scriptPath = rootDir & "\gui_launcher.py"

' Use WScript.Shell to launch, show window
Dim cmd
cmd = "cmd /c """ & pythonExe & """ """ & scriptPath & """"

wsh.Run cmd, 1, False
