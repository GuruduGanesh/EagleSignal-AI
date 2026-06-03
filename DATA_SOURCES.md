# DATA_SOURCES.md

## Data Source Strategy

Prefer official and legal APIs. Avoid uncontrolled scraping whenever a supported API exists.

The additive source registry lives in `config/analysis_source_registry.yml`. It
keeps the current implemented connectors as-is and adds a target verification
stack for analysis/recommendations: TradingView + Investing.com + Finviz +
Reuters + SEC EDGAR + BLS/BEA/FRED + Cboe as the minimum daily stack.

Important rule: one dashboard is useful for daily monitoring, but important
signals must be verified from official primary sources or licensed providers
before they can raise confidence.

## 0. Daily Monitoring And Verification Stack

| Source | Best for | Product role |
|---|---|---|
| TradingView | Charts, technicals, economic/earnings/revenue/dividend/IPO calendars, alerts, sectors, futures | Daily monitoring dashboard; manual/reference unless licensed integration is added |
| Investing.com | Economic calendar, global markets, futures, commodities, bonds, previous/forecast/actual macro releases | Macro and cross-market reference; verify releases from official sources |
| Finviz | Screener, heat map, insider trades, futures, forex, news | Market overview; quotes may be delayed, so never use alone for live trading |
| Koyfin | Company financials, macro dashboards, global markets, portfolios, reports | Optional research dashboard / paid reference |
| Reuters Markets | Market-moving news flow across stocks, commodities, currencies, global economics | High-quality news reference; licensed LSEG is production-grade |

Minimum practical daily stack:

```text
TradingView + Investing.com + Finviz + Reuters + SEC EDGAR + BLS/BEA/FRED + Cboe
```

Professional paid upgrade path:

```text
Bloomberg Terminal / LSEG Workspace / FactSet / S&P Capital IQ Pro
```

These are optional institutional-grade sources. They should be used through
licensed APIs/terminals only.

## 1. Official U.S. Government and Public Data

| Source | Use case | Notes |
|---|---|---|
| SEC EDGAR APIs | Company filings, submissions, XBRL company facts | Official source for filings |
| BLS API | Jobs, unemployment, CPI, PPI, wages | Official labor/inflation source |
| BEA API | GDP, personal income, spending, national accounts | Official economic growth source |
| U.S. Census Economic Indicators | Retail sales, housing starts, construction, trade, inventories | Official real-economy demand source |
| FRED API | Treasury yields, rates, macro series, financial conditions | Federal Reserve Bank of St. Louis data portal. **Optional** — without a key, macro falls back to keyless live sources (see §4a). |
| Federal Reserve | FOMC statements, minutes, speeches, policy releases | Use official release pages/RSS where available |
| CME FedWatch | Fed funds futures-implied hike/cut expectations | Derived market-implied rate probabilities; context only |
| U.S. Treasury | Yield curve, auctions, debt, fiscal data | Official Treasury data |
| EIA | Oil, gas, energy inventory data | Energy sector impact |
| OFAC / Treasury press releases | Sanctions and geopolitical economic restrictions | Official sanctions/geopolitical policy source |
| FDA | Drug/device approvals and safety announcements | Healthcare/biotech impact |
| DOD / SAM.gov / USAspending.gov | Government contracts | Defense/industrial/software contractor impact |
| FTC/DOJ | Antitrust/lawsuit/regulatory actions | Big Tech, healthcare, consumer, finance |
| White House / Congress.gov | Policy and legislative risk | Sector-level impact |
| White House RSS / Federal Register / GDELT policy search | Trump administration actions, executive orders, tariffs, sanctions, export controls, AI/data-center policy | Market-wide context mapped only to watched symbols |
| Local scheduled collector | Same configured real-data sources, run every two hours via Windows Task Scheduler or manually from browser | Retries failures and writes `data/job_runs.json` status |

Implemented keyless connectors in `ingestion/government.py`: Treasury FiscalData
(avg interest rate), BLS (CPI + unemployment), Federal Register (presidential
documents), **openFDA** (drug + device recalls), **DOJ Antitrust + FTC** (Federal
Register agency filter), and GDELT policy news. Events are categorized
(policy/fiscal/labor/fda/antitrust/trump_admin) and stored as `MARKET` evidence.
`BLS_API_KEY` is optional; everything else is keyless. Trump/admin policy news is
context until connected to a watched ticker through direct company mention,
sector theme, or explicit government action.

