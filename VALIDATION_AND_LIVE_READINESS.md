# Validation and Live Readiness Review

Review date: 2026-06-02

> **2026-06-02 focused-universe update:** AAPL, MRVL, and QBTS were added as active public watchlist targets; INTC, GOOGL, MSFT, AMZN, META, and AAPL cover the requested Intel/Google/Microsoft/Amazon/Meta/Apple names. Groq remains private AI-inference context only. Pipeline workers now retry transient per-ticker failures, and Options Edge keeps expandable expiry rows grouped during sorting.

> **2026-06-02 historical-foundation update:** successful pipeline runs now persist point-in-time prediction snapshots, options-expiry snapshots, and IV snapshots under `data/historical_snapshots`, with API visibility through `/snapshots/status`. This does not change scoring; it starts the data accumulation needed for IV Rank, full scorecards, feature stores, and no-lookahead tuning.

> **2026-06-02 roadmap-continuation update:** IV Rank/Percentile is wired into Options Edge from accumulated IV snapshots, selected options-chain and evidence snapshots now persist, `/reliability/scorecard` evaluates matured prediction snapshots, `/jobs/tune` and `eaglesignal auto-tune` support weekly ADR-002 retuning, and optional CuPy GPU Monte-Carlo is available through `ENABLE_GPU_MONTE_CARLO=true`.

> **2026-06-03 GPU/options tightening update:** `ENABLE_GPU_MONTE_CARLO` and
> `MONTE_CARLO_PATHS` are now passed directly from settings into the forecast
> engine, not just read opportunistically from the environment. Options Edge now
> enforces `MIN_OPTION_DAYS_TO_EXPIRY=5` by default in collection, scoring, refresh
> jobs, and dashboard rendering, so stale reports cannot display under-5-DTE
> recommendation rows. New scans also store 2D and 3D Monte-Carlo forecast bands
> beside the main horizon forecast for short-term/options review.

> **2026-06-03 options analytics fix:** Options Edge now includes chain-derived
> ATM IV skew, term-structure slope, unusual-activity score, and exact-contract
> OI-change versus the latest stored option snapshot. These are real chain/snapshot
> analytics, not a paid institutional unusual-flow feed. Remaining options gaps
> are paid flow/gamma vendors, full every-strike raw chain history, option-premium
> outcome calibration, and full multi-factor no-lookahead options backtesting.

> **2026-06-02 options-intelligence + ops update:** added a keyless earnings calendar (`ingestion/earnings.py`) feeding **earnings IV-crush gating** — long-premium expiries that bracket the next earnings date are capped to defined-risk/credit structures. The options engine now suggests **premium-selling** (bull-put/bear-call credit spreads, neutral iron condors) for rich-IV names instead of only buying, and every vertical carries est. net debit/credit, max gain, max loss, and breakeven. Weight tuning is now **multi-horizon** (intraday=1D, swing=5D, long-term/index=20D). Added an **X API daily read-cost guard** (`X_DAILY_READ_BUDGET`), an opt-in **LAN login lockdown** (`DASHBOARD_REQUIRE_LOGIN_ON_LAN`, loopback exempt), and 2026–2028 market holiday/half-day calendars. Full suite 60 passed; Docker image rebuilt and verified (`/health` ok, dashboard 200). These estimates are research-only 1σ approximations, not live multi-leg quotes; no automated real-money trading.

> **2026-06-01 engine re-validation (live scan, 38 names):** all 8 component engines populated 38/38 (technical_structure, price_volume_momentum, fundamentals, options_intelligence, macro_regime, sentiment, cross_market_correlation, ensemble_forecast). Per-signal source freshness confirmed live: market_data=yfinance 38/38, macro=available 38/38, government=available 38/38, options=available 38/38, news 28–50 items/name (avg 36.9) from google_news + yahoo_rss + yfinance + gdelt. Sentiment used the labelled `news_derived` fallback for all 38 because X/StockTwits/Bluesky are IP-blocked from this datacenter container (works residential or with `X_BEARER_TOKEN`). `missing_data` empty for scored names. Test suite 39/39 green. Manual Trade Journal add/edit/delete live in the dashboard. No code defects found in source coverage; the only non-live path is social-stream IP blocking, which degrades gracefully to real multi-source news sentiment.

This file validates the current EagleSignal AI project against the requested USA stock exchange prediction scope:

- U.S. equities, options, ETFs, and indexes only.
- Analyze only the user-provided watchlist, not random companies.
- Combine market data, options, SEC/fundamentals, macro, government, news, social sentiment, cross-market, risk, reports, backtesting, and alerts.
- Borrow the best ideas from the referenced GitHub projects without copying blindly.
- Be deployable in Docker Desktop.

> Research only. This project must never promise guaranteed returns or automate real-money trading without a separate, heavily controlled compliance and risk design.

## Executive Verdict

The project is a strong MVP scaffold, not yet a fully live institutional-grade prediction product.

Already present:

