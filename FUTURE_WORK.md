# EagleSignal AI — Future Work & Roadmap

> **Research tool, not financial advice.** This document is the consolidated backlog of
> planned/proposed work. It is the single source of truth for "what's next" — nothing
> here is implemented unless explicitly marked ✅ DONE. Last compiled: 2026-06-02.

**Effort legend:** `S` = quick (<1h hands-on) · `M` = 1–3h · `L` = ~half-day+ · `XL` = multi-day project.
**Status:** 🔲 planned · 🟡 partially done · ✅ done · ⏳ has a calendar/data lead-time.

---

## 0. Keystone: Historical Data Foundation ⭐ (unlocks most of the rest)

Today the engine can only *honestly* backtest/tune the **price-history-derived** engines
(technical, price/volume, forecast, cross-market) because those are the only inputs we
have point-in-time history for. Everything else (fundamentals, options, macro, sentiment,
news) uses **today's** snapshot — fitting them historically would be lookahead bias. A
historical data store is the single biggest enabler: it lights up full backtesting, IV
Rank, options analytics, and a real ML model.

| # | Item | Effort | Status | Why it matters |
|---|---|---|---|---|
| 0.1 | **Daily IV snapshot logger** — persist each scan's per-ticker implied volatility so IV history accumulates | M | ✅ DONE ⏳ | `historical_store.py` appends `data/historical_snapshots/iv_snapshots.jsonl`. Needs ~20–60 sessions before IV Rank is meaningful. |
| 0.2 | **Point-in-time snapshots** of fundamentals, macro, sentiment, news, options at each scan | L | 🟡⏳ | Compact prediction/run snapshots plus evidence-source snapshots now persist; full raw provider payload archiving is still pending. |
| 0.3 | **Historical options chains** store (strikes, IV, OI, volume, Greeks over time) | L | 🟡⏳ | Selected expiry/contract snapshots now persist to `options_chain_snapshots.jsonl` and power exact-contract OI-change comparisons; full every-strike raw chain history still pending. |
| 0.4 | **Earnings & corporate-event calendar** (historical + forward) | M | ✅ DONE | `ingestion/earnings.py` (keyless yfinance, graceful fallback) wires next-earnings date into the engine + options analysis; powers §1.5. Historical event store still pending. |
| 0.5 | **Feature/label store** built from point-in-time live scans | L | ✅ DONE ⏳ | `feature_snapshots.jsonl` now stores label-free model features per prediction; `/reliability/labels` joins matured forward labels without lookahead. GPU ML still needs enough accumulated rows. |
| 0.6 | **Time-series storage** decision (Parquet files vs SQLite/DuckDB vs a TSDB) | S–M | 🔲 | Architecture for 0.1–0.5; keep it simple (Parquet/DuckDB) first |
| 0.7 | **Live recommendation outcome tracking** — log every issued call + realized forward result for a true hit-rate scorecard | M | ✅⏳ | `/reliability/scorecard` evaluates matured equity snapshots; `/reliability/options-scorecard` evaluates option-premium P/L from future stored contract marks. Fresh calls stay pending until forward data exists. |

**Lead-time note:** 0.1 and 0.2 produce no value on day one — they must *accumulate*. Stand
them up early so the data is ready when the dependent features (IV Rank, full tuning, ML) land.

---

## 1. Options Intelligence Upgrade (ADR-003)

Fix for "the recommendation went down" — the engine currently models DTE buckets, absolute
IV, liquidity, spread, and flow, but has **no real Greeks, no IV-Rank, no IV-crush timing**,
and its sub-7-DTE penalty is too soft.

