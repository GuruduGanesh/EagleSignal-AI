# USA-Stock-Market-prediction

**Working product name:** EagleSignal AI  
**Scope:** U.S. stock exchange prediction and decision intelligence for **equities, options, ETFs, and U.S. market indexes only**.

> This project is for research, education, and decision support. It must not present outputs as guaranteed investment advice. Every recommendation must include uncertainty, evidence, source links, risk level, and invalidation conditions.

## 1. Vision

Build an all-in-one AI automation system that continuously gathers market, company, macroeconomic, government, political, geopolitical, options, technical, fundamental, and sentiment data, then produces explainable predictions for U.S. stocks, options, ETFs, and indexes.

The system should act like a combined:

- Quant analyst
- Fundamental analyst
- Macroeconomic analyst
- Options flow analyst
- News and government policy analyst
- Risk manager
- Backtesting engine
- Alerting/notification system
- Evidence-based AI research assistant

## 2. Core Prediction Targets

The system predicts and scores:

1. **Equities:** Individual U.S.-listed stocks.
2. **Options:** Calls/puts, IV, Greeks, unusual volume, open interest, expected move, skew, term structure, and chain-derived OI-change.
3. **Indexes:** S&P 500, Nasdaq 100, Dow Jones, Russell 2000, VIX and related index ETFs.
4. **ETFs:** SPY, QQQ, DIA, IWM, sector ETFs, bond ETFs, commodity-linked ETFs where relevant to equity risk.

No crypto, no forex-only signals, no gambling-style “guaranteed win” language.

## 3. Unique Differentiator

Most stock projects focus only on price, technical indicators, or financial ratios. This system must combine:

