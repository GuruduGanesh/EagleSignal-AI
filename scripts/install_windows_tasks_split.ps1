$ErrorActionPreference = "Stop"

# Splits EagleSignal collection into several small, independently managed
# Windows Task Scheduler jobs (per the user request for "small tasks with
# multiple jobs"). Each task is registered separately so you can enable,
# disable, or re-run any one of them on its own in Task Scheduler.
#
#   1. EagleSignalAI-MorningBrief  full research scan daily at 08:35 local
#   2. EagleSignalAI-EveningBrief  full research scan daily at 20:35 local
#   3. EagleSignalAI-Intraday30m   grouped parallel refresh + analysis every 5 min, 09:00-16:30
#   4. EagleSignalAI-WeeklyRetune  ADR-002 walk-forward retune every Saturday
#
# Per-user tasks: no Administrator elevation required.

$RepoRoot = Split-Path -Parent $PSScriptRoot
$FullRunner = Join-Path $RepoRoot "scripts\run_research_job.ps1"
$LightRunner = Join-Path $RepoRoot "scripts\run_intraday_job.ps1"
$TuneRunner = Join-Path $RepoRoot "scripts\run_weekly_tune_job.ps1"

if (-not (Test-Path $FullRunner)) { throw "Missing runner: $FullRunner" }
if (-not (Test-Path $LightRunner)) { throw "Missing runner: $LightRunner" }
if (-not (Test-Path $TuneRunner)) { throw "Missing runner: $TuneRunner" }

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

function Register-EagleMinuteTask([string]$Name, [string]$Runner, [int]$Minutes, [string]$Start, [string]$Duration, [string]$Desc) {
    $TaskRun = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \`"$Runner\`""
    $out = schtasks.exe /Create /TN $Name /TR $TaskRun /SC DAILY /ST $Start /RI $Minutes /DU $Duration /F 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to register ${Name}: $out"
    }
    try {
        Set-ScheduledTask -TaskName $Name -Settings $CommonSettings | Out-Null
    } catch {
        Write-Warning "Installed $Name, but could not apply common task settings: $($_.Exception.Message)"
    }
    Write-Host "Installed task: $Name ($Desc)"
}

# Retire older full-scan schedules so the active full prediction scans are only
# the requested morning/evening briefs.
foreach ($OldTask in @("EagleSignalAI-AtLogon", "EagleSignalAI-Every2Hours")) {
    if (Get-ScheduledTask -TaskName $OldTask -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $OldTask -Confirm:$false
        Write-Host "Removed retired task: $OldTask"
    }
}

# 1. Morning brief -- daily full scan before the US cash open.
Register-EagleTask "EagleSignalAI-MorningBrief" `
    (New-ScheduledTaskTrigger -Daily -At 8:35AM) `
    $FullRunner "EagleSignal morning full research brief at 08:35 local."

# 2. Evening brief -- daily full scan after the market session.
Register-EagleTask "EagleSignalAI-EveningBrief" `
    (New-ScheduledTaskTrigger -Daily -At 8:35PM) `
    $FullRunner "EagleSignal evening full research brief at 20:35 local."

# 3. Intraday grouped refresh + focused re-analysis -- every 5 min during the session.
# The task keeps the old name for continuity, but the cadence is now 5 minutes.
Register-EagleMinuteTask "EagleSignalAI-Intraday30m" `
    $LightRunner 5 "09:00" "07:30" "EagleSignal grouped parallel refresh and focused re-analysis every 5 minutes during the session."

# 4. Weekly retune -- refresh fitted weights from measured walk-forward replay.
Register-EagleTask "EagleSignalAI-WeeklyRetune" `
    (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At 8:00PM) `
    $TuneRunner "EagleSignal weekly ADR-002 walk-forward retune of price-derived weights."

Write-Host ""
Write-Host "Done. Review/manage these in Task Scheduler (taskschd.msc) under the Task Scheduler Library."
Write-Host "Re-run any one now with:  Start-ScheduledTask -TaskName <name>"
