$ErrorActionPreference = "Stop"

# Weekly ADR-002 retune. This replays only price-derived engines (no lookahead)
# and writes config/weights.fitted.yml when successful.

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    $Python = "python"
}

$env:PYTHONPATH = Join-Path $RepoRoot "src"

& $Python -m eaglesignal auto-tune --profiles swing,intraday,options_buying --horizon-days 5 --period 2y --step 5 --max-tickers 25
exit $LASTEXITCODE
