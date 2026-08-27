Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")
Dim dir : dir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "pythonw """ & dir & "\main.py""", 0, False