- Watchlist-scoped analysis through `config/watchlist.yml`.
- Default active watchlist is now intentionally focused on SPY/QQQ market context plus MU, AMD, AVGO, NVDA, INTC, AAPL, META, GOOGL, AMZN, TSM, ASML, LRCX, SMCI, DELL, HPE, WDC, AMAT, OKLO, PLTR, ISRG, RKLB, SNDK, MRVL, and QBTS. It should not scan all scripts by default. Groq is private context only, not an active ticker.
- CLI, FastAPI, Dockerfile, Docker Compose, GitHub Actions, reports, tests, and skill registry.
- Live-capable connectors for market data through yfinance, SEC EDGAR, FRED, NewsAPI/yfinance news, and yfinance options chains.
- Market-data fallback chain: yfinance -> Stooq daily history -> local cache from prior successful real download -> unavailable. No synthetic runtime prices are used.
- Technical indicators, fundamentals, options analytics, macro scoring, headline sentiment, cross-market comparison, risk blocking, backtest command, HTML/Markdown/JSON/CSV reports, and alert deduplication.
- Current-price snapshots for each analyzed script/ticker, including previous close, day change, volume, source, and retrieval time.
- Dummy paper-trade tracking in `data/paper_trades.json` so directional, non-blocked signals can be marked against later live price checks without placing broker orders.
- A tabbed dashboard with Overview, Current Prices, Why Suggested, News & Evidence, Paper Trades, and MD Validation views.
- Trends & Impact tab showing price move, news count/providers, evidence polarity, policy links, social signal, and forecast tilt.
- Bull/Bear Verdicts tab showing final research action for bullish, bearish/short, watch-only, and avoid candidates.
- Event Radar tab for SNDK-style moves: 20D/60D/252D acceleration, volume expansion, catalyst/policy density, drawdown from recent high, and exhaustion risk.
- Confidence Traces tab linking confidence to coverage/agreement math, available/missing engines, `/ticker/{symbol}`, `/signals`, and top source URLs.
- Options Edge tab showing short-term options bias, defined-risk strategy idea, nearest expiration, reference contract, put/call, IV, OI, volume, and warnings.
- Sortable tables across dashboard tabs.
- Theme Watchlists tab now includes live verdict/trend columns for scored symbols.
- Jobs tab plus `/jobs/run`, `/jobs/status`, `python -m eaglesignal collect`, and `scripts/install_windows_task.ps1` for browser/manual and every-two-hours local scheduled collection with retry.
- Manual Trades tab and `/manual-trades` API for user-entered trade price, quantity, note, current mark, and P/L tracking.
- Trump/admin policy lens in government news ingestion plus `POLICY_THEME_WATCHLISTS.md` and `config/policy_theme_watchlists.yml`.
- `MARKET_FACTOR_CHECKLIST.md` added as the required 23-factor analysis checklist for prediction and recommendation coverage.
- `config/analysis_source_registry.yml` added as an additive source-priority registry covering dashboard/reference tools, official primary sources, options/volatility/sentiment sources, news flow, paid institutional platforms, and automation APIs.
- Documentation files for motivation, workflow, architecture, data sources, skills, roadmap, requirements, `.env`, `.gitignore`, Docker, and license.

Recently implemented (2026-05-31 expansion):

- Multi-provider market-data fallback: yfinance → Finnhub → Tiingo → Alpha Vantage → Stooq → local cache, config-driven via `MARKET_DATA_PROVIDER_CHAIN`, with per-provider status in reports. No synthetic runtime prices.
- Multi-source news merge with dedup: NewsAPI + GDELT (keyless, throttled) + yfinance + StockTwits links.
- Government/fiscal/policy connector (`ingestion/government.py`): Treasury FiscalData (avg interest rate), BLS (CPI + unemployment), White House presidential-actions RSS, Federal Register (presidential documents), **openFDA drug + device recalls**, **DOJ Antitrust + FTC actions** (Federal Register agency filter), and GDELT policy news — all keyless except optional `BLS_API_KEY`. Events are categorized (policy/fiscal/labor/fda/antitrust/trump_admin), folded into the macro regime, and stored as MARKET evidence.
- Social sentiment connector (`ingestion/social.py`): StockTwits bull/bear labels and Reddit lexicon classification, capped to ±15 points so a viral post cannot dominate.
- Ensemble forecast engine (`analysis/forecast.py`): Monte-Carlo GBM bands (p05/median/p95, prob_up) seeded from real returns, plus turtle/MA/momentum trend-agent votes — borrowed conceptually from the two deep-learning repos, pure NumPy, unit-tested.
- Shared rate-limit manager (`ingestion/http_util.py`, SKILL-172) honoring GDELT's one-request/5s rule.
- Sector/ticker policy-impact mapper (`analysis/impact.py`, SKILL-056): links FDA recalls, DOJ/FTC actions, and policy headlines to the specific watchlist names they affect (direct brand-token match + thematic sector match), surfaced as `policy_impacts`, ticker evidence, and event-risk warnings. Conservative by design — unrelated regulatory actions do not attach.

Recently implemented (2026-05-31 confidence + options + UX pass):

