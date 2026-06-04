# EagleSignal AI Implementation Status

> Research-only product, not financial advice. Keep this file current after every
> meaningful change so a restarted terminal, rate-limit recovery, or new Codex
> turn can resume quickly without losing context.

Last updated: 2026-06-04 02:02 America/Chicago

## Backup

- Latest backup before FUTURE_WORK implementation: `backups/stock-market-backup-20260602-141036.zip`
- Latest backup before continuing pending tasks: `backups/stock-market-backup-20260602-150815.zip`
- Backup AFTER the options-intelligence + ops batch: `backups/stock-market-backup-20260602-160000-options-batch.zip` (src/tests/config/scripts/docs only).
- Backup AFTER the calendars + event-aware + Ollama/GPU sentiment batch: `backups/stock-market-backup-20260602-164000-calendars-sentiment.zip`.
- Backup AFTER the 2026-06-03 GPU + 5-DTE tightening batch: `backups/stock-market-backup-20260603-1000-gpu-dte.zip`.
- Backup AFTER the 2026-06-03 options analytics fix: `backups/stock-market-backup-20260603-1155-options-analytics.zip`.
- Backup BEFORE the 2026-06-03 feature/label + calibration batch: `backups/stock-market-backup-20260603-122821-feature-label-calibration.zip`.
- Backup excludes heavy/generated folders such as `.venv`, `reports`, `data`, caches, and prior backups.

## Active Objective

Implement the first practical batch from `FUTURE_WORK.md` while preserving all
existing dashboard, options, manual-trade, jobs, and watchlist behavior.

## Completed (2026-06-04 Semiconductor/storage ticker expansion)

- Added requested active semiconductor/storage names to `config/watchlist.yml`:
  - `ARM` / Arm Holdings plc
  - `STX` / Seagate Technology Holdings plc
- Both names have `options` strategy tags, so scheduled jobs, manual refresh,
  market/news/social/SEC/options data pulls, prediction scans, Options Edge,
  Trade Summary, Trade Strategy, and all ticker-driven tabs include them after
  the next scan.
- Updated `config/policy_theme_watchlists.yml` so Theme Watchlists includes
  `ARM` as chip-IP / edge-AI semiconductor context and `STX` as AI-storage /
  data-center storage context.

## Completed (2026-06-04 Requested ticker expansion)

- Added requested active scan tickers to `config/watchlist.yml`:
  - `QCOM` / QUALCOMM Incorporated
  - `APP` / AppLovin Corporation
  - `IONQ` / IonQ, Inc.
- Confirmed these requested names were already active: `AMD`, `SMCI`, `RKLB`,
  and `ISRG`.
- All seven requested tickers now have `options` strategy tags, so scheduled
  jobs, manual refresh, market/news/social/SEC/options data pulls, prediction
  scans, Options Edge, Trade Summary, Trade Strategy, and all ticker-driven tabs
  include them after the next scan.
- Updated `config/policy_theme_watchlists.yml` so Theme Watchlists also includes
  `QCOM`, `APP`, and `IONQ` as focused AI/quantum/software context.
- Updated the Theme Watchlists renderer to show the additional focused AI /
  quantum / software target section, not just the Trump-policy and priority
  AI hardware baskets.
- Validation: watchlist loader returned 44 active symbols at that step and reported all
  requested tickers as found.

## Completed (2026-06-04 Trade Summary lower-premium grouping)

- Tightened the execution-style strategy selection so Trade Summary and Trade
  Strategy only promote option contracts with:
  - DTE at or above `MIN_OPTION_DAYS_TO_EXPIRY`, with a hard floor of 5 days
  - a real quoted option premium greater than 0 and at or below `$50`
  - an actionable call/put signal, not `NO TRADE`
- Trade Summary now renders each ticker as a parent row and groups up to the
  top 3 qualifying expiries under that ticker.
- The grouped expiry rows remain collapsed until clicked, include the exact
  option contract/expiry/DTE/strike/entry/stop/exit and Add-option action, and
  keep sorting group-safe so expiries do not get separated from their ticker.
- Tickers without a lower-priced qualifying option remain visible as stock-only
  plans with the reason shown in the Option details cell.
