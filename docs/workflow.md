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
| Local Scheduled Collection | Every 2 hours while laptop is on | Refresh focused watchlist with retry | Dashboard/report update |

## 2. End-to-End Pipeline

```text
Scheduler
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
- Company press releases
- SEC filings since prior close
- Options data where available

### Required Steps

1. Load watchlist.
   - Keep the default scope focused: SPY/QQQ context plus MU, AMD, AVGO, NVDA, INTC, META, GOOGL, AMZN, TSM, SMCI, AMAT, OKLO, and SNDK.
   - Do not scan all scripts by default.
2. Pull premarket data.
3. Pull latest news and filings.
4. Pull macro calendar.
5. Identify gap movers.
6. Detect catalysts.
7. Compute preliminary score.
8. Apply risk filters.
9. Generate premarket report.
10. Send only high-priority alerts.

### Output Sections

- Market regime
- Top bullish candidates
- Top bearish candidates
- Avoid/no-trade list
- Major news catalysts
- Government/macro events today
- Options risk warnings
- Confidence and invalidation conditions

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
- Geopolitical shock affecting market
- Options activity anomaly confirmed
- SNDK-style abnormal stock move or exhaustion reversal

Alert must include:

- Event summary
- Event Radar verdict
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

## 13. Required Report Naming

```text
reports/YYYY-MM-DD/premarket_report.md
reports/YYYY-MM-DD/intraday_update.md
reports/YYYY-MM-DD/after_market_report.md
reports/YYYY-MM-DD/weekly_deep_scan.md
reports/YYYY-MM-DD/signals.json
reports/YYYY-MM-DD/audit_log.jsonl
```