## 2. Market Data

MVP options:

- yfinance for development/testing only
- Stooq or similar free sources where allowed
- Nasdaq/NYSE public pages where terms allow
- Local cache from a prior successful real-data download

Production options:

- Polygon.io
- Massive / Polygon market data APIs where licensed
- Intrinio
- Tiingo
- Alpha Vantage
- Nasdaq Data Link
- IEX Cloud alternatives where available
- Tradier / broker APIs for options
- ORATS / Cboe / OptionMetrics if licensed

Current runtime fallback order (configurable via `MARKET_DATA_PROVIDER_CHAIN`):

```text
yfinance -> Finnhub -> Tiingo -> Alpha Vantage -> Stooq daily history
         -> local cache from prior successful real download -> unavailable
```

- `yfinance`, `Stooq`, and `local_cache` are keyless.
- `Finnhub`, `Tiingo`, and `Alpha Vantage` activate automatically when
  `FINNHUB_API_KEY` / `TIINGO_API_KEY` / `ALPHAVANTAGE_API_KEY` are set; otherwise
  they are skipped and recorded as `no_api_key` in the provider status.
- Each attempt is logged in `provider_status` (e.g. `yfinance=ok`, `finnhub=no_api_key`).

Rules:

- Do not fabricate synthetic runtime market data. (Synthetic bars exist only as a unit-test fixture.)
- If all real providers fail and no local real-data cache exists, mark the ticker unavailable and skip prediction.
- Reports must show the winning provider and the fallback status for each attempted provider.
- Local cache is allowed only when it came from a previous real provider response.

## 3. News and Search

Implemented multi-source merge (deduped by normalized title, newest first):

- NewsAPI (when `NEWS_API_KEY` is set) — reputable financial/general news
- Finnhub company news (when `FINNHUB_API_KEY` is set) — company-tagged headlines
- Google News RSS (keyless) — top-source aggregator, originating publisher attributed
- Yahoo Finance RSS (keyless) — per-symbol headline feed
- GDELT DOC 2.0 (keyless, throttled to one request / 5s) — broad global news/events
- Direct White House presidential-actions RSS feed, Federal Register presidential documents, and GDELT policy/admin queries for Trump administration, White House, executive orders, tariffs, export controls, DOJ/FTC/FDA/DoD, AI/data-center policy
- Event Radar uses only real historical bars from the market-data provider chain. It does not fabricate SNDK-style moves; it detects acceleration, volume expansion, catalyst density, drawdown, and exhaustion from downloaded data.
- yfinance quote-page headlines (keyless)
- StockTwits stream links (keyless; may be IP-blocked on cloud hosts)

Only public RSS/APIs are used. No paywall/login bypass, no scraping behind access
controls, and no private or non-public (insider) sources — prohibited by law and by
SKILL-134. Also available as design references: company IR RSS, SerpAPI / Brave /
Tavily / Marketaux / FMP if licensed (`MARKETAUX_API_KEY`, `FMP_API_KEY`).
Reuters, Bloomberg, CNBC, MarketWatch, WSJ/Barron's, The Fly, Benzinga Pro,
Briefing.com, and Seeking Alpha are valuable news-flow/reference sources, but
paid/paywalled sources must only be used through licensed access. Rumors and
opinion sources are context-only until confirmed.

Rules:

- Rank official/company/SEC sources higher than media summaries.
- Separate confirmed events from rumors.
- Deduplicate similar stories. (Implemented: `_norm_title` dedupe across all providers.)
- Store source links and timestamps. (Implemented: evidence store records both.)

## 4. Social Sentiment

Use only legal/approved access (implemented with graceful fallback). The Sentiment
signal is **always populated** — when the social streams are blocked it falls back
to live news-headline polarity rather than going empty:

