# TeamsRecorder — funciones compartidas de entorno
#
# Una sola implementacion de "donde esta instalado", "que interprete usar" y
# "como parar/arrancar el daemon". Lo usan watchdog.ps1,
# restart_after_update.ps1 (llamado por hooks/post-merge) y la skill
# .claude/skills/teamsrecorder. Ningun consumidor debe reinventar esta logica
# ni hardcodear rutas de instalacion.
#
# Uso:  . (Join-Path $dir "tr_env.ps1")

$script:TRConfigFile = Join-Path $env:LOCALAPPDATA 'TeamsRecorder\install_path.txt'


function Test-TRRoot {
    # Un directorio es una instalacion valida si es un clon con el codigo dentro.
    # No se comprueba la URL del remote: los forks son legitimos.
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) { return $false }
    if (-not (Test-Path (Join-Path $Path '.git')))        { return $false }
    if (-not (Test-Path (Join-Path $Path 'main.py')))     { return $false }
    return (Test-Path (Join-Path $Path 'tray_app.py'))
}


function Save-TRRoot {
    # Persiste la ruta descubierta para que el siguiente arranque no vuelva a buscar.
    param([Parameter(Mandatory = $true)][string]$Path)

    try {
        $dir = Split-Path -Parent $script:TRConfigFile
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        Set-Content -Path $script:TRConfigFile -Value (Resolve-Path $Path).Path -Encoding utf8
    } catch {}
}


function Get-TRRoot {
    # Devuelve la ruta de instalacion, o $null si no la encuentra.
    # Orden: variable de entorno -> config guardada -> repo del directorio actual
    #        -> ubicaciones habituales.
    # Si devuelve $null, el llamador debe PREGUNTAR al usuario, nunca asumir
    # una ruta ni clonar de nuevo: un segundo clon deja dos apps compitiendo
    # por el mismo .lock.

    if (Test-TRRoot $env:TEAMSRECORDER_HOME) {
        return (Resolve-Path $env:TEAMSRECORDER_HOME).Path
    }

    if (Test-Path $script:TRConfigFile) {
        $saved = Get-Content $script:TRConfigFile -Raw -ErrorAction SilentlyContinue
        if ($saved) { $saved = $saved.Trim() }
        if (Test-TRRoot $saved) { return (Resolve-Path $saved).Path }
    }

    $top = & git rev-parse --show-toplevel 2>$null
    if ($LASTEXITCODE -eq 0 -and $top) {
        $top = ($top -replace '/', '\').Trim()
        if (Test-TRRoot $top) {
            $top = (Resolve-Path $top).Path
            Save-TRRoot $top
            return $top
        }
    }

    foreach ($cand in @(
        (Join-Path $env:USERPROFILE 'Documents\TeamsRecorder'),
        (Join-Path $env:USERPROFILE 'repos\teamsrecorder'),
        (Join-Path $env:USERPROFILE 'source\repos\teamsrecorder'),
        (Join-Path $env:USERPROFILE 'git\teamsrecorder'),
        (Join-Path $env:USERPROFILE 'TeamsRecorder')
    )) {
        if (Test-TRRoot $cand) {
            $cand = (Resolve-Path $cand).Path
            Save-TRRoot $cand
            return $cand
        }
    }

    return $null
}


function Get-TRPython {
    # Devuelve @{ Python; Pythonw; Source } o $null.
    # Prioridad: .venv del repo -> PATH (ignorando el alias de WindowsApps)
    #            -> instalaciones por usuario.
    # El .venv va primero: si el repo tiene uno, es el interprete con las
    # dependencias instaladas, y usar el del sistema instala en el sitio
    # equivocado y arranca la app sin sus paquetes.
    param([Parameter(Mandatory = $true)][string]$Root)

    $venv = Join-Path $Root '.venv\Scripts'
    $venvPy = Join-Path $venv 'python.exe'
    if (Test-Path $venvPy) {
        $venvPyw = Join-Path $venv 'pythonw.exe'
        if (-not (Test-Path $venvPyw)) { $venvPyw = $venvPy }
        return [pscustomobject]@{ Python = $venvPy; Pythonw = $venvPyw; Source = 'venv' }
    }

    $exe = $null
    foreach ($name in @('pythonw.exe', 'python.exe')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notlike '*WindowsApps*') { $exe = $cmd.Source; break }
    }

    if (-not $exe) {
        foreach ($cand in @(
            "$env:LOCALAPPDATA\Programs\Python\Python313\pythonw.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe",
            "$env:LOCALAPPDATA\Programs\Python\Python311\pythonw.exe"
        )) {
            if (Test-Path $cand) { $exe = $cand; break }
        }
    }

    if (-not $exe) { return $null }

    $dir = Split-Path -Parent $exe
    $py  = Join-Path $dir 'python.exe'
    $pyw = Join-Path $dir 'pythonw.exe'
    if (-not (Test-Path $py))  { $py  = $exe }
    if (-not (Test-Path $pyw)) { $pyw = $py }

    return [pscustomobject]@{ Python = $py; Pythonw = $pyw; Source = 'system' }
}


