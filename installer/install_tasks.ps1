param(
    [Parameter(Mandatory = $true)]
    [string]$InstallRoot,

    [Parameter(Mandatory = $true)]
    [string]$UserName
)

$ErrorActionPreference = "Stop"

$coreTaskName = "NODARIS Core"
$watchdogTaskName = "NODARIS Watchdog"
$coreDirectory = Join-Path $InstallRoot "Core"
$coreExecutable = Join-Path $coreDirectory "NODARIS Core.exe"
$qualifiedUser = if ($UserName.Contains("\")) {
    $UserName
} else {
    "$env:USERDOMAIN\$UserName"
}

if (-not (Test-Path -LiteralPath $coreExecutable -PathType Leaf)) {
    throw "Executavel do Core nao encontrado: $coreExecutable"
}

$principal = New-ScheduledTaskPrincipal `
    -UserId $qualifiedUser `
    -LogonType Interactive `
    -RunLevel Limited

$coreAction = New-ScheduledTaskAction `
    -Execute $coreExecutable `
    -Argument "--core" `
    -WorkingDirectory $coreDirectory

$coreTrigger = New-ScheduledTaskTrigger `
    -AtLogOn `
    -User $qualifiedUser

$coreSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask `
    -TaskName $coreTaskName `
    -Action $coreAction `
    -Trigger $coreTrigger `
    -Settings $coreSettings `
    -Principal $principal `
    -Description "Inicia e mantem o NODARIS Core em segundo plano." `
    -Force | Out-Null

$watchdogAction = New-ScheduledTaskAction `
    -Execute $coreExecutable `
    -Argument "--watchdog" `
    -WorkingDirectory $coreDirectory

$watchdogTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$watchdogSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $watchdogTaskName `
    -Action $watchdogAction `
    -Trigger $watchdogTrigger `
    -Settings $watchdogSettings `
    -Principal $principal `
    -Description "Verifica e recupera automaticamente o NODARIS Core." `
    -Force | Out-Null

Start-ScheduledTask -TaskName $coreTaskName

$deadline = (Get-Date).AddSeconds(60)
$healthValidated = $false

while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod `
            -Uri "http://127.0.0.1:8765/health" `
            -TimeoutSec 3

        if (
            $health.status -eq "ok" -and
            $health.service -eq "monitorping-api" -and
            $health.monitor_engine -eq "running"
        ) {
            $healthValidated = $true
            break
        }
    } catch {
        # O Core ainda esta iniciando; tentaremos novamente ate o prazo.
    }

    Start-Sleep -Seconds 2
}

if (-not $healthValidated) {
    throw "O NODARIS Core nao passou no health check apos a instalacao."
}
