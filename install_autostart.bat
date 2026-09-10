@echo off
setlocal

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

rem Eliminar VBS antiguo: VBScript esta deshabilitado en Windows 11 (KB5051989+)
del /Q "%STARTUP%\TeamsRecorder.vbs" 2>nul

rem Registrar tarea programada via Task Scheduler (no depende de VBScript)
powershell.exe -NonInteractive -ExecutionPolicy Bypass -File "%~dp0install_task.ps1"

if %errorlevel%==0 (
    echo TeamsRecorder watchdog instalado como tarea programada al inicio de sesion.
) else (
    echo ERROR al crear la tarea. Revisa que PowerShell tenga permisos.
)
pause
