@echo off
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

rem Eliminar VBS si todavia existe
del /Q "%STARTUP%\TeamsRecorder.vbs" 2>nul

rem Eliminar tarea programada
powershell.exe -NonInteractive -ExecutionPolicy Bypass -Command "Unregister-ScheduledTask -TaskName 'TeamsRecorder' -Confirm:$false -ErrorAction SilentlyContinue; Write-Host 'Tarea TeamsRecorder eliminada.'"

echo TeamsRecorder eliminado del inicio de Windows.
pause
