# WORKFLOW.md

## USA-Stock-Market-prediction Automation Workflow

This workflow defines how EagleSignal AI should run throughout the market day.

> All workflows must output research only, not financial advice.

## 1. Workflow Summary

| Workflow | When | Purpose | Output |
|---|---:|---|---|
| Premarket Scan | 6:00-8:30 AM ET | Find gap movers, news, macro events, options setup | Premarket Markdown/HTML report |
| Market Open Volatility Scan | 9:30-10:15 AM ET | Detect abnormal volume, gap continuation/fade | Intraday alert candidates |
| Midday Update | 12:00 PM ET | Re-score watchlist after morning action | Updated score table |
| Power Hour Scan | 3:00-3:45 PM ET | Detect closing strength/weakness and options positioning | Power-hour alerts |
| After-Market Scan | 4:30-7:00 PM ET | Earnings, SEC filings, guidance, after-hours moves | After-market report |
| Weekend Deep Scan | Saturday/Sunday | Fundamental, macro, backtest, sector rotation | Weekly report |
| Event Trigger | Any time | Breaking news, filing, Fed/CPI/jobs/FDA/DOD event | Urgent alert |
| Local Scheduled Collection | 9:00 AM America/Chicago daily | Run the single automatic refresh, analysis, and report write | Dashboard/report update |
| Browser Price Refresh | Manual | Patch current market prices without a full scan | Updated visible price cells |
| Browser Manual Collection | On demand from Dashboard -> Jobs | Run the same grouped refresh and analysis job immediately | Queued job + status |

## 2. End-to-End Pipeline

```text
Scheduler
  -> Parallel Source Groups
  -> Source Connectors
  -> Raw Data Storage
  -> Data Normalization
  -> Entity Resolution
  -> Evidence Store
  -> Feature Store
  -> Analysis Engines
  -> Prediction Engine
  -> Risk Manager
  -> LLM Reasoning Agent
  -> Report Generator
  -> Alert Deduplicator
  -> Notification Sender
  -> Audit Logger
```

## 3. Premarket Scan

### Inputs

- Watchlist tickers
- Index futures or proxy ETFs
- Premarket prices
- Overnight global market performance
- Latest U.S. and international news
- Government/Fed/Treasury calendar
- Trump administration / White House / Federal Register / tariff / export-control policy headlines
- Daily verification stack from `config/analysis_source_registry.yml`: TradingView, Investing.com, Finviz, Reuters, SEC EDGAR, BLS/BEA/FRED, and Cboe
- Company press releases
- SEC filings since prior close
- Options data where available

### Required Steps

1. Load watchlist.
   - Active scope is intentionally small: SPY/QQQ for market context plus MU, AMD, AVGO, NVDA, INTC, META, GOOGL, AMZN, TSM, ASML, LRCX, SMCI, DELL, HPE, WDC, AMAT, OKLO, PLTR, ISRG, RKLB, and SNDK.
   - Do not expand to all scripts. Add a symbol only when it is a top niche or highly news-driven research target.
2. Pull premarket data.
3. Pull latest news and filings.
4. Pull macro calendar.
   - Verify major economic releases from official BLS, BEA, Census, FRED, Treasury, or Federal Reserve sources where available.
   - Use TradingView, Investing.com, Finviz, Koyfin, and Reuters as dashboard/reference sources, not as sole truth for high-confidence trades.
5. Identify gap movers.
6. Detect catalysts.
7. Compute preliminary score.
8. Apply risk filters.
9. Run the market-factor checklist from `MARKET_FACTOR_CHECKLIST.md`.
   - Mark which factor groups were considered.
   - Mark which factor groups were missing, stale, or source-limited.
   - Separate bullish factors from bearish factors.
   - Reduce confidence when important groups are missing or contradictory.
10. Run the source registry check from `config/analysis_source_registry.yml`.
   - Prefer official/company/exchange/licensed sources over dashboards and opinion sources.
   - Mark delayed/manual/paywalled/context-only sources in the confidence trace.
   - Treat social, Substack, X accounts, Seeking Alpha opinions, and rumor desks as context until confirmed.
11. Refresh grouped source jobs in parallel when run manually or by the 9:00 AM schedule:
   - Market, news, sentiment, X/Twitter, government, Trump/admin, political/geopolitical, macro, global.
   - Official economic, company events, options/volatility, reference dashboards, automation APIs, paid platforms, source registry.
12. Analyze focused tickers in parallel after shared macro/government/global context is collected.
13. Generate premarket report.
14. Send only high-priority alerts.

### Output Sections

