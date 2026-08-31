@echo off
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "VBS=%STARTUP%\TeamsRecorder.vbs"

rem Eliminar entrada antigua si existe
del /Q "%VBS%" 2>nul

rem Crear lanzador en el inicio con la ruta ABSOLUTA a watchdog.ps1
rem (%~dp0 = carpeta de este .bat, con backslash final)
> "%VBS%" echo CreateObject("WScript.Shell").Run "powershell.exe -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File ""%~dp0watchdog.ps1""", 0, False

echo TeamsRecorder watchdog instalado en el inicio de Windows.
echo Ruta watchdog: %~dp0watchdog.ps1
pause
