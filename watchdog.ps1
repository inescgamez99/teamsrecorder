# TeamsRecorder Watchdog — reinicia el daemon si se cae
$dir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$mainpy = Join-Path $dir "main.py"
$lockf  = Join-Path $dir ".lock"
$logf   = Join-Path $dir "teamsrecorder.log"

# Buscar pythonw.exe / python.exe en PATH
$found = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if ($found) { $python = $found.Source }
else {
    $found2 = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($found2) { $python = $found2.Source } else { $python = $null }
}

function Log($msg) {
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    Add-Content -Path $logf -Value "$ts WATCHDOG: $msg" -Encoding UTF8
}

if (-not $python) { Log "ERROR: no se encontro python"; exit 1 }
Log "Watchdog iniciado (python: $python)"

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
