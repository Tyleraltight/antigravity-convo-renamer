Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

scriptsDir = fso.GetParentFolderName(WScript.ScriptFullName)
rootDir = fso.GetParentFolderName(scriptsDir)
targetScript = rootDir & "\renamer.py"
venvPyw = rootDir & "\.venv\Scripts\pythonw.exe"

If fso.FileExists(venvPyw) Then
    pyCmd = Chr(34) & venvPyw & Chr(34)
Else
    pyCmd = "pythonw.exe"
End If

exitCode = WshShell.Run(pyCmd & " " & Chr(34) & targetScript & Chr(34), 0, True)
Set WshShell = Nothing
Set fso = Nothing
WScript.Quit exitCode
