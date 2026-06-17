# RUNBOOK.md

Operating guide for EagleSignal AI. Research only — not financial advice.

## Run a full scan (host)

```powershell
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; $env:PIPELINE_MAX_WORKERS='16'
.\.venv\Scripts\python.exe -m eaglesignal run --top 10
```

- `--top N` limits only the PRINTED rows; the dashboard/report always render the
  full watchlist.
- Outputs land in `reports/YYYY-MM-DD/`: `signals.json`, `dashboard.html`,
  `report.md`, `summary.csv`, `audit_log.jsonl`.
- `signals.json` + `dashboard.html` are written only at the END of a successful
  run, so a partial run never corrupts the live report.

## Run via the API container

```powershell
docker compose up -d --build api      # rebuild after any .py change
# dashboard: http://127.0.0.1:8000/dashboard   (Ctrl+F5 to bypass cache)
```

Only `./reports`, `./data`, `./config` are volume-mounted; Python source is baked
into the image, so **code changes require a rebuild**.

## Resume after a rate limit / timeout / crash

Progress is checkpointed to **`data/run_state.json`** after every ticker (atomic
write). To inspect where a run stopped and what failed:

```powershell
Get-Content data\run_state.json | ConvertFrom-Json | Select-Object current_stage, last_successful_ticker, counts, failed_tickers
```

- `current_stage` — init / analyze / report / complete.
- `completed_tickers`, `failed_tickers`, `pending_tickers`, `retry_count`.
- `resume_from_here` — true while a run is incomplete.

Each ticker is independent and degrades gracefully, so the simplest resume is to
**re-run the scan** — completed names refetch quickly and failed ones get another
chance. To re-run ONLY the failed names:

```powershell
$failed = (Get-Content data\run_state.json | ConvertFrom-Json).failed_tickers -join ','
.\.venv\Scripts\python.exe -m eaglesignal run --tickers $failed   # if --tickers is supported; else edit the watchlist
```

> Note: cross-process auto-resume (continuing an aborted OS process from its
> checkpoint without re-running upstream stages) is PARTIAL — see PENDING_ITEMS.md.

## Rate-limit backoff

Per-ticker exception retries use an exponential schedule **30 → 60 → 120 → 300s**
(`run_state.backoff_seconds`). The number of attempts is
`PER_TICKER_RETRIES + 1`. Lower `PIPELINE_MAX_WORKERS` (e.g. 8) if a provider
throttles often.

## Reset run state

```powershell
Remove-Item data\run_state.json   # next run starts a fresh checkpoint
```

## Verify output quality

- Open **Bull/Bear Verdicts** — every row shows Validation status + Expected % +
  Final req pts + R/R. VALID candidates clear ≥5%/required-points and ≥2:1 R/R.
- Most large caps will read REJECTED on a 5-day swing horizon — that is correct.
  Use the **20-day / long-term profile** to surface bigger honest moves.

## Strictness knobs (`.env`)

| Var | Default | Meaning |
|---|---|---|
| `MIN_OPTION_PROFIT_PCT` | 5 | Option idea must show ≥ this % premium gain to be promoted. |
| `MIN_OPTION_DAYS_TO_EXPIRY` | 5 | Ignore expiries under this DTE. |
| `PIPELINE_MAX_WORKERS` | 16 | Parallel ticker workers. |
| `PER_TICKER_RETRIES` | 1 | Retries before a ticker is marked failed. |

The strict 5% / point-floor / 2:1 reward-risk rule is hard-coded in
`analysis/candidate_gate.py` (constants `MIN_REQUIRED_PERCENT`, `MIN_REWARD_RISK`).