- Market price action
- Options chain intelligence
- SEC filings and fundamentals
- Earnings transcripts and guidance
- U.S. government data
- Federal Reserve data
- Treasury and yield curve data
- Labor market data
- Inflation and GDP data
- Political and geopolitical event risk
- Global market correlation
- Company-specific contracts, agreements, lawsuits, product launches, leadership changes
- News sentiment
- Social sentiment from X/Twitter (official API, key-gated), plus KEYLESS real-time **Bluesky** and **Mastodon** (legal substitutes for unauthenticated X reads — breaking microblog posts), StockTwits, and Reddit; falls back to live news-headline sentiment so the signal is never empty when streams are IP-blocked
- Manual Trade Journal supports full add / edit / delete with live P/L re-marking (REST: POST/PUT/DELETE `/manual-trades`), plus **Add trade** buttons from Overview and Options Edge that capture the current displayed market price as the entry for a user-tracked long/short idea
- Macro regime works with or without a FRED key: keyless live fallback pulls Treasury yields (^TNX/^FVX/^TYX), VIX, WTI, and the dollar index from yfinance plus Treasury FiscalData
- Sector rotation and institutional flow proxies
- Trump administration / White House / Federal Register / tariff / export-control / defense / AI infrastructure policy monitoring
- Theme baskets for Trump-policy-adjacent public names and top AI/GPU/storage/chips/robotics/space stocks
- Focused default universe from the current niche screen plus top niche options names: SPY/QQQ as market context plus MU, AMD, AVGO, NVDA, INTC, AAPL, META, GOOGL, AMZN, TSM, ASML, LRCX, SMCI, DELL, HPE, WDC, AMAT, OKLO, PLTR, ISRG, RKLB, SNDK, MRVL, and QBTS. Groq is tracked as private AI-inference context only because it has no public stock ticker or listed options chain.
- Manual paper-trade journal for user-entered trade price, quantity, current mark, P/L, and notes
- Bullish and bearish final verdicts for long, short/put, watch-only, or avoid research
- SNDK-style event radar for abnormal price acceleration, volume expansion, catalyst density, and exhaustion/reversal risk
- Confidence = conviction in an actionable BUY/SELL: `evidence_quality × (0.15 + 0.85 × directional_conviction)`, so a neutral "no edge" call is capped low on purpose; high confidence requires a clear buy or sell. The Confidence Traces tab shows the Call (BUY/SELL/NO TRADE), conviction %, and data-quality %, and links to `/ticker/{symbol}`, `/signals`, and source URLs
- Source registry and verification stack: `config/analysis_source_registry.yml` keeps the existing connectors and adds the target daily stack of TradingView, Investing.com, Finviz, Reuters, SEC EDGAR, BLS/BEA/FRED, and Cboe; dashboards are monitoring aids, while confidence must be verified through official primary or licensed sources
- Options Edge tab for short-term options research: multi-source live chains (yfinance with a keyless CBOE delayed-quotes fallback), a default **5-DTE minimum** (`MIN_OPTION_DAYS_TO_EXPIRY=5`), and the **top 3 expirations by confidence** per name. Each row has a plain **BUY CALL (up ▲) / BUY PUT (down ▼) / NO TRADE (→)** call, green/orange/red colors, underlying current price, reference option contract/premium, bid/ask, bid/ask spread %, exact contract volume/OI, approximate delta/theta/vega, breakeven, premium % of spot, IV/realized-vol ratio, IV Rank/Percentile once enough snapshots exist, ATM IV skew, term-structure slope, chain-derived unusual-activity score, exact-contract OI-change, readiness, option-quality score, lot size, volume, OI, put/call, ATM strike, defined-risk spread strikes, IV, and an algorithmic confluence score. The **Options Risk Gate** deep-scores directional conviction, data quality, algo confluence, exact-contract liquidity, DTE, IV/realized vol, IV Rank, Greeks/theta, flow, premium cost, and spread, then caps or downgrades weak rows to **spread only**, **paper only**, or **no trade**. Direct **Add option** appears only for high-gate rows so medium/conflicted options do not look like naked-call recommendations. Ticker rows expand/collapse the ranked expiries, and sorting keeps every ticker group together.
- Sortable tables on every dashboard tab; the active tab persists across reloads (no snap-back to Overview) and a sticky toolbar offers Reload / Live-prices / Re-scan on every tab. Live/current prices auto-refresh every 10 minutes while the dashboard is open, with consistent green/red/gray coloring for up/down/flat movement and trade P/L.
- Theme Watchlists tab now merges static baskets with live verdict/trend data for scored tickers
- Scheduled local collection split into small Windows Task Scheduler jobs (08:35 morning full scan, 20:35 evening full scan, 5-minute intraday refresh + analysis, and weekly retune) via `scripts/install_windows_tasks_split.ps1`, with retry, status file, and a browser trigger; each scheduled/manual collection first fans grouped source refreshes out in parallel, then re-runs the focused prediction pipeline with parallel per-ticker workers and per-ticker retry for transient provider failures
- Historical point-in-time snapshots are persisted after successful scans when `ENABLE_HISTORICAL_SNAPSHOTS=true`: compact prediction, model-ready feature rows (`feature_snapshots.jsonl`), evidence, selected options-chain/expiry, and IV JSONL logs plus a per-run JSON file under `data/historical_snapshots`. This starts the no-lookahead foundation for IV Rank, scorecards, feature stores, and future ML training. Status is visible at `/snapshots/status`; measured equity outcomes are visible at `/reliability/scorecard`, option-premium outcomes at `/reliability/options-scorecard`, feature/label joins at `/reliability/labels`, and confidence calibration profiles at `/reliability/calibration` once enough forward data exists.
- Confidence calibration is now additive and traceable: live scans keep raw confidence in `confidence_trace.raw_confidence_score` and apply a saved historical bucket calibration only when enough matured outcomes exist. The Jobs tab exposes Reliability Scorecard, Options P/L Scorecard, Confidence Calibration, and Feature Labels buttons.
- Weekly ADR-002 retune is wired through `python -m eaglesignal auto-tune`, `/jobs/tune`, and `scripts/run_weekly_tune_job.ps1`; `scripts/install_windows_tasks_split.ps1` installs the weekly Task Scheduler entry.
- Optional GPU Monte-Carlo is available with `ENABLE_GPU_MONTE_CARLO=true` and CuPy installed; the prediction engine now passes this setting and `MONTE_CARLO_PATHS` directly into the forecast component. It falls back to NumPy CPU automatically. GPU can improve simulation throughput and local sentiment/advisor latency, while confidence quality still depends on source coverage, calibration, risk gates, and outcome tracking.
- New scans also store 2D and 3D Monte-Carlo bands beside the main horizon forecast, so the dashboard can show near-term expected return/range without changing the existing 5D score path.
- Full pipeline ticker analysis runs in parallel and is controlled by `PIPELINE_MAX_WORKERS` (default `16`). Raise it only if providers are not throttling; lower it if live APIs start failing/retrying.
- Backtesting and calibration
- Explainability and confidence scoring
- Optional AI Advisor backends: deterministic rules by default, OpenAI/Anthropic when keys are set, and local Ollama when `ADVISOR_PROVIDER=ollama` or `OLLAMA_BASE_URL` is configured. LLMs explain real signal JSON only; they do not invent facts or override deterministic scoring.