function Test-TRRecording {
    # $true si hay una grabacion en curso. Nunca reinicies la app si lo devuelve.
    param([Parameter(Mandatory = $true)][string]$Root)

    $statusFile = Join-Path $Root '.pipeline_status.json'
    if (-not (Test-Path $statusFile)) { return $false }

    try {
        $status = Get-Content $statusFile -Raw -Encoding UTF8 | ConvertFrom-Json
        return [bool](@($status.jobs | Where-Object { $_.stage -eq 'recording' }).Count)
    } catch {
        return $false
    }
}


function Get-TRDaemonProcess {
    # Procesos del daemon de ESTA instalacion, filtrados por linea de comandos.
    # Filtrar por nombre de proceso ("Get-Process python") esta mal por dos
    # motivos: mata Python de otros proyectos del usuario, y no captura
    # pythonw.exe, que es precisamente como corre la app.
    param([Parameter(Mandatory = $true)][string]$Root)

    $mainPy = [System.Management.Automation.WildcardPattern]::Escape((Join-Path $Root 'main.py'))
    return @(
        Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*$mainPy*" }
    )
}


function Get-TRWatchdogProcess {
    param([Parameter(Mandatory = $true)][string]$Root)

    $wd = [System.Management.Automation.WildcardPattern]::Escape((Join-Path $Root 'watchdog.ps1'))
    return @(
        Get-CimInstance Win32_Process -Filter "Name like '%powershell%'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*$wd*" }
    )
}


function Stop-TRDaemon {
    # Para el daemon (proceso padre + hijo de la UI). Devuelve cuantos paro.
    param([Parameter(Mandatory = $true)][string]$Root)

    # @() obligatorio: PowerShell desenvuelve los arrays de un elemento al
    # retornarlos, y entonces .Count vale $null en vez de 1.
    $procs = @(Get-TRDaemonProcess -Root $Root)
    if ($procs.Count -eq 0) { return 0 }

    # Los hijos primero: si muere el padre antes, deja huerfanos con el .lock tomado.
    $ids      = @($procs | ForEach-Object { $_.ProcessId })
    $children = @($procs | Where-Object { $ids -contains $_.ParentProcessId })
    $parents  = @($procs | Where-Object { $ids -notcontains $_.ParentProcessId })

    foreach ($p in ($children + $parents)) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    return $procs.Count
}


function Stop-TRWatchdog {
    # Se para antes de actualizar dependencias: si sigue vivo, relanza el daemon
    # a los 5 segundos y pip se pelea con los ficheros en uso.
    param([Parameter(Mandatory = $true)][string]$Root)

    $procs = @(Get-TRWatchdogProcess -Root $Root)
    foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    return $procs.Count
}


function Start-TRDaemon {
    # Arranca la app a traves del watchdog, que es el UNICO responsable de
    # lanzar main.py. Arrancar main.py aparte crea una segunda instancia que
    # pelea por el .lock con la que el watchdog acabara de levantar.
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [int]$TimeoutSeconds = 30
    )

    if (@(Get-TRWatchdogProcess -Root $Root).Count -eq 0) {
        $wd = Join-Path $Root 'watchdog.ps1'
        if (-not (Test-Path $wd)) { return $false }
        Start-Process -FilePath 'powershell.exe' `
            -ArgumentList @('-NonInteractive', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', $wd) `
            -WorkingDirectory $Root | Out-Null
    }

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (@(Get-TRDaemonProcess -Root $Root).Count -gt 0) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}


function Update-TRDependencies {
    param([Parameter(Mandatory = $true)][string]$Root)

    $py = Get-TRPython -Root $Root
    if (-not $py) { return $false }

    $req = Join-Path $Root 'requirements.txt'
    if (-not (Test-Path $req)) { return $false }

    & $py.Python -m pip install -r $req --quiet
    return ($LASTEXITCODE -eq 0)
}


function Show-TRNotification {
    param(
        [Parameter(Mandatory = $true)][string]$Text,
        [string]$Title = 'TeamsRecorder'
    )

    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $notify = New-Object System.Windows.Forms.NotifyIcon
        $notify.Icon = [System.Drawing.SystemIcons]::Information
        $notify.BalloonTipTitle = $Title
        $notify.BalloonTipText  = $Text
        $notify.Visible = $true
        $notify.ShowBalloonTip(8000)
        Start-Sleep -Seconds 2
        $notify.Dispose()
    } catch {}
}
