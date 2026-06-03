$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$env:PYTHONPATH = Join-Path $RepoRoot "src"

& $Python -m eaglesignal collect --strategy swing --horizon 5D --retries 2 --retry-delay-seconds 60
exit $LASTEXITCODE