- Market regime
- Top bullish candidates
- Top bearish candidates
- Avoid/no-trade list
- Major news catalysts
- Government/macro events today
- Options risk warnings
- Confidence and invalidation conditions
- Confidence trace links: `/ticker/{symbol}`, `/signals`, and top source URLs
- Short-term options edge: bias, strategy idea, nearest expiration, IV, put/call, liquidity, and warning
- Manual trade action: dashboard buttons can add a long/short tracking row at the current displayed price; the journal then supports edit/delete and live P/L refresh

## 4. Market Open Volatility Scan

### Purpose

Confirm or reject premarket signals after real volume appears.

### Checks

- Price vs VWAP
- Opening range breakout/breakdown
- Relative volume
- Spread/liquidity
- News confirmation
- Options flow confirmation

### Alert Rule

Send alert only if:

```text
score >= configured threshold
AND liquidity_score is acceptable
AND event risk is known
AND duplicate alert not sent recently
AND source evidence is fresh
```

## 5. Midday Update

### Purpose

Reduce noise after opening volatility and update signal quality.

### Required Steps

- Recalculate technical and volume signals.
- Re-check breaking news.
- Re-score options activity.
- Compare morning prediction vs realized move.
- Adjust confidence.

## 6. Power Hour Scan

### Purpose

Detect institutional closing behavior and next-day setup.

### Signals

- VWAP reclaim/loss
- Closing range strength
- Relative volume
- Options flow into close
- Index/sector confirmation
- News after 2 PM ET

## 7. After-Market Scan

### Purpose

Handle earnings, SEC filings, guidance changes, and after-hours market moves.

### Required Sources

- SEC filings
- Company investor relations pages
- Earnings press releases
- Earnings call transcript provider if available
- After-hours price data
- Options expected move and IV crush risk

### Output

- Earnings winners/losers
- Filings with material impact
- Guidance changes
- Next-day watchlist
- Risk warnings

## 8. Weekend Deep Scan

### Purpose

Run slower and deeper analysis.

### Tasks

- Recalculate weekly technicals.
- Update fundamentals.
- Pull latest SEC filings.
- Analyze macro regime.
- Analyze sector rotation.
- Review backtest performance.
- Update watchlist ranking.
- Generate weekly strategic report.

## 9. Event-Driven Urgent Alert Workflow

Trigger when:

- 8-K filed
- Earnings released
- Fed decision/speech/minutes
- CPI/PPI/PCE/jobs/GDP release
- Major company contract announced
- FDA approval/rejection
- DOD contract award
- Major lawsuit/antitrust action
- Trump/admin executive order, tariff, sanctions, export-control, AI/data-center, defense, energy, or space policy change
- Geopolitical shock affecting market
- Options activity anomaly confirmed
- SNDK-style abnormal stock move: high 20D/60D/252D return, fresh catalyst density, volume expansion, analyst revision, earnings/guidance surprise, supply-demand reset, or sudden exhaustion/reversal from highs

Alert must include:

- Event summary
- Event Radar verdict: bullish event watch, early event watch, bearish exhaustion watch, or no major event
- Source link
- Affected tickers/sectors
- Possible bullish/bearish impact
- Confidence
- Risk warning
- “Wait for confirmation” warning when needed

## 10. Context Preservation Rules

The system must not lose context between modules.

For every ticker, maintain:

```json
{
  "ticker": "TSLA",
  "current_market_context": {},
  "company_context": {},
  "macro_context": {},
  "news_context": {},
  "options_context": {},
  "technical_context": {},
  "risk_context": {},
  "options_trade_idea_context": {},
  "trend_impact_context": {},
  "event_radar_context": {},
  "final_verdict_context": {},
  "confidence_trace_context": {},
  "market_factor_checklist_context": {},
  "source_registry_context": {},
  "manual_trade_context": {},
  "previous_predictions": [],
  "evidence_ids": []
}
```

## 11. Alert Severity

| Severity | Meaning | Action |
|---|---|---|
| P0 | Major event likely affecting market/large ticker immediately | Send urgent alert |
| P1 | Strong signal with fresh evidence and liquidity | Send normal alert |
| P2 | Watchlist update only | Include in report |
| P3 | Weak/stale/conflicting signal | Store, no alert |

## 12. Failure Handling

If one source fails:

1. Retry with backoff.
2. Use secondary source if configured.
3. Mark missing data in report.
4. Reduce confidence.
5. Do not hallucinate missing data.
6. Continue other grouped refresh jobs in parallel so one failed source does not block all analysis.

## 13. Required Report Naming

```text
reports/YYYY-MM-DD/premarket_report.md
reports/YYYY-MM-DD/intraday_update.md
reports/YYYY-MM-DD/after_market_report.md
reports/YYYY-MM-DD/weekly_deep_scan.md
reports/YYYY-MM-DD/signals.json
reports/YYYY-MM-DD/audit_log.jsonl
```
