$ErrorActionPreference = "Stop"

$taskNames = @(
    "NODARIS Watchdog",
    "NODARIS Core"
)

foreach ($taskName in $taskNames) {
    $task = Get-ScheduledTask `
        -TaskName $taskName `
        -ErrorAction SilentlyContinue

    if ($null -eq $task) {
        continue
    }

    Stop-ScheduledTask `
        -TaskName $taskName `
        -ErrorAction SilentlyContinue

    Unregister-ScheduledTask `
        -TaskName $taskName `
        -Confirm:$false `
        -ErrorAction Stop
}
