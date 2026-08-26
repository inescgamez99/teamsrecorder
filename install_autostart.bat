@echo off
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

rem Eliminar entrada antigua si existe
del /Q "%STARTUP%\TeamsRecorder.vbs" 2>nul

rem Instalar el watchdog (auto-reinicia si se cae)
copy /Y "%~dp0start_watchdog.vbs" "%STARTUP%\TeamsRecorder.vbs"
echo TeamsRecorder watchdog instalado en el inicio de Windows.
pause