- **Confidence redefined as conviction in an actionable BUY/SELL** (`analysis/scoring.py`): confidence = `evidence_quality × (0.15 + 0.85 × directional_conviction)`. A neutral setup (opportunity ≈ 50) now scores low confidence by design; high confidence requires a clear directional lean backed by good, agreeing data. `avoid` is capped ≤30 and `neutral` ≤40. `evidence_quality()` (the old coverage+agreement math) still feeds the risk manager. Unit-tested (`test_neutral_confidence_is_low_even_with_agreement`, `test_conviction_zero_at_neutral_full_when_directional`).
- **Confidence Traces tab** now states the Call (BUY / SELL / NO TRADE), directional conviction %, and data-quality %, so the user never has to act on a high-confidence neutral again.
- **Multi-source, multi-expiry options** (`ingestion/options_chain.py`): yfinance primary with a **keyless CBOE delayed-quotes JSON fallback**; up to 5 short/medium-dated expirations collected per name; winning source recorded.
- **Top-3 expirations by confidence** (`analysis/options.py::analyze_expiries`): each expiry scored on conviction × liquidity × IV penalty × DTE factor ± options-flow agreement; surfaced with a plain **BUY CALL (up ▲)** / **BUY PUT (down ▼)** / **NO TRADE (→)** call and a green/orange/red traffic-light color in the Options Edge tab. The tab now enforces a default **5-DTE minimum**, and also shows underlying current price, exact expiry contract/premium, bid/ask, lot size, volume, call/put volume, OI, P/C, IV/RV, IV Rank/Percentile when enough snapshots exist, and an Add option button. Manual Trades refreshes the selected option contract premium by expiry instead of marking it with the underlying equity price. Algorithmic confluence (0–5) blends trend/momentum/forecast/opportunity/flow.
- **Options Risk Gate** (`analysis/options.py::analyze_expiries`): option-contract confidence now passes through a stricter gate using underlying direction, data quality, algorithmic confluence, exact-contract volume/OI, DTE, bid/ask spread, premium % of spot, IV vs 20-day realized volatility, approximate Black-Scholes delta/gamma/theta/vega, and breakeven. Sub-7-DTE naked options, high-IV/high-premium contracts, low-volume contracts, wide spreads, and high theta bleed are downgraded to **spread only**, **paper only**, or **no trade**. Direct dashboard **Add option** appears only for high-gate rows.
- **Optional local Ollama advisor** (`advisor.py`): the AI Advisor can use a local Ollama model when `ADVISOR_PROVIDER=ollama` or `OLLAMA_BASE_URL` is set. This is explanation-only over the real signal JSON; deterministic scoring and source-linked evidence remain the prediction source of truth.
- **Trump/admin & regulatory clues** are now surfaced directly in the final-verdict reasons.
- **Why Suggested** cards carry a deep news/events/source digest with hyperlinks and cross-tab navigation to the same ticker; every tab is one shared `PredictionResult`.
- **Dashboard UX**: active tab persists across reloads (URL hash + `localStorage`), so a refresh no longer snaps back to Overview. A sticky toolbar on every tab provides **↻ Reload**, **⟳ Live prices** (`/prices/refresh`, patches Overview/Prices cells in place), and **▶ Re-scan** (full live re-scan via `/jobs/run`, auto-reload on completion).
- **Scheduled tasks split** into small independent Windows jobs (`scripts/install_windows_tasks_split.ps1`): logon scan, full scan every 2 hours, 09:35 morning brief, and a 30-minute intraday light refresh.
- **Parallel category refresh** (`refresh.py`): the Jobs tab fans source categories out **concurrently in a thread pool** from one **Refresh ALL** button, with per-category buttons too. Core live groups include market, news, social, X/Twitter, government, Trump/admin, political/geopolitical, macro, and global; expanded coverage groups include official economic, company events, options/volatility, reference dashboards, automation APIs, paid platforms, and source registry. Endpoints `POST /jobs/refresh-all` (optional `analyze=true` chains the prediction pipeline), `POST /jobs/refresh/{category}`, `GET /jobs/refresh-status`. The three government-derived categories share one cached GDELT-throttled fetch. Each summary now shows latest item/source or source-readiness status.
- **Expanded grouped refresh coverage** (`refresh.py`, 2026-06-01): Jobs now also include `official_economic`, `company_events`, `options_volatility`, `reference_dashboards`, `automation_apis`, `paid_platforms`, and `source_registry`. Implemented sources are pulled live where available; manual/reference, paid, API-gated, and planned sources are still represented in the status table so the product records what was considered, skipped, or needs credentials.
- **Scheduled/manual collection alignment** (`jobs.py`): `/jobs/run`, `python -m eaglesignal collect`, and Windows scheduled scripts now run grouped parallel refresh first, then the prediction pipeline. This keeps manual browser refresh and automated laptop-on jobs on the same process.
- **Parallel analysis and live refresh cadence** (`pipeline.py`, `api.py`, dashboard JS): focused watchlist tickers are analyzed with parallel workers after shared macro/government/global context is collected; transient per-ticker failures retry inside each worker; `/prices/refresh` fetches current prices concurrently; the dashboard auto-refreshes live prices every 10 minutes and grouped source jobs every 30 minutes while open.
- **Manual trade controls** (`manual_trading.py`, dashboard JS): rows can be added from the form or directly from Overview/Options Edge at the current displayed entry price, then edited or deleted from the Manual Trades tab.
- **Trump/Administration policy basket is now actively scored**: DJT, BAH, LMT, RTX, NOC, GD, GE, SMR, CEG, VST, TSLA, LUNR, ASTS, ORCL, MSFT added to `config/watchlist.yml`; AAPL, MRVL, and QBTS are also active focused AI/options targets (41 names total).
- **Keyless live macro** (`macro_fred.py`): without `FRED_API_KEY`, macro now pulls a real regime from yfinance proxies (^TNX/^FVX/^TYX yields, ^VIX, WTI, dollar index) + Treasury FiscalData, so the macro signal is never empty. FRED stays primary when a key is present.
- **News-derived sentiment fallback** (`social.py`): when StockTwits/Reddit are IP-blocked and X has no token, sentiment is computed from live multi-source news-headline polarity (capped, clearly labelled `news_derived`) so the Sentiment category always pulls real, recent data and feeds analysis.
- **Keyless real-time microblog sources** (`social.py` + `news.py`): added **Bluesky** (AT Protocol `searchPosts`, keyless public) and **Mastodon** (public hashtag timeline) as legal, real-time substitutes for unauthenticated X reads — they feed both news items and sentiment. Source order: X(token)→StockTwits→Bluesky→Mastodon→Reddit→news-derived. Bluesky may be 403'd from datacenter IPs (works residential); Mastodon works everywhere; both degrade gracefully. We never scrape X or bypass any access control.
- **Manual Trade Journal CRUD**: full add/edit/delete with live P/L re-marking. `update_manual_trade`/`delete_manual_trade` in `manual_trading.py`; `PUT /manual-trades/{id}` and `DELETE /manual-trades/{id}`; dashboard inline edit + delete buttons. Verified end-to-end (create→edit→delete→404).