## 4. Reference Repositories Reviewed

These repositories inspired the design direction. Do not blindly copy code; use the concepts and rebuild cleanly.

| Repository | Useful idea to borrow | How this project improves it |
|---|---|---|
| `ZhuLinsen/daily_stock_analysis` | AI decision dashboard, multi-source market/news aggregation, scheduled reports, alerting | Make it U.S.-focused with options, SEC filings, government data, risk scoring, and traceable evidence |
| `dfdezdom/investdaytip` | Multi-factor 0-100 scoring, CLI, fast concurrent fetching, HTML report, testable scoring functions | Add options signals, macro/government/geopolitical intelligence, calibration, backtesting, explainable confidence |
| `myhhub/stock` | Technical indicators, candlestick recognition, strategy screening, backtesting, automation | Translate concepts into U.S. market, Python-first architecture, safer read-only mode by default |
| `SumanthT26/USA-Stock-Market-prediction-using-Financial-Fundamental-data` | Fundamental financial indicators and ML modeling | Add live SEC/company fundamentals, time-series validation, feature store, model monitoring |
| `EvotecIT/UnifiStockTracker` | Targeted monitoring and notification instead of noisy alerts | Apply targeted alerting to tickers, events, filings, options flow, and market regime changes |

## 5. High-Level Modules

```text
market-data-ingestion
news-government-crawler
company-fundamentals
sec-filings-parser
options-intelligence
macro-regime-engine
geopolitical-risk-engine
sentiment-engine
technical-analysis-engine
cross-market-correlation-engine
feature-store
prediction-models
backtesting-engine
risk-manager
llm-reasoning-agent
report-generator
alerting-engine
web-dashboard
api-service
scheduler
observability
compliance-guardrails
```

## 6. Main Outputs

For every ticker/index/option candidate, output:

- Direction: Bullish / Bearish / Neutral / Avoid
- Time horizon: Intraday, 1 day, 5 days, 20 days, earnings window, long-term
- Confidence score: 0-100 — conviction in the actionable BUY/SELL call (data quality × directional conviction); neutral/avoid are capped low
- Confidence trace: the call (BUY/SELL/NO TRADE), conviction %, data quality %, agreement %, available/missing engines, source links, and raw signal endpoint
- Expected move range
- Best-case / base-case / worst-case scenario
- Key catalysts
- Key risks
- Supporting evidence links
- Technical signal summary
- Fundamental signal summary
- Options signal summary
- Short-term options strategy idea
- Macro/government/news signal summary
- Sentiment signal summary
- Position sizing warning
- Invalidation level
- “Do not trade” warning when evidence is weak or conflicting
- Trend impact summary showing price move, news volume/providers, evidence polarity, policy links, social signal, and forecast tilt
- Bull/Bear Verdicts summary showing the final research action and why
- Event Radar summary showing breakout score, exhaustion score, 20D/60D/252D returns, volume expansion, bullish clues, and bearish clues
- Manual trade tracking for user-entered analysis validation

