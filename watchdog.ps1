# TeamsRecorder Watchdog — reinicia el daemon si se cae
$dir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$mainpy = Join-Path $dir "main.py"
$lockf  = Join-Path $dir ".lock"
$logf   = Join-Path $dir "teamsrecorder.log"

# Resolver el interprete: .venv del repo primero, luego PATH, luego
# instalaciones por usuario. Ver Get-TRPython en tr_env.ps1.
. (Join-Path $dir "tr_env.ps1")
$pyEnv = Get-TRPython -Root $dir

function Log($msg) {
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Add-Content -Path $logf -Value "$ts WATCHDOG: $msg" -Encoding UTF8
}

if (-not $pyEnv) { Log "ERROR: no se encontro python"; exit 1 }
$python = $pyEnv.Pythonw
Log "Watchdog iniciado (python: $python, origen: $($pyEnv.Source))"

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