| # | Item | Effort | Status | Notes |
|---|---|---|---|---|
| 1.1 | **Black-Scholes Greeks** (delta/gamma/theta/vega) on the reference contract + surface on Options Edge | M | ✅ DONE | Quantifies "move needed vs daily decay"; surfaced in Options Edge. |
| 1.2 | **Harden short-DTE handling** + auto-prefer spreads on risky setups | S | ✅ DONE | Options Edge now enforces `MIN_OPTION_DAYS_TO_EXPIRY=5` by default, so sub-5-DTE expiries are not considered; 5–6 DTE setups remain heavily gated/paper-only when risk is high. |
| 1.3 | **Realized-vs-implied vol** ratio ("are these options expensive?") | S–M | ✅ DONE | Uses 20D realized volatility vs chain IV and gates expensive long-premium setups. |
| 1.4 | **IV Rank / IV Percentile** (relative IV — the true crush signal) | M | ✅⏳ | Implemented from stored IV snapshots and surfaced in Options Edge; needs ~20+ stored observations before it becomes available per ticker/expiry. |
| 1.5 | **Earnings/event IV-crush detection** wired from the event radar | M–L | ✅ DONE | Any long-premium expiry that brackets the next earnings date is flagged and capped to defined-risk/credit structures (harsher inside 5 days). |
| 1.6 | **Premium-selling strategies** (credit spreads, covered calls) for high-IV/low-move names like AMAT | M | ✅ DONE | Rich-IV setups now surface a bull-put / bear-call **credit spread** (and an iron condor for neutral high-IV) as the preferred structure over buying premium. |
| 1.7 | **Richer multi-leg structures** (verticals beyond debit, iron condors) with max-gain/loss/breakeven | M | ✅ DONE | Spreads now carry est. net debit/credit, max gain, max loss, and breakeven; iron condor added for neutral high-IV. Values are 1σ-width estimates, not live multi-leg quotes. |
| 1.8 | **Skew, term structure, chain-derived UOA, and OI-change** | M | ✅ DONE ⏳ | Options Edge now computes ATM IV skew, next-expiry IV slope, chain-derived unusual-activity score, and exact-contract OI change from stored snapshots. Needs accumulated scans; paid institutional unusual-flow/gamma feeds remain future upgrades. |
| 1.9 | **Index-options-only execution lane** | S | ✅ DONE | Options Edge/strategy promotion now only shows SPX, XSP, NDX, XND, RUT, VIX, DJX, and OEX; equity options remain disabled for trade recommendations. Index-option ideas also require `MIN_INDEX_OPTION_MOVE_POINTS=50` by default. |

---

## 2. Prediction Engine — measured, not guessed

| # | Item | Effort | Status | Notes |
|---|---|---|---|---|
| 2.1 | **Backtest-driven weight tuning (ADR-002)** — walk-forward, no lookahead, writes `weights.fitted.yml` | L | ✅ DONE | Live; tunes price-derived engines only |
| 2.2 | **Weekly auto re-tune** wired into scheduled jobs | S | ✅ DONE | `eaglesignal auto-tune`, `/jobs/tune`, `run_weekly_tune_job.ps1`, and `EagleSignalAI-WeeklyRetune` task installer path added. |
| 2.3 | **Multi-horizon tuning** — tune `intraday` at 1D, swing-family at 5D, long_term at 20D separately | M | ✅ DONE | `tune_multi_horizon()` groups profiles by natural horizon (`PROFILE_HORIZON_DAYS`) and replays each once; weekly auto-retune now uses it so `intraday` is fitted at 1D. |
| 2.3a | **Near-term 2D/3D forecast bands** for short-term/options review | S | ✅ DONE | New scans persist `short_horizon_forecasts` with 2D and 3D Monte-Carlo P(up), median return, and p05/p95 bands beside the main horizon forecast. |
| 2.4 | **Tune the non-price engines** (fundamentals/options/macro/sentiment) | L | 🟡⏳ | Feature rows now persist; tuning still needs enough matured labels plus no-lookahead calibration tests. |
| 2.5 | **Full-prediction backtest + accuracy scorecard** (not just technical) | L | 🟡⏳ | Equity/options scorecard endpoints are live and data-dependent; full walk-forward multi-factor calibration and GPU ML promotion gates remain. |
| 2.6 | **Event-aware confidence** — reduce/flag confidence near high-impact scheduled events (FOMC/jobs/CPI/earnings) | M | ✅ DONE | New `ingestion/calendars.py` (FOMC + rule-based macro + earnings); engine applies a 0.85 confidence haircut + event-risk warning + invalidation when a high-impact event falls inside the horizon. Surfaced in `confidence_trace.event_calendar` and `/calendar`. |
| 2.7 | **Broad stock-market prediction engine** | M | ✅ DONE | `analysis/stock_market_engine.py` combines market regime, VIX, WTI oil, dollar, global correlations, government/policy/geopolitical clues, scheduled calendar risk, and market-wide HN/Seeking Alpha headlines into one traceable broad-tape score. |

---

## 3. Sentiment & Data Sources

| # | Item | Effort | Status | Notes |
|---|---|---|---|---|
| 3.1 | **Reddit OAuth** (official, free) so social works from datacenter/container IPs | M | 🔲 | **Your step:** create a free Reddit app (client id/secret) |
| 3.2 | **Residential/ISP proxy** support for StockTwits/Reddit when blocked | S | ✅ DONE | `EAGLESIGNAL_HTTP_PROXY` added; StockTwits Cloudflare must NOT be bypassed |
| 3.3 | **Upgrade sentiment NLP** from bag-of-words lexicon to a real model (LLM/transformer, GPU) | M–L | ✅ DONE | `analysis/llm_sentiment.py` scores headlines via local Ollama (GPU) when `ENABLE_LLM_SENTIMENT=true` + Ollama reachable; always falls back to the lexicon. Surfaced at `/advisor/health`. |
| 3.4 | **X/Twitter via official API** (pay-per-use ~$0.005/read, or legacy Basic) | S code | 🔲 | **Your decision:** costs money; code already key-gated by `X_BEARER_TOKEN` |
| 3.5 | **X read-cost counter** + 1×/day gating to cap spend if X is enabled | S | ✅ DONE | `data/x_api_usage.json` counts daily reads + est. cost; `X_DAILY_READ_BUDGET` (default 50, 0=off) blocks further paid calls once hit. |
| 3.6 | Keyless legal substitutes (Bluesky + Mastodon) | — | ✅ DONE | Already live |

