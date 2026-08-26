Dim dir
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
CreateObject("WScript.Shell").Run "powershell.exe -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & dir & "\watchdog.ps1""", 0, False