- X/Twitter official API v2 — IMPLEMENTED and key-gated (`X_BEARER_TOKEN`): company
  news + cashtag sentiment (`ingestion/x_twitter.py` → news/social) and
  government-handle/policy tweets (folded into `government.py`). Requires a paid X
  API plan; without a token X is skipped. We use only the official API — never
  scraping, never bypassing access controls or ToS.
- **Bluesky (AT Protocol) public search — KEYLESS, real-time.** `app.bsky.feed.searchPosts`
  on **`api.bsky.app`** (the official public AppView host). This is our **legal, keyless
  real-time substitute for unauthenticated X reads** — many finance/journalist/breaking-news
  accounts cross-post here. Feeds both news items (`news.py`) and sentiment (`social.py`).
  Note: the older `public.api.bsky.app` host now returns 403 (edge block) from *all* IPs
  including residential — the fix was switching to `api.bsky.app`, which returns 200 with
  live posts and needs no credentials. Verified live (NVDA/TSLA/AMAT return 50 posts each).
- **Mastodon public hashtag timeline — KEYLESS, real-time.** `mastodon.social`
  `/api/v1/timelines/tag/<ticker>` public endpoint, toots classified by the bull/bear
  lexicon. Works from datacenter IPs too.
- StockTwits public symbol stream — uses explicit Bullish/Bearish labels. **Now behind a
  Cloudflare bot challenge** (returns 403 "Just a moment...") to keyless clients from every
  IP; we never bypass it, so it degrades gracefully and is skipped unless an official key
  path becomes available.
- Reddit search — the keyless `reddit.com/search.json` endpoint now returns 403; live Reddit
  requires the **official OAuth API** (free registered app: `REDDIT_CLIENT_ID` /
  `REDDIT_CLIENT_SECRET`). Skipped gracefully until those are configured.

Sentiment source order (first available wins): X (if token) → StockTwits → **Bluesky**
→ **Mastodon** → Reddit → news-derived fallback. Because Bluesky/Mastodon are keyless
and real-time, the Sentiment signal now reflects breaking microblog chatter even
without a paid X token, and is never empty.
- **News-derived sentiment (keyless fallback, always available)** — when the above
  are unreachable (datacenter IPs are routinely 403'd by StockTwits/Reddit, and X
  needs a paid token), `social.py::_from_news` classifies the **live multi-source
  news headlines** (Google/Yahoo/GDELT/Finnhub/yfinance) with the same transparent
  lexicon and reports a net bull/bear read plus the latest item timestamp. This
  reflects the real, recent news flow and is clearly labelled `news_derived` so it
  is never mistaken for retail chatter. It is still capped downstream so it cannot
  dominate a signal.

### 4b. GPU/LLM sentiment classifier (optional upgrade)

The default headline sentiment is a transparent finance **lexicon** (bag-of-words,
fully offline). When `ENABLE_LLM_SENTIMENT=true` **and** a local **Ollama** server
is reachable (`OLLAMA_BASE_URL` or `ADVISOR_PROVIDER=ollama`), headlines are scored
by a local GPU-accelerated LLM instead (`analysis/llm_sentiment.py`). It is strictly
opt-in and **always degrades to the lexicon** when Ollama is absent, slow, or returns
junk, so the daily scan never blocks on it. The model only scores polarity of
already-collected real headlines (it never invents news) and is capped downstream
exactly like the lexicon. Check liveness at `GET /advisor/health`.

### 4a. Keyless live macro (no FRED key required)

`ingestion/macro_fred.py` uses FRED when `FRED_API_KEY` is set, and otherwise pulls
a **real live macro regime from keyless sources** so the macro tab is never empty:

- yfinance market proxies: `^TNX` (10Y), `^FVX` (5Y), `^TYX` (30Y) Treasury yields,
  `^VIX`, `CL=F` (WTI crude), `DX-Y.NYB` (dollar index), plus a derived 10y-5y curve.
- U.S. Treasury FiscalData average interest rate on marketable debt (keyless).

The snapshot records its `source` (`fred` or `keyless_live …`) and an `as_of`
timestamp, both surfaced in the Jobs-tab macro summary.

Rules:

- Social sentiment is never enough by itself. (Implemented: capped to ±15 points and
  blended at 0.25 weight behind news at 0.75 inside the sentiment component.)