## 7. Suggested Repository Structure

```text
USA-Stock-Market-prediction/
├── README.md
├── SKILLS.md
├── MASTER_AI_PROMPT.md
├── WORKFLOW.md
├── ARCHITECTURE.md
├── DATA_SOURCES.md
├── MARKET_FACTOR_CHECKLIST.md
├── PRODUCT_REQUIREMENTS.md
├── ROADMAP.md
├── .env.example
├── .github/
│   └── workflows/
│       └── market_prediction.yml
├── src/
│   ├── ingestion/
│   ├── analysis/
│   ├── options/
│   ├── fundamentals/
│   ├── macro/
│   ├── sentiment/
│   ├── models/
│   ├── risk/
│   ├── reports/
│   └── alerts/
├── tests/
└── reports/
```

## 8. First MVP

Build the MVP in this order:

1. Read ticker list from config.
2. Pull price history and basic market data.
3. Pull SEC company facts and latest filings.
4. Pull macro series from official sources.
5. Pull news using approved APIs.
6. Compute technical indicators.
7. Compute fundamental scores.
8. Compute macro/regime risk.
9. Generate 0-100 multi-factor score.
10. Produce Markdown/HTML report.
11. Add GitHub Actions schedule.
12. Add backtesting and confidence calibration.
13. Add options chain analytics.
14. Add web dashboard and alerts.

## 9. Safety and Legal Boundaries

- Respect robots.txt, site terms, API rate limits, and fair-access policies.
- Prefer official APIs over scraping.
- Never store API keys in code.
- Do not automate trading in the MVP.
- Do not claim guaranteed profit.
- Do not use non-public material information.
- Every AI claim must cite evidence and show uncertainty.

## 10. Current Validation

Read [`VALIDATION_AND_LIVE_READINESS.md`](VALIDATION_AND_LIVE_READINESS.md) for the current truth table of what is implemented, what is only documented, what sources are missing, and the next steps needed to make EagleSignal AI closer to a live U.S. equities/options/index prediction product.

Read [`POLICY_THEME_WATCHLISTS.md`](POLICY_THEME_WATCHLISTS.md) for Trump/admin policy-adjacent public stocks and the top AI/GPU/storage/chips/robotics/space research basket.

Read [`MARKET_FACTOR_CHECKLIST.md`](MARKET_FACTOR_CHECKLIST.md) for the required 23-factor analysis checklist covering fundamentals, valuation, macro, government/policy, geopolitics, sector trends, sentiment, technicals, options, liquidity, institutional flows, bonds, currencies, commodities, global markets, events, earnings calls, calendar effects, volatility, alternative data, AI/technology, index structure, and black-swan risk.

Read [`config/analysis_source_registry.yml`](config/analysis_source_registry.yml) for the additive source registry covering daily dashboard tools, official primary sources, options/volatility/sentiment sources, market-news sources, paid institutional platforms, and automation APIs.

## 11. Manual and Scheduled Collection

- Browser trigger: open `/dashboard`, choose **Jobs**, then click **Run Now**.
- Browser auto-refresh: while `/dashboard` is open, live prices refresh every 10 minutes and grouped source jobs refresh every 30 minutes; use **Refresh ALL + analyze** or **Re-scan** when you want a full prediction/report rewrite immediately.
- CLI trigger: `python -m eaglesignal collect --strategy swing --horizon 5D`.
- Windows schedule: run `scripts/install_windows_tasks_split.ps1` once for split jobs, including 08:35 and 20:35 full scans plus a 5-minute grouped parallel refresh + analysis during market hours. The older single-task installer `scripts/install_windows_task.ps1` is still available.
- Status file: `data/job_runs.json`, also visible through `/jobs/status` and the dashboard Jobs tab.