- Options Edge remains broad research context; the lower-premium cap is applied
  to the practical Trade Summary/Trade Strategy promotion layer.

## Completed (2026-06-04 Compact trade summary)

- Added a new **Trade Summary** dashboard tab before the detailed Trade
  Strategy tab.
- Trade Summary is sorted best-first using a soft ranking that rewards
  confidence, opportunity, directional clarity, option readiness, liquidity,
  tight spreads, and lower risk.
- Stock-only rows show only the stock plan fields:
  current price, target price, target days, stop loss, exit price, bias,
  probability/forecast, and summary reason.
- Option-qualified rows add only the option-specific details:
  expiry, DTE, contract, strike, option entry, option stop, option exit,
  readiness/gate, spread %, volume/OI, IV Rank, and delta/theta.
- **Add option** remains wired into Manual Trade Journal for option rows.
- Live price refresh recalculates current/target/stop/exit cells in both Trade
  Summary and Trade Strategy.
- Existing detailed Trade Strategy tab remains in place and is also best-first.

## Completed (2026-06-04 Jobs refresh/generate schedule)

- Added a clear **Generate from newest data** button to the Jobs tab.
- The button queues the existing `/jobs/refresh-all` path with `analyze=true`,
  so all source groups refresh in parallel first, then the prediction pipeline
  runs and writes a fresh dashboard/report.
- Kept the existing **Refresh ALL source cache** path for category/status-only
  refreshes, with the existing `+ analyze` checkbox still available.
- Browser-side source auto-refresh now queues refresh + analysis every **2
  hours** instead of the prior 30-minute cache-only refresh.
- Updated `scripts/install_windows_tasks_split.ps1` to retire the old
  `EagleSignalAI-Intraday30m` 5-minute task and register
  `EagleSignalAI-RefreshAnalyze2h`, which runs grouped parallel refresh +
  analysis every **2 hours** while the laptop is on.
- Updated README/status text so restarted terminals know the active schedule.

## Completed (2026-06-04 Trade Strategy tab)

- Added a new dashboard tab: **Trade Strategy**.
- The tab converts the same shared prediction/options analysis into a concise
  research plan per ticker:
  - current underlying price
  - bullish/bearish bias
  - target price and target-days window
  - stop loss and exit price
  - selected option expiry, DTE, contract, strike, option entry, option stop,
    and option exit
  - option confidence, readiness/risk gate, spread %, volume/OI, IV Rank, and
    delta/theta
- The tab reuses existing Manual Trades wiring via **Add option**, so a selected
  strategy can be tracked in the manual journal without creating any broker
  order.
- Live price refresh now recalculates Trade Strategy current/target/stop/exit
  cells in-place when `/prices/refresh` returns new prices.
- Implementation is additive in `src/eaglesignal/reports/generator.py`; no
  prediction-engine, manual-trade, jobs, or options-engine behavior was removed.

## Completed (2026-06-02 Options Edge UX overhaul — critical page)

- **Two-row layout** per expiry (`reports/generator.py`): line 1 = metrics + Add-trade
  button; line 2 (full-width `opt-why` row) = consolidated **Verdict** + recommended
  **structure** (spread legs w/ est. max gain/loss/breakeven + premium-selling alt) +
  the **full Why (evidence)** (no longer truncated). The long evidence text moved off
  the wide single row, as requested.
- **Consolidated Verdict** (`_opt_verdict`) translates the risk gate into plain English:
  ✅ TRADEABLE / ⚠️ TRADE AS A SPREAD / 📝 PAPER ONLY / 🚫 NO TRADE, each with a one-line
  meaning. The help panel now states Confidence IS the single all-parameter score, and
  explains exactly what "spread only" means (don't buy the naked option — trade the
  defined-risk spread shown).
- **Add-trade button on every actionable row** (was only `gate==high`): labeled by gate
  (Add option / Add (spread leg) / Add (paper)); clicking adds to **Manual Trades** and
  switches to that tab (handler already calls `activateTab('manual')`).
- Sort grouping + collapse updated so each entry's two rows always travel together; the
  parent's Why row stays visible, child Why rows collapse with their expiry.
