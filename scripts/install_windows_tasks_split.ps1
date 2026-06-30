$ErrorActionPreference = "Stop"

# Registers the single requested automatic Windows Task Scheduler job:
#
#   EagleSignalAI-Daily9AM  full research scan daily at 09:00 local
#
# Everything else is manual from the dashboard Jobs tab. Per-user task:
# no Administrator elevation required.

$RepoRoot = Split-Path -Parent $PSScriptRoot
$FullRunner = Join-Path $RepoRoot "scripts\run_research_job.ps1"
if (-not (Test-Path $FullRunner)) { throw "Missing runner: $FullRunner" }

function New-RunnerAction([string]$Runner) {
    New-ScheduledTaskAction `
        -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`"" `
        -WorkingDirectory $RepoRoot
}

$CommonSettings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

function Register-EagleTask([string]$Name, $Trigger, [string]$Runner, [string]$Desc) {
    try {
        Register-ScheduledTask `
            -TaskName $Name `
            -Action (New-RunnerAction $Runner) `
            -Trigger $Trigger `
            -Settings $CommonSettings `
            -Description $Desc `
            -Force | Out-Null
        Write-Host "Installed task: $Name"
    } catch {
        Write-Warning "Failed to register $Name : $($_.Exception.Message)"
    }
}

# Retire older schedules so the active automatic refresh is only the requested
# daily 09:00 local run.
foreach ($OldTask in @(
    "EagleSignalAI-AtLogon",
    "EagleSignalAI-Every2Hours",
    "EagleSignalAI-MorningBrief",
    "EagleSignalAI-EveningBrief",
    "EagleSignalAI-RefreshAnalyze2h",
    "EagleSignalAI-Intraday30m",
    "EagleSignalAI-WeeklyRetune"
)) {
    if (Get-ScheduledTask -TaskName $OldTask -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $OldTask -Confirm:$false
        Write-Host "Removed retired task: $OldTask"
    }
}

Register-EagleTask "EagleSignalAI-Daily9AM" `
    (New-ScheduledTaskTrigger -Daily -At 9:00AM) `
    $FullRunner "EagleSignal daily full research scan at 09:00 local time. Manual refreshes are handled from the dashboard Jobs tab."

Write-Host ""
Write-Host "Done. Review/manage these in Task Scheduler (taskschd.msc) under the Task Scheduler Library."
Write-Host "Re-run any one now with:  Start-ScheduledTask -TaskName <name>"