---

## 4. GPU Acceleration (RTX 5060 Laptop, 8 GB, Blackwell sm_120)

> The daily scan is **network-bound**, so GPU won't speed it up. GPU pays off for the LLM
> advisor, Monte-Carlo/backtesting, and a future ML model.

| # | Item | Effort | Status | Notes |
|---|---|---|---|---|
| 4.1 | **Phase 1 — Local LLM advisor (Ollama on GPU)** | S | ✅ DONE | Ollama installed + `llama3.2:3b` pulled (2GB, fits 8GB VRAM) + verified (inference returns sensible scores). `.env` set `ADVISOR_PROVIDER=ollama` / `ENABLE_LLM_SENTIMENT=true`; `/advisor/health` reports `active_backend=ollama, reachable=true` on host AND container (via `host.docker.internal`). |
| 4.2 | **Phase 2 — GPU Monte-Carlo** (`monte_carlo()` via CuPy + CPU fallback) | M | ✅ DONE | Optional `ENABLE_GPU_MONTE_CARLO=true` uses CuPy when installed and falls back to NumPy CPU; `MONTE_CARLO_PATHS` controls path count and is now passed directly from the prediction engine into the forecast component. |
| 4.3 | **Phase 3 — GPU-trained ML model** (XGBoost/LightGBM GPU, optional PyTorch) | XL | 🔲 | The real accuracy lever. Depends on §0.5 feature store + §0.2 snapshots |
| 4.4 | **NVIDIA Container Toolkit** setup if the *containerized* app needs the GPU (`--gpus all`) | S–M | 🔲 | WSL2 already sees the GPU; native venv use is simpler to start |

### 4A. GPU + AI Reliability Upgrade

GPU acceleration should make the platform faster where the work is compute-heavy, but it will not
make markets perfectly predictable. The honest target is not "100% accurate predictions"; it is a
system that is highly reliable in data collection, retry/fallback behavior, source traceability,
confidence calibration, risk gating, paper-trade outcome tracking, and post-trade learning.

| # | Item | Effort | Status | Why it matters |
|---|---|---|---|---|
| G.1 | **Verify NVIDIA runtime** with `nvidia-smi`, CUDA, and Docker GPU access | S | 🟡 | Ollama runs on the host GPU and is reachable from the container via `host.docker.internal`. Native CUDA/CuPy-in-container verify still pending (only needed for §4.2/§4.3). |
| G.2 | **Ollama GPU advisor** for local ticker/news/options reasoning | S–M | ✅ DONE | Live + verified: advisor + headline-sentiment both call local Ollama (`llama3.2:3b`); `/advisor/health` confirms reachable on host and container. |
| G.3 | **GPU news/sentiment classifier** | M | ✅ DONE | `analysis/llm_sentiment.py` (Ollama, opt-in, lexicon fallback); wired into the sentiment engine. |
| G.4 | **GPU Monte-Carlo for equities + options** | M | ✅ DONE | Forecast Monte Carlo has optional CuPy acceleration, deterministic CPU fallback, and settings-wired path/GPU controls. |
| G.5 | **Historical feature store + GPU ML model training** | XL | 🔲⏳ | Main path toward measurable accuracy improvement; depends on §0.2/§0.5 |
| G.6 | **Similar-event memory using embeddings/RAG** | L | 🔲 | Finds SNDK-like breakout/exhaustion setups and past event analogs |
| G.7 | **Reliability scorecard** for hit rate, option P/L, false positives, false negatives | M–L | ✅⏳ | `/reliability/scorecard`, `/reliability/options-scorecard`, `/reliability/calibration`, and `/reliability/labels` are live; values mature as forward bars/option marks accumulate. |
| G.8 | **Model ensemble**: rules + ML + LLM explanation + risk gate | L | 🔲 | More robust than trusting one model or one confidence number |

Recommended GPU sequence:

1. Verify GPU access on the laptop and Docker.
2. Wire Ollama GPU advisor first.
3. Start historical snapshots immediately.
4. Add GPU sentiment/news classifier.
5. Add GPU Monte-Carlo.
6. Build the feature store.
7. Train GPU ML models.
8. Add the reliability dashboard so every recommendation is judged after the fact.

---

## 5. Remote Access & Deployment

