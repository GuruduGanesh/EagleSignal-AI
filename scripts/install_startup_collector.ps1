$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LoopScript = Join-Path $RepoRoot "scripts\run_research_job_loop.ps1"
$Startup = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $Startup "EagleSignalAI-ResearchCollector.lnk"

if (-not (Test-Path $LoopScript)) {
    throw "Missing loop script: $LoopScript"
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$LoopScript`""
$Shortcut.WorkingDirectory = $RepoRoot
$Shortcut.Description = "EagleSignal AI collector loop every two hours after login."
$Shortcut.Save()

Write-Host "Installed startup collector shortcut: $ShortcutPath"
Write-Host "It will run after the next login. Start now with: powershell -NoProfile -ExecutionPolicy Bypass -File `"$LoopScript`""