Still missing or incomplete for the full vision:

- Live X/Twitter ingestion remains key-gated and off by default; StockTwits/Reddit may be IP-blocked on cloud hosts (work locally / with a token).
- BEA, Census, Federal Reserve speech/minutes feeds, CME FedWatch, Congress, DOD/SAM.gov/USAspending, EIA, OFAC, ISM/PMI, AAII, and Cboe market-statistics connectors are not yet fully implemented (FDA recalls and DOJ/FTC actions are now implemented).
- Company investor relations, earnings calendars, transcripts, analyst revisions, press releases, contracts, lawsuits, and product events are not first-class connectors yet.
- Options analytics are now stronger than the original MVP: IV rank/percentile
  (data-dependent), approximate Greeks, spread/liquidity gates, earnings IV-crush
  logic, ATM IV skew, term-structure slope, chain-derived unusual activity, and
  exact-contract OI-change are implemented. Paid institutional unusual-flow/gamma
  vendors, full every-strike raw chain history, and option-premium calibration
  are still incomplete.
- The ensemble forecast is a transparent statistical model (Monte-Carlo + agents), not a trained/calibrated neural net with a model registry.
- Source freshness and reliability are recorded per evidence record but not yet hard-enforced as trade gates on every component.
- `/dashboard` serves the latest generated dashboard quickly; live prices can now be patched in place via the toolbar **⟳ Live prices** button (`/prices/refresh`) without a full re-scan, but fresh news/options still require a **▶ Re-scan**.

## Watchlist Scope Validation

Current behavior:

- `config/watchlist.yml` defines the default assets.
- `src/eaglesignal/config.py` loads the watchlist, removes duplicates, normalizes tickers to uppercase, and assigns asset types.
- `src/eaglesignal/pipeline.py` analyzes only the loaded watchlist unless `--tickers` or the API `tickers` parameter is provided.
- `src/eaglesignal/pipeline.py` runs ticker analysis in parallel and retries transient per-ticker failures before skipping a symbol.
- `STRICT_WATCHLIST_ONLY=true` is the default. If CLI/API tickers include symbols not in the watchlist, those symbols are ignored unless strict mode is disabled.
- Company names and exchanges are preserved from the watchlist and used by the news connector where supported.

Required hardening still remaining:

- Add asset classes for `index`, `index_proxy_etf`, and `option_contract` explicitly. Today SPY/QQQ/IWM are ETF proxies for indexes.
- Add exchange validation for U.S.-listed securities only.

## Requirement Coverage Matrix

