$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $RepoRoot "scripts\run_research_job.ps1"
$TaskName = "EagleSignalAI-Daily9AM"

if (-not (Test-Path $Runner)) {
    throw "Missing runner script: $Runner"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`"" `
    -WorkingDirectory $RepoRoot

$Daily = New-ScheduledTaskTrigger -Daily -At 9:00AM

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Daily `
        -Settings $Settings `
        -Description "EagleSignal AI daily 09:00 local focused watchlist research collection. Later refreshes are manual from the dashboard Jobs tab." `
        -Force | Out-Null

    Write-Host "Installed scheduled task: $TaskName"
    Write-Host "Runner: $Runner"
} catch {
    Write-Warning "Task Scheduler registration failed: $($_.Exception.Message)"
    Write-Warning "Installing no-admin Startup-folder fallback instead."
    & (Join-Path $RepoRoot "scripts\install_startup_collector.ps1")
}
