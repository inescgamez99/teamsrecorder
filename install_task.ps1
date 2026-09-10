param([string]$WatchdogPath = "")

if (-not $WatchdogPath) {
    $WatchdogPath = Join-Path $PSScriptRoot "watchdog.ps1"
}
$WatchdogPath = (Resolve-Path $WatchdogPath).Path

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$WatchdogPath`""

# Trigger 1: al iniciar sesión interactiva
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$logonTrigger.Delay = "PT10S"

# Trigger 2: al despertar de suspensión/hibernación
# EventID 1 de Microsoft-Windows-Power-Troubleshooter indica que el sistema se wake
$wakeQuery = '<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name=''Microsoft-Windows-Power-Troubleshooter''] and EventID=1]]</Select></Query></QueryList>'
$wakeClass = Get-CimClass -Namespace 'Root/Microsoft/Windows/TaskScheduler' -ClassName 'MSFT_TaskEventTrigger' -ErrorAction SilentlyContinue
$triggers = @($logonTrigger)
if ($wakeClass) {
    $wakeTrigger = New-CimInstance -CimClass $wakeClass -ClientOnly -Property @{
        Enabled      = $true
        Subscription = $wakeQuery
        Delay        = 'PT20S'
    }
    $triggers += $wakeTrigger
    $triggerDesc = "AtLogOn (10s) + wake-from-sleep (20s)"
} else {
    $triggerDesc = "AtLogOn (10s)  [wake trigger no disponible en este sistema]"
}

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName "TeamsRecorder" `
    -Action $action `
    -Trigger $triggers `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "Tarea 'TeamsRecorder' registrada para $env:USERDOMAIN\$env:USERNAME"
Write-Host "Triggers: $triggerDesc"
Write-Host "Watchdog: $WatchdogPath"
