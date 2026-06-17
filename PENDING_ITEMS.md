# PENDING_ITEMS.md

Honest status of the strict-candidate-gate request. Research only.

## ✅ Completed and verified

- **Strict expected-move / reward-risk gate** (`analysis/candidate_gate.py`),
  single source of truth, applied in `predict()`.
- **Price-band rule** `final_required_points = max(price×5%, 5 if <100 else 10)`
  with 5% priority — expensive stocks correctly require >10 pts.
- **Verdict downgrade** to `watchlist_only` / `no_trade` / `rejected_*`, incl. new
  `rejected_insufficient_expected_move`.
- **No faked targets** — target derived from the profile-horizon Monte-Carlo
  forecast on real returns; weak setups are rejected, not inflated.
- **Consistency across tabs** — gate computed once, every tab/CSV/JSON/Markdown
  reads the same `PredictionResult` fields. Bull/Bear Verdicts rebuilt with the
  strict validation columns.
- **New columns** added: Validation status, Expected pts, Expected %, Final
  required pts, Reward/Risk, Rejected reason (Bull/Bear Verdicts tab + CSV).
- **Checkpoint/resume** — `data/run_state.json` (atomic, per-ticker) + retry list.
- **Exponential backoff** 30/60/120/300s on per-ticker exception retries.
- **Docs** — CHANGELOG, VALIDATION_REPORT, RUNBOOK, this file, DATA_SOURCES update.
- **Tests** — 95 pass (9 new gate tests).

## Index options — data-quality guards + open bug (2026-06-15)

The Index Options tab is now restricted to **cash index option tickers**
(SPX/NDX/RUT/VIX/XSP/XND/DJX/OEX); cash chains DO return via the CBOE delayed
endpoint. Guards added to keep the table trustworthy:
- **Profit estimate capped at +250%** — a cheap far-OTM index contract cannot
  plausibly 10–30× from a few-percent index move; the linear delta×move estimate
  over-shoots when the snapshot delta is the ATM reference. Capped + flagged.
- **ACTIONABLE requires a real directional/structured trade and confidence ≥35** —
  "no directional edge" / near-zero-confidence rows are shown as 👀 watch, never
  green.

⚠️ **OPEN BUG — mini-index underlying price scaling.** XSP/XND/DJX report the
*parent* index level (e.g. XSP ≈ SPX ≈ 7563 instead of SPX/10 ≈ 756; DJX shows the
full DJIA). This inflates index points and profit for those three tickers. Root
cause is in the price/CBOE layer (`market_data` / `options_chain`), not the
strategy builder. **TODO:** divide XSP by 10, XND/DJX by 100 (or fetch the correct
mini quote). Until fixed, the profit cap + confidence gate prevent these from
showing as ACTIONABLE, but their point/profit figures are off.

⚠️ Cash-index option **confidence is low (0–15)** because liquidity/data-quality
scoring penalises the delayed CBOE feed, so on a 5-day horizon almost no row is
ACTIONABLE. For green rows use the **20-day profile** or a paid options feed.

## Index Options Strategies focus (2026-06-04)

✅ New **⭐ Index Options** tab (`analysis/index_strategies.py`): per-strategy
confidence, premium <$35, profit ≥10%, lower-price/higher-volume/higher-momentum
ranking, strict status (underlying ≥5% AND option ≥10%), all values populate.
Thresholds set (price 35, profit 10%). Watchlist gained IWM/DIA/GLD/USO/TLT.

⚠️ **Cash-index option chains (SPX/NDX/RUT/VIX) rarely return from free sources**
(yfinance 404, CBOE delayed often empty). The tab therefore populates from the
**ETF proxies** (SPY/QQQ/IWM/DIA) and macro ETFs (GLD/USO) — which is the chosen
"both: cash → ETF fallback" behaviour. A true cash-chain feed needs a paid/licensed
provider (Cboe LiveVol, Polygon, Tradier). TODO: auto-fetch the ETF proxy chain
inside the pipeline when a cash-index chain is empty (today the proxy is sourced
because the ETF is independently in the watchlist).

⚠️ **On a 5-day horizon almost every index row shows "needs ≥5% index move"** —
you chose the strict rule *underlying ≥5% AND option ≥10%*, and indices rarely move
5% in 5 days. Run the **20-day / long-term profile** for ✅ ACTIONABLE index rows,
or relax to "option ≥10% only" if you want index-option leverage plays without
requiring a 5% index move.

## ⚠️ Partial / known limitations

1. **Full 40-column research table** — the request listed ~40 columns (Sector,
   Average Volume, Options Liquidity, Technical/Fundamental/News/OptionsFlow/
   Catalyst/MarketRegime scores as separate 0-100 fields, Invalidation Level,
   Data Sources Checked, etc.). The **strict-decision columns** are implemented on
   the Bull/Bear Verdicts tab + CSV. The remaining descriptive columns are either
   shown on OTHER tabs (component scores on Overview/Confidence; catalysts/risks in
   Why; data sources in News & Evidence) or NOT yet broken out as dedicated
   per-row fields. Not all live on one mega-table. **TODO:** add an optional
   "full research export" (CSV/XLSX) materialising every column in one sheet.

2. **Separate Catalyst Score / Options-Flow Score / News-Sentiment Score as
   0-100 fields** — currently these live inside the blended component scores
   (`component_scores`) and the options/sentiment engines, not as standalone
   normalized 0-100 columns. **TODO:** surface each as its own field on
   `PredictionResult`.

3. **Cross-process auto-resume** — `run_state.json` records completed/failed/
   pending and enables a failed-only re-run, but the pipeline does not yet
   *automatically* skip already-completed tickers from a prior aborted PROCESS and
   stitch their persisted `PredictionResult`s back in. Today's resume path is
   "re-run the scan / re-run failed tickers" (each ticker is independent and cheap
   to recompute). **TODO:** load prior run_state + persisted snapshots and continue
   in-place.

4. **Backoff scope** — exponential backoff applies to per-ticker *exception*
   retries (the likely rate-limit path). "Insufficient bars" uses the short delay.
   Attempt count is `PER_TICKER_RETRIES+1` (default 2); raise it to use the full
   30/60/120/300 ladder.

5. **Catalyst requirement for "strong"** — `has_catalyst` is currently
   `bool(catalysts)` (SEC filings + top news). A richer, typed catalyst engine
   (earnings beat, FDA, M&A, contract) would make the strong-tier gate sharper.

6. **VALID candidates are rare on short horizons** — a real 5%+ move in a 5-day
   swing window is uncommon for large caps, so most names read REJECTED. This is
   intended (quality over quantity). Run the **20-day / long-term profile** for
   more candidates; do not lower the 5% rule to manufacture them.

## ❌ Not started (explicitly out of this pass)

- Per-row **Sector**, **Average Volume**, **Options Liquidity** as dedicated
  validated columns on the candidate table.
- Dedicated **XLSX** research export.
- Live broker / order integration (intentionally never — research only).

## Failed tickers / providers (last run)

See `data/run_state.json` → `failed_tickers`. Common transient failures:
GDELT (read timeout), Ollama localhost (dGPU down → lexicon fallback),
StockTwits (Cloudflare), Reddit (auth wall) — all degrade gracefully.