| Requested capability | Current status | Evidence in repo | What to add next |
|---|---|---|---|
| Analyze only listed indexes/scripts/equities/company names | Implemented-partial | `config/watchlist.yml`, `load_watchlist`, `STRICT_WATCHLIST_ONLY` | Company aliases and U.S. exchange validation |
| Current market price | Implemented-partial | `market_snapshot` on each prediction | Licensed real-time provider instead of yfinance/Stooq development feeds |
| Market-data fallback | Implemented | `market_data.py` 6-provider chain (yfinance/Finnhub/Tiingo/Alpha Vantage/Stooq/cache) + provider status in dashboard | Add Polygon/Tradier/Intrinio providers when keys are available |
| Dummy/paper live trade tracking | Implemented | `paper_trading.py`, `data/paper_trades.json`, dashboard Paper Trades tab | Close rules, stop rules, trade journal, broker sandbox integration |
| Manual trade journal | Implemented | `/manual-trades`, `manual_trading.py`, Manual Trades tab, Overview/Options Add trade buttons | Add close operation and daily history charts |
| Trump/admin policy monitoring | Implemented | `government.py` White House RSS + Federal Register + GDELT terms, `impact.py`, policy theme docs | Add Truth Social/X official APIs if legally configured |
| Trends/news impact | Implemented | `trend_impact` prediction field and Trends & Impact dashboard tab | Add historical trend charts |
| Confidence trace links | Implemented | `confidence_trace` prediction field and Confidence Traces tab | Add model-card style downloadable trace bundle |
| Short-term options edge | Implemented | `options_trade_idea` + `analyze_expiries`, Options Edge tab, yfinance + CBOE multi-source chain, default 5-DTE minimum, top-3 expirations with BUY CALL/BUY PUT/NO TRADE, up/down arrows, green/orange/red colors, underlying current price, option premium, bid/ask, lot size, volume, OI, defined-risk spreads, Greeks, IV/realized-vol ratio, IV Rank/Percentile from snapshots, ATM IV skew, term-structure slope, chain-derived unusual-activity score, exact-contract OI-change, sub-7-DTE risk gate for 5–6 DTE, algo confluence, Add option tracking | Need enough IV/OI snapshots for every ticker/expiry; add paid unusual-flow/gamma vendor and option-premium scorecard |
| Sortable dashboard tables | Implemented | Generic dashboard table sorter | Add persistent sort preferences |
| Stay on current tab after refresh | Implemented | Active tab persisted via URL hash + `localStorage`; toolbar Reload/Live-prices/Re-scan on every tab | — |
| Per-page live data refresh | Implemented | Sticky toolbar `⟳ Live prices` (`/prices/refresh`) + `▶ Re-scan` (`/jobs/run`) | Auto-poll option |
| Bullish and bearish verdicts | Implemented | `final_verdict` prediction field and Bull/Bear Verdicts tab | Add calibrated win/loss outcome tracking by verdict type |
| SNDK-style event radar | Implemented | `analysis/event_radar.py`, `event_radar` field, Event Radar dashboard tab | Add analyst-revision feed and earnings-calendar vendor |
| Local scheduled jobs | Implemented | `jobs.py`, CLI `collect`, API `/jobs/run`, `/jobs/status`, Windows task scripts | Add Docker worker profile and richer queue UI |
| Parallel grouped refresh jobs | Implemented | `refresh.py`, Jobs tab, `/jobs/refresh-all`, `/jobs/refresh/{category}`, `/jobs/run` pre-refresh | Add per-group retry policies and source-level freshness gating |
| Live market data | Implemented-partial | yfinance + key-gated Finnhub/Tiingo/Alpha Vantage in `market_data.py` | Licensed real-time provider such as Polygon, Intrinio, Nasdaq Data Link, Tradier, or broker feed |
| Ensemble forecast / uncertainty bands | Implemented | `analysis/forecast.py` Monte-Carlo bands + trend agents, `Forecast` schema, dashboard "Why" card | Add trained sequence model with registry + calibration |
| Near-term 2D/3D move bands | Implemented-new-scan | `PredictionResult.short_horizon_forecasts`, engine computes 2D and 3D Monte-Carlo bands with the same GPU/path settings, dashboard Why cards render them | Existing saved reports need a fresh scan to populate the new field |
| Historical point-in-time snapshots | Implemented-partial | `historical_store.py`, pipeline `snapshots`, `/snapshots/status`, prediction/evidence/options-chain/options-expiry/IV JSONL + per-run JSON files | Full raw provider payload archive and full every-strike options chain history still pending |
| IV Rank / IV Percentile | Implemented-data-dependent | `iv_rank_metrics()`, Options Edge IV Rank column, Options Risk Gate caps | Needs ~20+ stored IV observations per ticker/expiry |
| Weekly auto-retune | Implemented | `eaglesignal auto-tune`, `/jobs/tune`, `run_weekly_tune_job.ps1`, `EagleSignalAI-WeeklyRetune` installer entry | Retunes price-derived engines only until source snapshots mature |
| GPU Monte-Carlo | Implemented-optional | `ENABLE_GPU_MONTE_CARLO`, `MONTE_CARLO_PATHS`, settings-wired forecast call, CuPy backend with NumPy fallback | Requires local CuPy/CUDA validation before enabling high path counts |
| Reliability scorecard | Implemented-data-dependent | `/reliability/scorecard` from `prediction_snapshots.jsonl` | Fresh calls remain pending until forward bars exist; option-premium scorecard needs historical option marks |
| Options prediction | Implemented-partial | `options_chain.py`, `analysis/options.py`, `historical_store.py` | Implemented: multi-expiry chains, 5-DTE floor, top expiry ranking, approximate Greeks, IV Rank/Percentile when snapshots exist, ATM skew, term slope, spread filters, earnings IV-crush gate, chain-derived unusual activity, OI change, and expiration selection. Pending: paid flow/gamma, full every-strike history, option-premium backtest/calibration |
| Technical indicators/patterns | Partial-good | `analysis/technical.py`, `analysis/patterns.py`, tests | Add VWAP intraday, opening range, support/resistance, candlestick library or broader pattern set |
| Fundamentals and balance sheets | Partial | SEC company facts in `sec_edgar.py`, `fundamentals.py` | More XBRL tags, ratios, restatements, segment data, growth rates, filing-date-safe historical features |
| SEC filings | Partial | latest 10-K/10-Q/8-K/Form 4 metadata | Filing text parser, material-event extractor, Form 4 insider trend, 13F trend |
| Company contracts and agreements | Missing | documented in `SKILLS.md` | SAM.gov, USAspending.gov, DOD awards, company PR/IR, SEC exhibit parser |
| Revenue department / tax/fiscal context | Missing | mentioned in docs only | Treasury FiscalData, IRS releases where market-relevant, CBO/JCT for tax policy |
| Job market | Implemented-partial | FRED UNRATE + BLS CPI/unemployment in `government.py` | BLS payrolls, PPI, wages, JOLTS, release calendar and surprise-vs-consensus |
| Political and geopolitical | Implemented-partial | Federal Register + GDELT policy + openFDA recalls + DOJ/FTC actions in `government.py`, stored as MARKET evidence | White House, Congress.gov, OFAC, State Dept, Defense, sector/ticker impact mapper |
| FDA / regulatory events | Implemented-partial | openFDA drug+device recalls; DOJ Antitrust + FTC consent orders; `impact.py` ticker mapping | FDA approvals/CRLs, supplier/customer exposure graph, merger-review tracking |
| Government event → ticker mapping | Implemented | `analysis/impact.py` (SKILL-056): direct brand-token + thematic sector match, `policy_impacts` + event-risk warnings | Supplier/customer/peer exposure graph, confidence scoring per link |
| U.S. government news | Implemented-partial | Federal Register API + GDELT policy query | More agency RSS/API connectors with sector/ticker impact mapper |
| Other-country market correlations | Partial | SPY benchmark only | Global ETFs/indexes, FX risk proxies, commodities, rates, rolling beta/correlation matrix |
| Company news | Partial | yfinance news / NewsAPI | Company IR RSS/pages, PRNewswire/BusinessWire if licensed, SEC 8-K press releases |
| Latest X/Twitter comments | Partial | StockTwits + Reddit in `social.py` (key-gated X documented) | Official X API v2 connector, cashtag/company filters, bot/spam scoring |
| Sentiment trends | Implemented-partial | multi-source headline lexicon + capped social blend in `sentiment.py` | FinBERT/LLM classifier, entity-aware sentiment, volume baseline |
| Socioeconomic/material stocks | Partial | macro score and sector tags | Sector exposure graph, commodities/materials feeds, policy/weather/supply-chain impact |
| Backtesting | Partial | `backtest.py`, CLI command | Walk-forward feature snapshots, no-lookahead checks, options backtests, calibration metrics |
| Deep learning / ensemble models | Implemented-partial | `analysis/forecast.py` Monte-Carlo bands + trend-agent ensemble (statistical, real history) | Add trained sequence model with saved scalers, model registry, walk-forward promotion gates |
| Reports/dashboard | Present-good | Markdown/HTML/JSON/CSV generator, tabbed dashboard | More filters, ticker detail routes, live refresh controls |
| Alerts | Partial | dispatcher and state file | Email/Slack/Discord/Telegram delivery tests, severity routing, event-driven alerts |
| Docker Desktop | Present | `Dockerfile`, `docker-compose.yml` | Health/readiness docs, volume permissions, scheduled worker profile |
| 23-factor market checklist | Documented, implementation pending | `MARKET_FACTOR_CHECKLIST.md`, README/Workflow/PRD links | Add factor coverage auditor to every `PredictionResult` and dashboard trace |
| Source-priority registry | Implemented-partial | `config/analysis_source_registry.yml`, `refresh.py` grouped Jobs/status, `DATA_SOURCES.md`, README/Workflow/PRD links | Add source-priority trace to every recommendation |