- Detect bot/spam risk; compare mention volume to baseline.
- Treat influencers and viral posts carefully.
- StockTwits/Reddit may block datacenter IPs (HTTP 403). The connectors degrade to
  `available=false` and record the attempt; set `STOCKTWITS_TOKEN` or run from a
  residential IP / your local Docker Desktop to enable them. We never bypass access controls.

## 5. Options Data

Implemented multi-source, multi-expiry collector (`ingestion/options_chain.py`),
real/delayed data only — never fabricated option prices. Source fallback:

```text
yfinance option_chain  ->  CBOE delayed-quotes JSON (keyless)  ->  unavailable
```

- For each ticker we select up to **5 short/medium-dated expirations** (default:
  **minimum 5 DTE**, preferring the 5–60 day window) and pull full calls/puts for
  each. `MIN_OPTION_DAYS_TO_EXPIRY` controls the floor; recommendation scoring
  never falls back below it.
- `yfinance` is primary. If it returns nothing, the **CBOE delayed-quotes JSON**
  (`https://cdn.cboe.com/api/global/delayed_quotes/options/<SYM>.json`, keyless) is
  parsed and reshaped into the same calls/puts frames so the engine is
  source-agnostic. The winning source is recorded on the chain (`source`) and shown
  under the ticker in the Options Edge tab.
- When no live chain exists from any source, the options engine degrades to a
  historical-volatility expected move and the row says so plainly.

Required fields (collected where the source provides them):

- Expiration, Strike, Call/put, Bid/ask/last, Volume, Open interest, Implied
  volatility, Greeks if available

Derived analytics (`analysis/options.py`):

- Put/call ratio, average IV, expected move (ATM straddle, else hist-vol), liquidity
  (total OI) and illiquidity flag, unusual volume, defined-risk vertical spread strikes
  from the 1σ expected move.
- **Per-expiry ranking (`analyze_expiries`)**: every collected expiration is scored on
  directional conviction (from the shared underlying analysis) × liquidity × IV penalty
  × days-to-expiry factor ± options-flow agreement, and the **top 3 expirations by
  confidence** are surfaced. Each carries a plain call — **BUY CALL (up ▲)** /
  **BUY PUT (down ▼)** / **NO TRADE (neutral →)** — a 0–100 confidence, and a
  traffic-light color (green = high/up, orange = caution/neutral, red = down/low).
- **Options Edge two-row layout (dashboard):** each expiry renders as **two lines** —
  line 1 = the numbers + an **Add trade** button (drops the idea into the Manual Trades
  tab); line 2 = a consolidated **Verdict** + the recommended **structure** + the full
  **Why (evidence)**. The **Confidence** column is the single consolidated 0–100 score
  (it already blends direction, data quality, algo confluence, liquidity, DTE, IV vs
  realized vol, Greeks/theta, flow, spread, IV-Rank, and event/earnings risk). The
  Verdict translates the risk gate into plain English: **✅ TRADEABLE** (trade the listed
  option), **⚠️ TRADE AS A SPREAD** (don't buy the naked option — rich IV/earnings/wide
  spread; use the defined-risk spread shown), **📝 PAPER ONLY** (track, don't risk real
  money), **🚫 NO TRADE** (no edge). The Add-trade button appears on every actionable
  row, labeled by gate (Add option / Add (spread leg) / Add (paper)).
- IV rank/percentile is implemented from accumulated point-in-time IV snapshots
  and is data-dependent until each ticker/expiry has enough observations. Options
  Edge also computes chain-derived ATM IV skew, next-expiry term-structure slope,
  unusual-activity score, and exact-contract OI-change versus stored snapshots.
  `/reliability/options-scorecard` measures option-premium P/L from later stored
  marks for the same exact contract; rows remain pending until future scans
  observe that contract again. Paid institutional unusual-flow/gamma vendors and
  full every-strike raw chain archiving remain future upgrades.

## 5a. Feature Store, Labels, and Calibration

