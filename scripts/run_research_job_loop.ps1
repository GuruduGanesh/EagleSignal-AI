$ErrorActionPreference = "Continue"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $RepoRoot "scripts\run_research_job.ps1"
$LogDir = Join-Path $RepoRoot "data\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$LogFile = Join-Path $LogDir "collector-loop.log"

"$(Get-Date -Format o) EagleSignal collector loop started." | Out-File -FilePath $LogFile -Encoding utf8 -Append

while ($true) {
    try {
        "$(Get-Date -Format o) Running collector." | Out-File -FilePath $LogFile -Encoding utf8 -Append
        powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Runner *>> $LogFile
    } catch {
        "$(Get-Date -Format o) Collector loop error: $($_.Exception.Message)" | Out-File -FilePath $LogFile -Encoding utf8 -Append
    }
    Start-Sleep -Seconds 7200
}