## Referenced GitHub Project Lessons

Sources reviewed:

- `ZhuLinsen/daily_stock_analysis`: LLM-driven A/H/U.S. stock analysis with multi-source quotes, real-time news, decision dashboard, multi-channel push, GitHub Actions, Docker, FastAPI/WebUI/Bot-style modules, and backtesting concepts.
- `dfdezdom/investdaytip`: Multi-factor 0-100 scoring for stocks/ETFs, custom ticker files, concurrent fetching, HTML export, pure testable scoring functions, and advisor mode.
- `myhhub/stock`: InStock system for daily stock/ETF data, indicators, chip/cost distribution, K-line pattern detection, strategy screening, backtesting, scheduling, mobile web display, Docker image, and optional automated trading. For this project, keep the analysis/backtest ideas but do not enable automated trading by default.
- `SumanthT26/USA-Stock-Market-prediction-using-Financial-Fundamental-data`: Uses 200+ financial indicators from annual filings, EDA, statistical analysis, model building, tree models, SMOTE/PCA, and AUC/precision style evaluation.
- `EvotecIT/UnifiStockTracker`: Not a finance predictor, but useful as an alerting pattern: monitor only the specific user-selected items, recheck at a configured interval, and avoid spam from broad monitoring.
- `JordiCorbilla/stock-prediction-deep-neural-learning`: LSTM time-series forecasting, saved scalers/config/model artifacts, newer direction-plus-magnitude design, and stochastic forecast bands.
- `huseinzol05/Stock-Prediction-Models`: Large research collection of LSTM/GRU/Seq2Seq/attention/CNN sequence models, stacking ensembles, trading agents, sentiment consensus, and Monte Carlo simulations.