Successful scans write point-in-time, label-free feature rows to
`data/historical_snapshots/feature_snapshots.jsonl`. The rows flatten the current
market snapshot, component scores/weights, forecast bands, options edge, event
radar, source coverage, freshness, and verdict fields exactly as seen at scan
time.

Labels are deliberately added later:

- `/reliability/labels` joins feature rows to matured forward equity outcomes
  after future bars exist.
- `/reliability/scorecard` measures equity directional hit rate/returns.
- `/reliability/options-scorecard` measures option-premium P/L from later stored
  contract marks.
- `/reliability/calibration` builds a saved confidence-bucket calibration profile.
  Live scans read that saved profile quickly and preserve raw confidence in
  `confidence_trace.raw_confidence_score`.

## 5b. Dashboard live-refresh UX

Every tab of the HTML dashboard shares a sticky toolbar with three controls, and
the active tab is **persisted** (URL hash + `localStorage`) so a reload keeps you
on the same tab instead of snapping back to Overview:

- **↻ Reload** — reloads the page and restores the current tab.
- **⟳ Live prices** — calls `/prices/refresh` and patches the current price and day
  change in the Overview + Current Prices tables in place (no full re-scan), then
  stamps a "Prices as of …" time in the toolbar.
- **▶ Re-scan** — POSTs `/jobs/run` for a full live re-scan, polls `/jobs/status`,
  and auto-reloads on completion while staying on the current tab.

## 5c. Parallel category refresh jobs (`refresh.py`)

The Jobs tab splits the refresh into **independent category jobs that run
concurrently in a thread pool** (`ThreadPoolExecutor`), so a "refresh all" is
bounded by the slowest source, not the sum. Measured ~3× speed-up (e.g. 5
categories: 40s parallel vs ~128s serial).

| Category | Source(s) refreshed |
|---|---|
| `market` | Latest real prices for the watchlist (provider fallback chain) |
| `news` | Multi-source company news merge (NewsAPI/Google/Yahoo/Finnhub/GDELT/yfinance) |
| `social` | StockTwits/Reddit bull-bear sentiment |
| `xtwitter` | Official X/Twitter API v2 — company + government (key-gated, never scraped) |
| `government` | Treasury/BLS/Federal Register/openFDA/DOJ-FTC/GDELT policy |
| `trump` | Trump administration / White House / executive-action news |
| `political` | Geopolitical + regulatory/policy reads (policy/antitrust/FDA/fiscal/labor) |
| `macro` | FRED/Treasury macro regime |
| `global` | US/Europe/Asia index levels (geopolitical risk-on/off) |
| `official_economic` | Grouped BLS/BEA/Census/FRED/Treasury/Fed/EIA/OFAC/Congress source coverage plus implemented macro/government pulls |
| `company_events` | SEC filings for the focused watchlist plus earnings calendar/company IR source coverage |
| `options_volatility` | Options chains for the focused watchlist plus Cboe/VIX/AAII/risk-sentiment source coverage |
| `reference_dashboards` | TradingView/Investing.com/Finviz/Koyfin/Reuters/Bloomberg/CNBC/MarketWatch/WSJ reference coverage, marked manual/licensed/context-only |
| `automation_apis` | Alpha Vantage/FMP/Nasdaq Data Link/Polygon/Massive API readiness and key status |
| `paid_platforms` | Bloomberg Terminal/LSEG/FactSet/S&P Capital IQ optional licensed upgrade status |
| `source_registry` | Full `config/analysis_source_registry.yml` source-priority map and market-day workflow |

Endpoints (in `api.py`):

