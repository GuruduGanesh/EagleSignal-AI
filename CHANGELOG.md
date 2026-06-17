# CHANGELOG.md

All notable changes to EagleSignal AI. Most recent first.

---

## 2026-06-04 — Index Options Strategies focus (primary tab)

**Why:** Refocus the product on **index option strategies**, each with its own
confidence; prefer lower-priced, higher-volume, higher-momentum contracts; target
option premium **< $35**; profit potential **≥ 10%**; strict actionable gate
**underlying ≥5% AND option ≥10%**; all values must populate.

### New
- **`src/eaglesignal/analysis/index_strategies.py`** — `build_index_strategies()`
  turns each index/ETF prediction's `all_expiry_snapshots` into ranked option
  STRATEGIES (Long Call/Put, debit/credit spreads, iron condor) with per-strategy
  **confidence**, entry premium (<$35), est. exit, **profit %**, volume, OI,
  direction-aligned **momentum**, IV/spread, and a strict status (✅ ACTIONABLE
  only when index move ≥5% AND option profit ≥10%; otherwise shown with the gap).
  Selection prefers **lower premium + higher volume + higher momentum**. Reuses
  the existing universe module (`index_options.py`) for the cash→ETF proxy map
  (SPX→SPY, NDX→QQQ, RUT→IWM, DJX→DIA).
- **`reports/generator.py`** — new **⭐ Index Options** tab (placed right after
  Overview as the primary focus) with all columns populated + Add-trade buttons;
  `_index_strategies_section()`.
- **`config/watchlist.yml`** — added IWM, DIA (RUT/DJX proxies) + GLD, USO, TLT
  (gold / oil / bonds macro factors).
- **`tests/test_index_strategies.py`** — 4 tests (index vs stock, <$35 filter +
  profit calc, weak-move flag, lower-price/higher-volume ranking).

### Changed
- **Thresholds:** `MAX_STRATEGY_OPTION_PRICE` 50 → **35**; `min_option_profit_pct`
  default 5 → **10** (env `MIN_OPTION_PROFIT_PCT`).

### Validated
- 103 tests pass. Live index scan populated 9 strategies across IWM/USO/GLD with
  confidence, sub-$35 premiums, 8–25% profit estimates, volume, momentum, and the
  ≥5%-move gate status. Cash SPX/NDX/RUT returned no free chains → ETF proxies
  carry the tab (expected). See PENDING_ITEMS.md for the cash-index data note.

## 2026-06-04 — Strict expected-move / reward-risk candidate gate

**Why:** Research candidates were being marked bullish/bearish when current price
and target were only ~1% apart (e.g. HPE 53.69 → 54.34, +1.22%). Those are not
trade-worthy. The system must reject weak setups, never inflate targets.

### New files
- **`src/eaglesignal/analysis/candidate_gate.py`** — single source of truth.
  `evaluate_candidate(...)` computes `expected_points`, `expected_percent`,
  `min_required_points` (5 if price<100 else 10), `final_required_points =
  max(price×5%, floor)`, `reward_risk_ratio`, and returns a strict
  `validation_status` + `final_label`. A name is VALID only if
  `expected_points ≥ final_required_points` AND `expected_percent ≥ 5` AND
  `reward_risk ≥ 2:1` AND tier score thresholds. Adds the
  `rejected_insufficient_expected_move` label.
- **`src/eaglesignal/run_state.py`** — resumable checkpoint. Writes
  `data/run_state.json` after every ticker (atomic temp-file + replace) with
  run_id, stage, completed/failed/pending tickers, retry counts, error. Provides
  `backoff_seconds()` (30/60/120/300 exponential schedule).
- **`tests/test_candidate_gate.py`** — 9 tests for the price-band rule, weak-move
  rejection, expensive-stock 5% dominance, reward/risk, watchlist, high-risk.

### Changed files / functions
- **`prediction/engine.py`**
  - `_canonical_target_stop(...)` (NEW) — derives target & stop from the
    profile-horizon Monte-Carlo forecast (5D swing / 20D long / 1D intraday) on
    REAL returns. Never fabricated.
  - `predict(...)` — after the confidence ceiling, calls `evaluate_candidate`,
    OVERRIDES `final_verdict.label` + `research_action` with the gated verdict,
    and sets `validation_status`, `rejected_reason`, `candidate_gate`,
    `target_price`, `stop_price`, `expected_points`, `expected_percent`,
    `final_required_points`, `reward_risk_ratio`.
  - **Before:** any directional lean → `bullish_research_candidate` /
    `bearish_or_short_research_candidate`, regardless of move size.
  - **After:** only setups clearing the strict bar get a candidate label; the
    rest become `watchlist_only` / `no_trade` / `rejected_*`.
- **`schemas.py`** — `PredictionResult` gains `candidate_gate`, `target_price`,
  `stop_price`, `expected_points`, `expected_percent`, `final_required_points`,
  `reward_risk_ratio`, `validation_status`, `rejected_reason`.
- **`reports/generator.py`**
  - `_bull_bear(...)` now reads `validation_status` → shows
    BULLISH/BEARISH only for VALID candidates; otherwise WATCHLIST / REJECTED /
    NO TRADE with the reason. Applies to Trade Summary, Trade Strategy, Options
    Edge, Bull/Bear Verdicts (all tabs consistent).
  - Trade Summary / Trade Strategy / Verdicts now read the **authoritative**
    `p.target_price` / `p.stop_price` (no per-tab recomputation).
  - **Bull/Bear Verdicts** tab rebuilt to a 15-column strict-validation view:
    Ticker, Bull/Bear, Validation status, Current, Target, Expected pts,
    Expected %, Final req pts, R/R, Target days, Confidence, Opp, Risk, Rejected
    reason, Why.
  - `render_csv(...)` adds final_verdict, validation_status, current/target,
    expected_points/percent, final_required_points, stop, reward_risk, reason.
  - `render_markdown(...)` adds a per-ticker Verdict + Strict-gate line.
- **`pipeline.py`** — creates `run_state` at start, marks each ticker
  completed/failed, uses exponential backoff on exception retries, writes final
  state + a `run_state` summary into `RunResult.snapshots`.

### Validation
- 95 tests pass (9 new gate tests). End-to-end scan confirmed: HPE +1.22%,
  NVDA +0.43%, MSFT −0.17%, PLTR +0.04% all → REJECTED / NO_TRADE.

---

## 2026-06-04 — Column consistency + clear notes + percent profit filter
- Consistent columns (Bull/Bear, Confidence, Volume, Current, Target price,
  Target days) across Trade Summary, Trade Strategy, Options Edge, Verdicts.
- `_clear_trade_note` plain-English notes; percent-based option-profit filter
  (`min_option_profit_pct`, default 5%) with low-potential flags.

## 2026-06-04 — Market regime + factor-coverage + target days + Bull/Bear
- `analysis/market_regime.py` (risk-on/off tape + beta sensitivity),
  `analysis/factor_coverage.py` (23-group audit + honest confidence ceiling),
  per-ticker data-driven Target Days, Bull/Bear verdict column + banner.

_(Earlier history is in IMPLEMENTATION_STATUS.md.)_