| # | Item | Effort | Status | Notes |
|---|---|---|---|---|
| 5.1 | **HTTP Basic login** on the API (env-gated, localhost/LAN exempt, tunnel enforced) | M | ✅ DONE | `DASHBOARD_USER`/`DASHBOARD_PASSWORD` |
| 5.2 | **Quick Cloudflare tunnel** (temporary `trycloudflare.com` URL) | S | ✅ DONE | Ephemeral; for testing |
| 5.3 | **Permanent named tunnel + `cloudflared service install`** (fixed URL, auto-start on boot) | S | 🔲 | **Your step:** `cloudflared tunnel login` needs your Cloudflare domain |
| 5.4 | *(Alt)* **Tailscale** (private, no domain needed, auto-start) | S | 🔲 | Install app on phone; choose this OR 5.3 |
| 5.5 | **Cloudflare Access** second auth layer (email/Google) | S | 🔲 | Optional belt-and-suspenders on the public URL |
| 5.6 | **LAN auth lockdown** option (require login on LAN too; host-networking/trusted-proxy) | S–M | ✅ DONE | `DASHBOARD_REQUIRE_LOGIN_ON_LAN=true` enforces login for non-loopback LAN clients; localhost/loopback stays exempt. (Loopback detection needs host networking, not Docker bridge.) |
| 5.7 | **24/7 cloud deploy** (VPS/Fly.io/Render) if laptop-off uptime ever needed | L | 🔲 | Moves secrets/scans to cloud; out of scope for now |

---

## 6. Security & Operations

| # | Item | Effort | Status | Notes |
|---|---|---|---|---|
| 6.1 | **`docker compose build`** to bake current `.py` changes (auth, tuning, proxy, CLI) into the image | S | ✅ DONE | Image rebuilt 2026-06-02 incl. earnings/IV-crush, premium-selling, multi-horizon tuning, X cost guard, LAN lockdown; `/health` ok, dashboard 200. Re-run after future `.py` edits. |
| 6.2 | Keep **`.env` git-ignored**; secrets only via env vars | — | ✅ ongoing | Never commit credentials/keys |
| 6.3 | **Rotate the generated dashboard password** to something memorable | S | 🔲 | **Your step** |
| 6.4 | Compliance guardrails (no insider/non-public data; respect ToS/robots/rate limits; no paywall bypass) | — | ✅ ongoing | Non-negotiable; must persist |

---

## 7. Maintenance & Housekeeping

| # | Item | Effort | Status | Notes |
|---|---|---|---|---|
| 7.1 | **Market-holiday + half-day calendars** kept current beyond 2026 | S | ✅ DONE | 2026–2028 full holidays + half-days in the dashboard clock (+ 2029-01-01 boundary); extend annually. |
| 7.2 | **Options price coverage** — some expiries still show "—" when source returns no ATM quote | S | 🟡 | Improved via fresh scans; add more source fallbacks |
| 7.3 | **Docs upkeep** (README/ARCHITECTURE/DATA_SOURCES + this file) as features land | S | ongoing | — |

---

## Recommended sequencing & totals

**Batch 1 — Quick, high-value (~1 day):**
§6.1 rebuild · §4.1 Ollama advisor · §1.2 DTE fix · §1.3 realized-vs-implied · §1.7/1.6 spread+sell logic ·
§5.3 or §5.4 permanent remote access · **§2.2 weekly re-tune done** · **start §0.1 + §0.2 data logging now (lead-time).**

**Batch 2 — Medium (~1 day):**
§1.1 Greeks · §1.5 earnings IV-crush · §4.2 GPU Monte-Carlo · §3.1 Reddit OAuth · §3.3 better sentiment.
*(§1.4 IV-Rank lights up once §0.1 history matures over a few weeks.)*

**Batch 3 — Strategic (~2–3 days):**
§0.5 feature store · §4.3 GPU ML model · §2.4 non-price tuning · §2.5 full-prediction scorecard.
*(The genuine "highest accuracy" upgrade; depends on the Historical Data Foundation.)*

**Grand total: ~4–5 days focused implementation.** Longest *calendar* dependency = IV-Rank/
historical snapshots (weeks to accumulate) → **begin §0.1/§0.2 first.**

### Blockers only you can clear
1. ~~Install **Ollama** + pull a model (§4.1).~~ ✅ DONE 2026-06-02 — Ollama installed, `llama3.2:3b` pulled, advisor + GPU sentiment active.
2. **Cloudflare domain login** for the permanent tunnel, or install **Tailscale** (§5.3/§5.4).
3. Create a **Reddit app** for OAuth (§3.1).
4. Approve **CUDA/CuPy/XGBoost** installs for the Blackwell GPU (§4.2/§4.3).
5. Decide on **paid X/Twitter API** spend (§3.4).
6. Rotate the **dashboard password** (§6.3).
