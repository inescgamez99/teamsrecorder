# TeamsRecorder — reinicio tras una actualizacion
#
# Lo invoca hooks/post-merge despues de cada git pull. Tambien es seguro
# ejecutarlo a mano:
#   powershell -ExecutionPolicy Bypass -File .\restart_after_update.ps1
#
# La ruta se deduce de la ubicacion de este fichero, asi que funciona
# independientemente de donde este clonado el repo.

$root = $PSScriptRoot
. (Join-Path $root 'tr_env.ps1')

if (Test-TRRecording -Root $root) {
    Write-Host ''
    Write-Host 'TeamsRecorder: hay una grabacion en curso.' -ForegroundColor Yellow
    Write-Host '   Los cambios ya se han descargado. Reinicia la app cuando termine la reunion.' -ForegroundColor Yellow
    Write-Host ''
    Show-TRNotification -Text 'Hay una grabacion en curso. Reinicia la app cuando termine la reunion.'
    exit 0
}

# Orden importante: parar el watchdog antes que el daemon. Al contrario, el
# watchdog relanza la app a los 5 segundos y pip actualiza ficheros en uso.
Stop-TRWatchdog -Root $root | Out-Null
Stop-TRDaemon   -Root $root | Out-Null

if (-not (Update-TRDependencies -Root $root)) {
    Write-Host 'TeamsRecorder: no se pudieron actualizar las dependencias.' -ForegroundColor Yellow
    Write-Host '   Revisa que exista el entorno virtual (.venv) o que python este en el PATH.' -ForegroundColor Yellow
}

if (Start-TRDaemon -Root $root) {
    Write-Host 'TeamsRecorder reiniciado con los ultimos cambios.' -ForegroundColor Green
    exit 0
}

Write-Host 'TeamsRecorder: el daemon no ha arrancado.' -ForegroundColor Red
Write-Host "   Revisa $root\teamsrecorder.log" -ForegroundColor Red
exit 1
