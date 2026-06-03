$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $RepoRoot "scripts\run_research_job.ps1"
$TaskName = "EagleSignalAI-ResearchCollector"

if (-not (Test-Path $Runner)) {
    throw "Missing runner script: $Runner"
}

$Action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`"" `
    -WorkingDirectory $RepoRoot

$AtLogOn = New-ScheduledTaskTrigger -AtLogOn
$EveryTwoHours = New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Hours 2) `
    -RepetitionDuration (New-TimeSpan -Days 1)

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
        -Trigger @($AtLogOn, $EveryTwoHours) `
        -Settings $Settings `
        -Description "EagleSignal AI focused watchlist research collection every two hours with retry." `
        -Force | Out-Null

    Write-Host "Installed scheduled task: $TaskName"
    Write-Host "Runner: $Runner"
} catch {
    Write-Warning "Task Scheduler registration failed: $($_.Exception.Message)"
    Write-Warning "Installing no-admin Startup-folder fallback instead."
    & (Join-Path $RepoRoot "scripts\install_startup_collector.ps1")
}
