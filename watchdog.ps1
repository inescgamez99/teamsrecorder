# TeamsRecorder Watchdog — reinicia el daemon si se cae
$dir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$mainpy = Join-Path $dir "main.py"
$lockf  = Join-Path $dir ".lock"
$logf   = Join-Path $dir "teamsrecorder.log"

# Log definido antes de cargar tr_env.ps1 para capturar cualquier fallo de arranque
function Log($msg) {
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Add-Content -Path $logf -Value "$ts WATCHDOG: $msg" -Encoding UTF8
}

Log "Watchdog iniciado (PID $PID)"

try {
    . (Join-Path $dir "tr_env.ps1")
} catch {
    Log "ERROR cargando tr_env.ps1: $_"
    exit 1
}

$pyEnv = Get-TRPython -Root $dir
if (-not $pyEnv) { Log "ERROR: no se encontro python"; exit 1 }

# Salir si ya hay otro watchdog corriendo para esta instalacion
$existing = @(Get-TRWatchdogProcess -Root $dir | Where-Object { $_.ProcessId -ne $PID })
if ($existing.Count -gt 0) {
    Log "Otro watchdog ya corre (PIDs: $($existing.ProcessId -join ', ')). Saliendo."
    exit 0
}

$python = $pyEnv.Pythonw
Log "Python: $python (origen: $($pyEnv.Source))"

while ($true) {
    # Limpiar lock huerfano
    if (Test-Path $lockf) {
        $pid_in_lock = Get-Content $lockf -ErrorAction SilentlyContinue
        if ($pid_in_lock) {
            $alive = Get-Process -Id $pid_in_lock -ErrorAction SilentlyContinue
            if (-not $alive) {
                Remove-Item $lockf -Force -ErrorAction SilentlyContinue
                Log "Lock huerfano eliminado (PID $pid_in_lock)"
            }
        }
    }

    Log "Iniciando daemon..."
    $proc = Start-Process -FilePath $python -ArgumentList "`"$mainpy`"" -PassThru -WorkingDirectory $dir
    $proc.WaitForExit()
    $exitCode = $proc.ExitCode
    Log "Daemon termino (exit $exitCode). Reiniciando en 5s..."
    Start-Sleep -Seconds 5
}
