$ErrorActionPreference = "Stop"

# Two-hour grouped refresh/analyze: runs the same scheduled/manual collection
# path as the browser Jobs tab. Sources are grouped and refreshed in parallel
# before the focused watchlist is re-analyzed, so every important source
# category is considered without becoming one giant serial process.

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$env:PYTHONPATH = Join-Path $RepoRoot "src"

& $Python -m eaglesignal collect --strategy swing --horizon 5D --retries 1 --retry-delay-seconds 30
exit $LASTEXITCODE