- `POST /jobs/refresh-all` — fan all categories out in parallel from one call;
  `{"analyze": true}` chains the full prediction pipeline afterward ("the post
  should analyze") and writes fresh reports in the background.
- `POST /jobs/refresh/{category}` — refresh a single category synchronously.
- `GET /jobs/refresh-status` — last-refresh time + one-line summary per category.

Thread-safety: each job is network-read-only and returns its own summary (no shared
mutable evidence store). The three government-derived categories share one cached
`fetch_government()` snapshot (90s TTL) so a parallel run does **one** GDELT-throttled
fetch instead of three.

The scheduled/manual full collection path (`python -m eaglesignal collect`,
`/jobs/run`, and the Windows scheduled scripts) now runs these grouped refresh
jobs first, then runs the prediction pipeline. That keeps automated and manual
refresh behavior aligned.

## 5c. Additional Options, Volatility, And Daily Workflow Sources

Additional target sources:

- Cboe Daily Market Statistics for VIX, put/call ratio, and market-wide options stats.
- Cboe VIX page for official volatility context.
- AAII Sentiment Survey for weekly retail sentiment.
- CNN Fear & Greed / MacroMicro as supporting sentiment/risk indicators only.

Use this source order every market day:

| Time | Check | Preferred sources |
|---|---|---|
| Before market open | Futures, Treasury yields, oil, dollar, VIX, economic calendar | Investing.com, TradingView, MarketWatch calendar, Treasury, Cboe |
| 8:30 AM ET releases | CPI, jobs, PCE, GDP, retail sales, jobless claims | BLS, BEA, Census, FRED |
| During market | SPY, QQQ, IWM, sector ETFs, VIX, bond yields, top movers, unusual options | TradingView, Finviz, Cboe, Koyfin |
| After market | Earnings, guidance, SEC 8-K filings, analyst reactions | Nasdaq earnings, SEC EDGAR, Reuters, Seeking Alpha, company IR |
| Weekend | Macro trend, Fed probabilities, sector rotation, next week's earnings, geopolitical risks | FRED, CME FedWatch, TradingView, Investing.com, Reuters, official government sources |

## 5d. Event calendars (economic / political / company)

`ingestion/calendars.py` provides honest, mostly-keyless event calendars that feed
the engine's **event-risk awareness** (a high-impact event inside a prediction's
horizon reduces confidence — see "measured, not guessed"):

- **Economic / political (FOMC):** FOMC decision days are read from the curated
  `config/event_calendar.yml` — only officially-published dates from the Federal
  Reserve calendar, never guessed. Update annually.
- **Rule-derivable macro releases:** monthly **non-farm payrolls** (first Friday,
  high impact) and weekly **initial jobless claims** (Thursdays, medium impact) are
  generated deterministically. CPI/PCE/GDP exact dates drift month to month and are
  intentionally **not fabricated** — add them to the YAML when the official date is
  known.
- **Company calendar:** next earnings date per ticker, pulled live (keyless) from the
  earnings connector and also surfaced per-prediction on
  `options_trade_idea.earnings`.

API: `GET /calendar?days=21` (instant, market/macro only) and
`GET /calendar?days=21&include_earnings=true` (adds live per-ticker earnings; slower).

## 6. Data Freshness SLA

| Data type | Freshness target |
|---|---:|
| Intraday price | 1-15 minutes when market open |
| Daily price | Same day after close |
| Options chain | 1-15 minutes for options alerts |
| SEC filings | Same day/event-driven |
| Macro data | On official release schedule |
| News | Near-real-time where available |
| Social | Intraday/daily |
| Fundamentals | Latest filing cycle |

## 7. Source Reliability Ranking

| Rank | Source type |
|---:|---|
| 100 | Official SEC/government/company filing/source |
| 90 | Exchange or licensed market data provider |
| 80 | Reputable financial news provider |
| 70 | Established data aggregator |
| 50 | General web search result |
| 35 | Social media / forum |
| 10 | Anonymous rumor / unverified content |

## 8. Source Connector Configuration Example

```yaml
sources:
  sec:
    enabled: true
    base_url: "https://data.sec.gov"
    rate_limit_per_second: 5
  fred:
    enabled: true
    api_key_env: "FRED_API_KEY"
  bls:
    enabled: true
    api_key_env: "BLS_API_KEY"
  bea:
    enabled: true
    api_key_env: "BEA_API_KEY"
  market_data:
    provider: "yfinance_dev"
  news:
    provider_priority:
      - company_ir
      - sec
      - serpapi
      - brave
      - tavily
  social:
    x_enabled: false
    reddit_enabled: false
```

## 9. Compliance Notes

- Respect every source’s terms and robots.txt.
- Prefer APIs over scraping.
- Add user-agent information for official API access when required.
- Do not use private data or insider information.
- Do not bypass paywalls or access controls.