Techniques already borrowed:

- Daily decision dashboard idea.
- Watchlist-first workflow.
- Multi-factor 0-100 scoring.
- Pure scoring functions with tests.
- HTML/Markdown reports.
- Docker/GitHub Actions deployment.
- Targeted alerts and deduplication.
- Technical indicator and candlestick direction.
- Fundamental scoring from financial statements.
- Real market-data fallback with provider status and local real-data cache.

Techniques still missing:

- True multi-source fallback per data type.
- LLM reasoning over a complete evidence store.
- Concurrent fetching for large watchlists.
- Rich web dashboard and bot interaction.
- Larger technical factor/pattern library.
- Historical feature store with model training and calibration.
- Scheduled/event-driven recheck loop for user-selected events.
- Strict no-spam alert controls by event type and severity.
- Deep-learning model pipeline: direction/magnitude heads, scalers, model registry, uncertainty bands, walk-forward promotion gates.
- Stacking/ensemble layer over rule scores, technical features, fundamentals, options, sentiment, macro, and sequence-model output.

## What Is Needed To Make It More Live

1. Replace single-provider development data with provider abstraction.

   Add provider interfaces and configure priority/fallback:

   - Market bars: Polygon, Tiingo, Intrinio, Nasdaq Data Link, IEX alternatives, broker API.
   - Options: Tradier, Polygon Options, ORATS, Cboe DataShop, broker API.
   - News: NewsAPI plus Benzinga/Financial Modeling Prep/AlphaSense-like licensed source if available, company IR, SEC.
   - Social: official X API, Reddit API, StockTwits if allowed.

   Current MVP fallback already avoids fabricated prices:

   ```text
   yfinance -> Stooq -> local real-data cache -> unavailable/skip
   ```

2. Add event-driven connectors.

   The market does not wait for daily batch scans. Add polling/webhook-style checks for:

   - SEC 8-K/10-Q/10-K/Form 4.
   - Earnings releases and guidance.
   - Fed decisions, minutes, speeches.
   - CPI/PPI/PCE/jobs/GDP releases.
   - FDA approvals/rejections.
   - DOJ/FTC antitrust actions.
   - DOD/SAM.gov/USAspending contract awards.
   - Major geopolitical shock headlines.

3. Store raw data and normalized features.

   Current reports are generated from a run, but a live predictor needs:

   - `data/raw/source/YYYY-MM-DD/entity/*.json`
   - SQLite/DuckDB feature store for MVP.
   - Prediction history table.
   - Outcome table for calibration.
   - Source freshness and latency table.

4. Make source freshness enforceable.

   Each signal should carry:

   - `published_at`
   - `retrieved_at`
   - `source_name`
   - `source_type`
   - `freshness_status`
   - `reliability_score`
   - `can_trade_on_this`

   If a source is stale, lower confidence or block the signal.

5. Separate prediction from explanation.

   Keep deterministic/statistical models as the predictor. Use LLMs only to:

   - Summarize evidence.
   - Explain contradictions.
   - Produce scenarios.
   - Ask what data is missing.
   - Check whether the report overstates confidence.

6. Add model quality tracking.

   Required metrics:

   - Directional accuracy by horizon.
   - Brier score / calibration curve.
   - Win rate.
   - Average return.
   - Max drawdown.
   - Sharpe/Sortino.
   - False positive rate.
   - Performance by market regime.

7. Add a live scheduler.

   Docker Desktop can run:

   - `api` service for on-demand dashboard/API.
   - `worker` service for premarket/intraday/after-market scans.
   - `event-monitor` service for SEC/news/social/government polling.

## Important Missing Sources

High priority official/government:

- SEC EDGAR submissions, company facts, filing text, Form 4, 13F.
- Federal Reserve press releases, FOMC calendar, speeches, minutes.
- CME FedWatch for market-implied Fed expectations.
- FRED and Treasury yield curve.
- BLS: CPI, PPI, payrolls, unemployment, wages, JOLTS.
- BEA: GDP, PCE, personal income/spending.
- U.S. Census Economic Indicators: retail sales, housing starts, construction, trade, inventories.
- Treasury FiscalData and auction data.
- EIA: crude, gas, inventories, production.
- OFAC/Treasury sanctions and geopolitical economic restrictions.
- ISM and S&P Global PMI releases.
- FDA: approvals, complete response letters, recalls, safety alerts.
- DOJ/FTC: antitrust, consumer protection, merger actions.
- Congress.gov and Federal Register: legislation/regulation.
- White House: executive actions and policy announcements.
- OFAC/State/Commerce/BIS: sanctions and export controls.
- SAM.gov, USAspending.gov, DOD contract awards.

High priority company/market:

- Company investor relations pages and RSS feeds.
- Earnings calendar and earnings call transcripts.
- Nasdaq, Yahoo Finance, and TradingView earnings calendars.
- Press releases from company IR, PRNewswire, BusinessWire, GlobeNewswire.
- Analyst estimates/revisions if licensed.
- Insider transactions from Form 4.
- Institutional 13F trends.
- Sector ETFs and industry peer baskets.
- Index futures/proxy ETFs, VIX/VIX term structure, Treasury ETFs, oil/gold/copper, dollar index proxies.
- TradingView, Investing.com, Finviz, Koyfin, and Reuters as dashboard/reference sources, with official-source verification.
- Bloomberg Terminal, LSEG Workspace, FactSet, and S&P Capital IQ Pro as optional licensed institutional upgrades.

High priority sentiment:

- X/Twitter official API using cashtags and company names.
- Reddit API for selected finance subreddits where allowed.
- StockTwits if API access is available.
- AAII Sentiment Survey for weekly retail sentiment.
- CNN Fear & Greed and MacroMicro as supporting risk/sentiment references only.
- GDELT for broad global news/event coverage.
- Bot/spam/duplicate detection.

## Strict Context Rules For The AI Product

The system should never analyze a company only because it appears in the news. It should only use external companies as context when they are connected to a watched asset.

Examples:

- If `NVDA` is watched, news about TSMC, AMD, export controls, semiconductor equipment, and hyperscaler capex can be contextual evidence.
- If `AAPL` is watched, supply chain and China policy can be contextual evidence.
- If no watched ticker is materially related, store the event as market context only, not as a ticker prediction.

Required implementation rule:

```text
candidate_prediction_assets = explicit_watchlist_assets
context_assets = peers + suppliers + customers + indexes + sector ETFs + macro proxies
Only candidate_prediction_assets receive predictions.
context_assets can only explain or adjust scores.
```

## Next Engineering Tasks

P0:

- Add company aliases to watchlist config.
- Add factor-coverage auditor for the 23 groups in `MARKET_FACTOR_CHECKLIST.md`.
- Add source-priority trace from `config/analysis_source_registry.yml` to every recommendation.
- Add stronger data-source status and freshness panels to reports.
- Add source freshness/reliability enforcement to every component.
- Add close operation and daily history charts for manual trade journal.
- Add BLS and BEA connectors.
- Add Census, Fed/FOMC, CME FedWatch, EIA, OFAC, ISM/PMI, AAII, and Cboe market-statistics connectors where legal/API access is available.
- Add X/Twitter official API connector behind `ENABLE_X_SENTIMENT=false` default.
- Add government event connectors for Fed, Treasury, FDA, DOJ/FTC, DOD/SAM.gov/USAspending.
- Add company IR/press release connector.

P1:

- Add provider abstraction and fallback priority.
- Add concurrent fetching with rate-limit manager.
- Add feature store and prediction outcome store.
- Add paid options unusual-flow/gamma vendor integration and full every-strike chain archive. Chain-derived IV Rank, skew, term-structure, unusual-activity, and OI-change analytics are already implemented.
- Add earnings calendar and IV crush event logic.
- Add walk-forward backtesting and calibration reports.
- Add interactive dashboard filters and ticker detail pages.

P2:

- Add LLM evidence-review agent.
- Add geopolitical risk engine.
- Add supply-chain/competitor graph.
- Add analyst revision and transcript sentiment if licensed.
- Add portfolio risk view.

## Documentation Status

Required docs exist:

- `README.md`
- `SKILLS.md`
- `WORKFLOW.md`
- `ARCHITECTURE.md`
- `DATA_SOURCES.md`
- `MARKET_FACTOR_CHECKLIST.md`
- `PRODUCT_REQUIREMENTS.md`
- `REFERENCE_ANALYSIS.md`
- `ROADMAP.md`
- `.env.example`
- `.gitignore`
- `requirements.txt`
- `requirements-dev.txt`
- `Dockerfile`
- `docker-compose.yml`
- `LICENSE`

Recommended doc additions:

- Keep this file as the living validation document.
- Add `OPERATIONS.md` for Docker Desktop runbooks, scheduling, health checks, logs, and source failure triage.
- Add `MODEL_GOVERNANCE.md` for no-lookahead validation, feature provenance, calibration, model versioning, and promotion rules.
- Add `COMPLIANCE.md` for legal source access, no insider data, no paywall bypassing, and research-only language checks.
