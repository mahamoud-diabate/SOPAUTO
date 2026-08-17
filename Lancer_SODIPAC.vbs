Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
pyExe = "C:\Users\diaba\AppData\Local\Programs\Python\Python312\pythonw.exe"
If Not fso.FileExists(pyExe) Then
    pyExe = "pythonw"
End If
WshShell.CurrentDirectory = scriptDir
WshShell.Run """" & pyExe & """ """ & scriptDir & "\main.py""", 0, False