- Validation: full suite **69 passed** (fixed 2 advisor tests to force the rules backend
  so they're independent of the now-Ollama `.env`). Rendered dashboard confirmed: 2 rows
  per entry, verdict badges, Add buttons present incl. "Add (spread leg)" on spread-only,
  Why header removed. Docker image rebuilt.

## ▶ FIX LOG 2026-06-02 (dashboard 2-tickers + Ollama activation)

- **Root cause of "only 2 tickers" + stuck scans:** my new per-ticker earnings
  network call (yfinance) had no timeout and could hang the worker pool, so the
  full scan never finished and the dashboard kept showing the last 2-ticker
  validation run. **Fixed:** `ingestion/earnings.py` now runs the lookup under a
  hard `EARNINGS_FETCH_TIMEOUT` (default 6s) via a thread pool; on timeout it
  caches "unavailable" and the scan continues. (`--top N` only limits PRINTED
  rows, never the analysis — the dashboard always renders the full watchlist.)
- **Ollama/GPU activated (was a user blocker):** Ollama was already installed;
  pulled `llama3.2:3b` (2GB, fits 8GB VRAM), verified inference. Set in `.env`:
  `ADVISOR_PROVIDER=ollama`, `ADVISOR_MODEL=llama3.2:3b`, `ENABLE_LLM_SENTIMENT=true`.
  `docker-compose.yml` now points the container at the host GPU via
  `OLLAMA_BASE_URL=http://host.docker.internal:11434` + `extra_hosts host-gateway`.
  Verified: `/advisor/health` → `active_backend=ollama, reachable=true` on host AND
  container; `classify_headlines` returns nuanced GPU scores (beat +0.8, probe -0.7).
- **RESOLVED:** full 41-ticker scan completed 16:36 CT (exit 0) with GPU sentiment
  on; `/dashboard` now serves all 41 names (902 KB). Note: the browser caches the
  HTML — a **hard reload (Ctrl+F5)** or `?cb=` query is needed to see a fresh scan.
  If a scan ever stalls again, re-run:
  `$env:PYTHONPATH='src'; $env:PIPELINE_MAX_WORKERS='16'; .\.venv\Scripts\python.exe -m eaglesignal run --top 41`
  (add `$env:ENABLE_LLM_SENTIMENT='false'` for a faster lexicon-only populate).

## ▶ RESUME POINT (read this first if a session was interrupted)

**State as of 2026-06-02 ~16:40 CT:** TWO batches are complete, tested, and baked
into Docker — (A) options-intelligence + ops (60 passed) and (B) calendars +
event-aware confidence + Ollama/GPU sentiment (**69 passed total**). The ONLY thing
that may be unfinished is the cosmetic **full 41-ticker scan** that repopulates
today's dashboard. Nothing about the code depends on that scan.

**Batch B new files:** `src/eaglesignal/ingestion/calendars.py`,
`src/eaglesignal/analysis/llm_sentiment.py`, `config/event_calendar.yml`;
tests `test_calendars.py`, `test_llm_sentiment.py`.
**Batch B edited files:** `prediction/engine.py` (event-risk haircut + calendar
wiring), `analysis/sentiment.py` (LLM classifier hook), `advisor.py`
(`ollama_status`/`advisor_health`), `api.py` (`/advisor/health`, `/calendar`),
`config.py` (`enable_llm_sentiment`), plus `.env.example`, `DATA_SOURCES.md`,
`FUTURE_WORK.md`. New endpoints: `GET /advisor/health`, `GET /calendar`.

**Code changes are NOT under git** (no repo). The resume sources of truth are this
file + the backup zip listed under "Backup" above. To roll back the batch, unzip
`backups/stock-market-backup-20260602-160000-options-batch.zip` over the repo.

**New files:** `src/eaglesignal/ingestion/earnings.py`; `tests/test_earnings.py`,
`tests/test_tuning.py`, `tests/test_x_twitter.py`.
**Edited files:** `src/eaglesignal/config.py` (3 new settings),
`prediction/engine.py` (earnings wiring), `analysis/options.py` (IV-crush gate +
`_build_structures` premium-selling/multi-leg), `tuning.py` (`tune_multi_horizon`),
`jobs.py` (auto-tune uses multi-horizon), `ingestion/x_twitter.py` (read counter),
`api.py` (LAN lockdown), `reports/generator.py` (2026–2028 calendars),
`tests/test_options_edge.py` (2 new cases), `.env.example`, `FUTURE_WORK.md`,
`VALIDATION_AND_LIVE_READINESS.md`.

**How to finish / re-run the only in-flight step (safe to repeat any time):**
```
$env:PYTHONPATH='src'; $env:PYTHONIOENCODING='utf-8'; $env:PIPELINE_MAX_WORKERS='16'
.\.venv\Scripts\python.exe -m eaglesignal run --top 10
```
Then confirm the dashboard repopulated:
```
Invoke-RestMethod http://127.0.0.1:8000/health
# open http://127.0.0.1:8000/dashboard  (expect ~41 Overview rows)
```

**If you hit yfinance/news/API rate limits or transient errors during a scan:**
- It is safe to simply re-run the `eaglesignal run` command above; the pipeline
  retries transient per-ticker failures and degrades gracefully (no fabricated data).
- Lower `PIPELINE_MAX_WORKERS` (e.g. `8`) if providers throttle too often.
- Earnings/options/social sources that fail just return `available=False`; the
  prediction still completes. No partial run corrupts state — `signals.json` is
  only written at the end of a successful run.
- No further `docker compose build` is needed unless you edit `.py` files again
  (dashboard re-renders from the mounted `./reports`).

**No other pending CODE work in this batch.** Remaining roadmap items are either
data-lead-time (IV-Rank/scorecards need weeks of snapshots) or blocked on you
(Ollama, Cloudflare/Tailscale, Reddit app, X spend, password rotation) — see
`FUTURE_WORK.md` "Blockers only you can clear".

## Completed

- Completed (2026-06-03 feature/label + calibrated-confidence batch):
  - Added point-in-time `feature_snapshots.jsonl` rows for every successful
    prediction scan. These rows flatten market, component, forecast, options,
    event, freshness, and verdict features without future labels.
  - Added `/reliability/labels`, which joins stored feature rows to matured
    forward equity labels only after forward bars exist, avoiding lookahead.
  - Added `/reliability/options-scorecard`, which measures option-premium P/L
    from later stored marks for the same exact option contract. Rows remain
    pending until future option-chain snapshots exist.
  - Added `/reliability/calibration`, which builds and saves a historical
    confidence-bucket calibration profile from matured equity outcomes.
  - Live prediction scans now read the latest saved calibration profile quickly:
    raw confidence is preserved in `confidence_trace.raw_confidence_score`;
    `confidence_trace.calibration` explains whether confidence was adjusted or
    why it was left raw.
  - Jobs tab now exposes Reliability Scorecard, Options P/L Scorecard,
    Confidence Calibration, and Feature Labels buttons.
  - Validation completed so far:
    - compile changed Python files — passed.
    - focused reliability/historical tests — passed: 6 passed.
    - full unit test suite — passed: 77 passed, 1 existing datetime warning.
    - re-rendered `reports/2026-06-03/dashboard.html` from 41 signals.
    - rebuilt/restarted Docker API with `docker compose up -d --build api`.
    - `/health` returned `ok`.
    - `/snapshots/status` shows `feature_snapshots=2` after a real two-ticker
      pipeline smoke run that did not overwrite the 41-row dashboard report.
    - `/reliability/options-scorecard`, `/reliability/calibration`, and
      `/reliability/labels` returned `ok`; current rows are correctly pending
      until future bars/option marks exist.
    - In-app browser verified Jobs tab buttons for Options P/L Scorecard,
      Confidence Calibration, and Feature Labels, plus the new Calibration
      column in Confidence Traces with 41 rows.
- Completed (2026-06-03 options analytics fix):
  - Converted several "pending options analysis" gaps into implemented,
    source-labelled analytics without removing existing Options Edge behavior.
  - Added chain-derived ATM IV skew: near-ATM put IV minus near-ATM call IV,
    with bullish/bearish/balanced labels.
  - Added chain-derived term-structure slope: next-expiry average IV minus the
    current-expiry average IV, with contango/backwardation/flat labels.
  - Added chain-derived unusual-activity score from exact-contract volume/OI
    plus call/put chain volume. This is not a paid institutional unusual-flow
    feed and is labelled as chain-derived.
  - Added exact-contract OI-change tracking by comparing the current reference
    contract against the latest stored `options_chain_snapshots.jsonl` row for
    the same contract.
  - Surfaced `Skew/Term` and `UOA/OI Δ` columns in Options Edge and expanded
    the top help text so the user can see what each value means.
  - Fixed the stale MD-validation/dashboard text that still said Greeks,
    IV Rank, skew, term structure, UOA, OI change, and IV-crush were incomplete.
    The remaining honest gaps are paid unusual-flow/gamma vendors, full
    every-strike raw options history, option-premium outcome calibration, and
    full multi-factor no-lookahead backtesting.
  - Validation completed:
    - Focused options/historical tests: 12 passed.
    - Full unit test suite: 74 passed.
    - Re-rendered `reports/2026-06-03/dashboard.html` from 41 signals.
    - Rebuilt/restarted Docker API with `docker compose up -d --build api`.
    - `/health` returned `ok`.
    - Served dashboard contains the new `Skew/Term`, `UOA/OI`, and
      chain-derived activity help text, and no longer contains the stale
      pre-fix Options Analysis validation wording.
    - In-app browser verified the Options Edge tab at
      `http://127.0.0.1:8000/dashboard?cb=options-fix-20260603#options`.
    - Current saved report has 121 pre-fix option expiry rows, so the new
      `Skew/Term` and `UOA/OI` cells may show `--` until the next full
      prediction scan writes fresh `signals.json`.
- Completed (2026-06-03 schedule update):
  - Updated `scripts/install_windows_tasks_split.ps1` and applied it to Windows
    Task Scheduler.
  - Retired `EagleSignalAI-Every2Hours` so full scans are not running outside
    the requested daily morning/evening windows.
  - `EagleSignalAI-MorningBrief`: full prediction scan daily at **08:35 local**.
    Verified next run: 2026-06-04 08:35.
  - `EagleSignalAI-EveningBrief`: full prediction scan daily at **20:35 local**.
    Verified next run: 2026-06-03 20:35.
  - Superseded 2026-06-04: the prior `EagleSignalAI-Intraday30m` 5-minute
    cadence was retired and replaced by `EagleSignalAI-RefreshAnalyze2h`.
  - `EagleSignalAI-WeeklyRetune`: installed/verified weekly Saturday 20:00.
  - Updated README, WORKFLOW, and dashboard text to match the new cadence.
- Completed (2026-06-03 GPU + options expiry tightening):
  - Re-read current project state after outside changes before editing.
  - GPU Monte-Carlo is now wired from `Settings` into the prediction engine:
    `ENABLE_GPU_MONTE_CARLO` and `MONTE_CARLO_PATHS` are passed directly into
    `forecast_signal()` instead of relying only on ambient environment reads.
  - Added `MIN_OPTION_DAYS_TO_EXPIRY` (default `5`) to config and `.env.example`.
  - Options recommendation collection now enforces the 5-DTE minimum in
    `pipeline.py`, `refresh.py`, and `analysis/options.py`; sub-5-DTE expiries
    are not considered for Options Edge/recommendations.
  - Manual Trades exact option quote lookup still uses `min_days=0` so existing
    user-entered contracts can continue to be marked live even if they are close
    to expiry.
  - Added `short_horizon_forecasts` to each new prediction so 2D and 3D
    Monte-Carlo P(up), median return, and p05/p95 bands are available beside the
    existing main-horizon forecast. The dashboard Why cards render these bands
    after the next live scan writes fresh `signals.json`.
  - Updated README, DATA_SOURCES, FUTURE_WORK, and dashboard MD-validation text
    to reflect the 5-DTE floor and settings-wired GPU Monte Carlo.
  - Re-rendered `reports/2026-06-03/dashboard.html` from the latest 41-signal
    report so the browser no longer displays stale under-5-DTE option rows.
- Created a local project backup archive before edits.
- Re-read `FUTURE_WORK.md` and current source layout.
- Added historical snapshot settings:
  - `ENABLE_HISTORICAL_SNAPSHOTS=true`
  - `HISTORICAL_SNAPSHOTS_DIR=data/historical_snapshots`
- Added `historical_store.py` to persist:
  - compact prediction snapshots (`prediction_snapshots.jsonl`)
  - compact options-expiry snapshots (`options_expiry_snapshots.jsonl`)
  - IV snapshots (`iv_snapshots.jsonl`)
  - per-run JSON files by date
- Wired snapshot persistence into successful pipeline runs.
- Added `/snapshots/status` API visibility.
- Added unit coverage for snapshot writing and status counts.
- Updated README, validation docs, `.env.example`, and `FUTURE_WORK.md`.
- Validation completed:
  - Targeted snapshot/options tests passed: 5 passed.
  - Full unit test suite passed: 45 passed.
  - Full host run restored the complete dashboard with 41 predictions.
  - Full host run wrote 41 prediction snapshots, 121 options-expiry snapshots, and 121 IV snapshots.
  - Docker image rebuilt and `eaglesignal-api` restarted healthy.
  - `/health` returned `ok`.
  - `/snapshots/status` returned enabled with accumulated snapshot counts.
  - In-app browser verified dashboard loads with 41 Overview rows, 41 Options Edge parent rows, and Manual Trades still present.
- Confirmed these roadmap items are already implemented in code and need validation/docs rather than duplicate work:
  - Options Edge grouped parent/expiry rows with group-safe sorting.
  - Black-Scholes-style Greeks on reference contracts.
  - Sub-7-DTE options risk gate and confidence caps.
  - Realized-vol vs implied-vol ratio in Options Edge.
  - Local Ollama-capable advisor backend, key/API-gated.
  - Parallel Jobs tab refresh categories.
  - Manual Trade add/edit/delete with live P/L refresh.
- Continued pending roadmap implementation:
  - Added richer point-in-time snapshot persistence:
    - `options_chain_snapshots.jsonl` for selected expiry/contract snapshots.
    - `evidence_snapshots.jsonl` for source/evidence replay.
    - IV Rank helper functions from accumulated `iv_snapshots.jsonl`.
  - Added IV Rank / IV Percentile fields to Options Edge expiry ideas.
  - Added IV Rank risk caps for expensive long-premium options setups.
  - Added optional GPU Monte-Carlo:
    - `ENABLE_GPU_MONTE_CARLO=false` by default.
    - `MONTE_CARLO_PATHS=4000` default.
    - CuPy path when available; NumPy CPU fallback always works.
  - Added weekly auto-retune wiring:
    - `python -m eaglesignal auto-tune`
    - `/jobs/tune`
    - `scripts/run_weekly_tune_job.ps1`
    - `EagleSignalAI-WeeklyRetune` in `scripts/install_windows_tasks_split.ps1`
  - Added reliability scorecard foundation:
    - `src/eaglesignal/reliability.py`
    - `/reliability/scorecard`
    - Jobs tab buttons for snapshot status, reliability scorecard, and weekly retune.
  - Added focused tests for IV Rank, Options Edge IV Rank gates, GPU Monte-Carlo fallback, and empty scorecard behavior.
- Runtime speed follow-up:
  - Full `eaglesignal run --top 10` was observed taking about 10 minutes on the 41-ticker watchlist.
  - The pipeline already analyzed tickers concurrently, but the worker cap was fixed at 8.
  - Added `PIPELINE_MAX_WORKERS` with default `16` and wired `pipeline.py` to use it.
  - Increase cautiously if the laptop/network can handle it; lower it if yfinance/news/API providers throttle too often.
  - Validation: config/pipeline compile passed; focused tests passed (`5 passed`).

## Completed (2026-06-02 calendars + event-aware confidence + Ollama/GPU sentiment)

- §3 sources — Event calendars (`ingestion/calendars.py` + `config/event_calendar.yml`):
  - Keyless economic/political calendar: curated **FOMC** decision days (official
    Fed dates only, never guessed) + rule-derived **non-farm payrolls** (first
    Friday) and weekly **initial jobless claims** (Thursdays).
  - Company calendar: live per-ticker next-earnings (keyless).
  - `GET /calendar` (instant market/macro; `?include_earnings=true` adds live earnings).
- §2 accuracy — Event-aware confidence (engine):
  - A high-impact scheduled event inside the prediction horizon applies a **0.85
    confidence haircut**, adds an event-risk warning + verdict reason, and surfaces
    `event_calendar` / `event_risk_applied` in `confidence_trace`. Verified live:
    NFP (3d out) correctly triggered the haircut on a 5D run.
- §3.3 / G.3 — GPU/LLM sentiment (`analysis/llm_sentiment.py`):
  - Local **Ollama** headline classifier, opt-in via `ENABLE_LLM_SENTIMENT=true`,
    always falls back to the lexicon when Ollama is absent/slow/garbled. Wired into
    `analysis/sentiment.py`; method is labeled in the rationale.
- §4.1 / G.2 — Ollama health (`advisor.py` + `GET /advisor/health`):
  - `ollama_status()` probes `/api/tags`; `advisor_health()` reports the active
    backend + whether GPU sentiment is live. Verified: with no Ollama installed it
    correctly reports `active_backend=rules`, `ollama.reachable=false`.
- Validation: full suite **69 passed** (was 60; added `test_calendars.py`,
  `test_llm_sentiment.py`). Docker image rebuilt; `/advisor/health` and `/calendar`
  return 200. 2-ticker host run confirmed event-risk end-to-end.

## Completed (2026-06-02 options-intelligence + ops batch)

- §0.4 + §1.5 Earnings calendar & IV-crush:
  - Added `ingestion/earnings.py` — keyless next-earnings lookup (yfinance
    `get_earnings_dates` → `.calendar` fallback), per-process cache, graceful
    `available=False`, never fabricates a date.
  - Wired `days_to_earnings`/`next_earnings_date` into the engine and into
    `analyze_expiries`. Any long-premium expiry that brackets the next earnings
    date is flagged `earnings_in_window` and capped to defined-risk/credit
    structures by the Options Risk Gate (harsher inside 5 days).
- §1.6 + §1.7 Premium-selling & richer multi-leg (`analysis/options.py`):
  - New `_build_structures()` adds est. net debit/credit, max gain, max loss,
    and breakeven to verticals (§1.7); for rich-IV setups it surfaces a
    bull-put / bear-call **credit spread** (and an iron condor for neutral
    high-IV) as the preferred structure over buying premium (§1.6).
  - New `ExpiryIdea` fields: `earnings_in_window`, `days_to_earnings`,
    `next_earnings_date`, `strategy_label`, `alt_structure`.
- §2.3 Multi-horizon tuning (`tuning.py`):
  - `PROFILE_HORIZON_DAYS` + `horizon_for_profile()` + `tune_multi_horizon()`
    group profiles by natural horizon (intraday=1D, swing-family=5D,
    long_term/index=20D) and replay each once. Weekly auto-retune (`jobs.py`)
    now uses it, so `intraday` is finally fitted at 1D.
- §3.5 X read-cost counter (`ingestion/x_twitter.py`):
  - `data/x_api_usage.json` counts daily reads + est. cost; `X_DAILY_READ_BUDGET`
    (default 50, 0=off) blocks further paid calls once the budget is hit.
- §5.6 LAN auth lockdown (`api.py`):
  - `DASHBOARD_REQUIRE_LOGIN_ON_LAN=true` enforces login for non-loopback LAN
    clients too; loopback/localhost stays exempt.
- §7.1 Market calendars (`reports/generator.py`):
  - 2026–2028 full holidays + half-days (+ 2029-01-01 boundary).
- §6.1 Docker image rebuilt to bake all of the above; `/health` ok, dashboard 200.
- Validation:
  - Full suite **60 passed** (was 49); added `test_earnings.py`, `test_tuning.py`,
    `test_x_twitter.py`, and earnings/premium-selling cases in `test_options_edge.py`.
  - All changed Python files compile (incl. the dashboard f-string).
  - 2-ticker host run confirmed real-data end-to-end: AMD earnings available,
    gate→spread-only, premium-selling `bull_put_credit_spread` alternative and
    max-gain/loss/breakeven present on the spread.
  - Full watchlist scan re-run to restore the complete dashboard.

## In Process

- Full 41-ticker host run re-running to repopulate today's dashboard with the new
  options intelligence across all names (a quick 2-ticker validation run had
  temporarily overwritten today's report).

## Latest Validation

- Validation for the 2026-06-03 GPU + options expiry tightening:
  - compile changed Python files — passed.
  - focused tests — passed: 22 passed.
  - full test suite — passed: 73 passed, 1 existing datetime deprecation warning.
  - after adding 2D/3D short-horizon forecast bands:
    - compile changed Python files — passed.
    - focused tests — passed: 19 passed.
    - full test suite — passed: 73 passed, 1 existing datetime deprecation warning.
  - Docker rebuild/restart — passed; `eaglesignal-api` is healthy.
  - `/health` returned `ok`.
  - `/advisor/health` returned `active_backend=ollama`, `reachable=true`, and
    `llm_sentiment_active=true`.
  - Current settings smoke check:
    - `MIN_OPTION_DAYS_TO_EXPIRY=5`.
    - `ENABLE_GPU_MONTE_CARLO=false`, `MONTE_CARLO_PATHS=4000`.
    - X/NewsAPI/Finnhub keys are not configured, so those feeds are considered
      but skipped/fallback cleanly until keys are added.
  - Browser verification — passed:
    - dashboard title `EagleSignal AI Dashboard`
    - 41 Overview rows
    - 41 Options Edge parent rows
    - IV Rank column visible
    - Options Edge text shows the default 5-DTE minimum
    - minimum displayed Options Edge DTE is 5
    - displayed DTE below 5 count is 0
- Validation for the continued roadmap batch:
  - compile changed Python files — passed.
  - targeted tests — passed: 13 passed.
  - full tests — passed: 49 passed.
  - regenerate reports/dashboard — passed with full 41-ticker host run.
    - Latest run wrote 41 prediction snapshots.
    - Latest run wrote 194 options-expiry snapshots.
    - Latest run wrote 194 options-chain snapshots.
    - Latest run wrote 194 IV snapshots.
    - Latest run wrote 867 evidence snapshots.
  - Docker rebuild/restart — passed; `eaglesignal-api` is healthy.
  - API verification — passed:
    - `/health` returned `ok`.
    - `/snapshots/status` returned enabled with 125 prediction snapshots, 442 options-expiry snapshots, 194 options-chain snapshots, 442 IV snapshots, and 867 evidence snapshots.
    - `/reliability/scorecard` returned `ok`; current rows are pending/not-actionable because there are not yet enough forward bars after today's recommendations.
  - Browser verification — passed:
    - dashboard title `EagleSignal AI Dashboard`
    - 41 Overview rows
    - 41 Options Edge parent rows
    - IV Rank column visible
    - Jobs tab has Run Weekly Retune, Snapshot Status, and Reliability Scorecard controls

## Pending

- IV Rank/IV Percentile needs ~20+ stored IV observations per ticker/expiry before the dashboard can show real ranks instead of "need N/20".
- Full raw every-strike options-chain archive beyond selected expiry/contract snapshots.
- Full raw provider payload snapshots for every non-price data source.
- Option-premium scorecard is implemented, but useful values require future
  stored option marks for the same contracts to accumulate.
- GPU ML model training, embeddings/RAG similar-event memory, and non-price-engine tuning after enough point-in-time snapshots exist.

## Validation Commands

- Unit tests: `python -m pytest -q`
- Host collect run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m eaglesignal collect`
- Faster host run: `$env:PYTHONPATH='src'; $env:PIPELINE_MAX_WORKERS='16'; .\.venv\Scripts\python.exe -m eaglesignal run --top 10`
- Docker redeploy: `docker compose up -d --build api`
- Health check: `Invoke-RestMethod http://127.0.0.1:8000/health`

## Current Working Notes

- Do not claim or target 100% prediction accuracy. The goal is better measured
  reliability: source traceability, fallback behavior, calibrated confidence,
  risk gates, and outcome tracking.
- Keep all existing functionality as-is unless a roadmap item requires an additive
  change.
- Latest dashboard URL verified: `http://127.0.0.1:8000/dashboard?cb=roadmap-finish#overview`.
