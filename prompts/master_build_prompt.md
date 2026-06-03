# MASTER_AI_PROMPT.md

Copy this entire prompt into ChatGPT, Claude, Cursor, Windsurf, GitHub Copilot, or any agentic coding tool when you want it to build the project.

---

## Master Build Prompt: USA Stock Market Prediction Automation

You are a **principal AI engineer, quantitative research architect, financial data engineer, options analyst, macro analyst, DevSecOps architect, and product strategist**.

Build a production-ready, modular, open-source-ready software project named:

```text
USA-Stock-Market-prediction
```

Product brand name:

```text
EagleSignal AI
```

The system must predict, score, explain, and monitor U.S. market opportunities for:

- U.S. equities
- U.S. stock options
- U.S. ETFs
- U.S. indexes

Do **not** include crypto, forex-only trading, sports betting, gambling, or unrealistic “guaranteed profit” claims.

## Primary Goal

Create an all-in-one AI automation and workflow system that crawls, ingests, normalizes, analyzes, scores, backtests, and reports market intelligence from every relevant angle without losing context.

It must analyze:

1. U.S. stock price action
2. Options chain data
3. Company financial statements
4. SEC filings
5. Earnings reports
6. Company news
7. Company contracts, agreements, lawsuits, patents, product launches, leadership changes
8. Local and international economic conditions
9. U.S. government announcements
10. Federal Reserve statements and data
11. Treasury yield curve and auctions
12. Labor market and job reports
13. Inflation reports
14. GDP and consumer data
15. Political news
16. Geopolitical news
17. Global market correlations
18. Sector rotation
19. Social sentiment from public and legal sources
20. X/Twitter comments where official API/legal access exists
21. Reddit/StockTwits/forum sentiment where allowed
22. Socioeconomic indicators affecting material, energy, defense, healthcare, banks, technology, AI, semiconductor, real estate, retail, and industrial stocks

The analysis checklist must be documented in `MARKET_FACTOR_CHECKLIST.md` and used as the required coverage map for recommendations. It must cover company fundamentals, valuation, macro, government/policy, geopolitics, sector trends, sentiment, technicals, options, liquidity, institutional flows, bonds/credit, currency, commodities, global correlation, news/events, earnings calls, seasonal/calendar effects, volatility/risk, alternative data, AI/technology factors, index factors, and black-swan risk.

The source registry must be documented in `config/analysis_source_registry.yml` and used as an additive source-priority map. Keep all existing connectors, then add TradingView, Investing.com, Finviz, Reuters, SEC EDGAR, BLS/BEA/FRED, Cboe, Census, Federal Reserve/FOMC, CME FedWatch, Treasury, EIA, OFAC, Federal Register, Congress.gov, White House, Nasdaq earnings calendar, company IR, AAII, CNN Fear & Greed, MacroMicro, Bloomberg/LSEG/FactSet/S&P Capital IQ Pro, Alpha Vantage, FMP, Nasdaq Data Link, and Polygon/Massive as target sources where legal/API/licensed access exists. Monitoring dashboards are useful, but high-confidence recommendations must verify important signals from official primary or licensed sources.

## Non-Negotiable Behavior

The AI must:

- Preserve full context across all analysis stages.
- Never use one weak signal as final truth.
- Compare bullish, bearish, and neutral evidence.
- Produce evidence-backed reasoning with links.
- Include uncertainty and invalidation points.
- Use time-series-safe validation for ML.
- Avoid data leakage.
- Rank sources by reliability.
- Detect stale, duplicate, low-quality, or manipulative news.
- Refuse to create guaranteed-profit claims.
- Clearly state “research only, not financial advice.”

## Inspiration From Existing Repositories

Use these as concept references only. Do not copy code blindly.

1. `ZhuLinsen/daily_stock_analysis`
   - Useful concepts: AI decision dashboard, multi-source market/news aggregation, scheduled analysis, notification channels, Markdown reports, GitHub Actions/Docker/FastAPI style deployment.
   - Improve with: U.S. government data, SEC filings, options analytics, evidence traceability, risk controls.

2. `dfdezdom/investdaytip`
   - Useful concepts: 0-100 multi-factor scoring, asset-specific models, concurrent fetching, CLI output, HTML export, pure/testable scoring functions, advisor mode.
   - Improve with: options flow, macro regime engine, geopolitical risk, model calibration, alerting.

3. `myhhub/stock`
   - Useful concepts: technical indicators, candlestick pattern recognition, strategy screening, backtesting, scheduled jobs, web dashboard.
   - Improve with: U.S. market adaptation, read-only safety, API-first architecture, clean Python packaging.

4. `SumanthT26/USA-Stock-Market-prediction-using-Financial-Fundamental-data`
   - Useful concepts: financial statement features, EDA, preprocessing, model building.
   - Improve with: live SEC/XBRL data, continuous feature store, forward-looking validation.

5. `EvotecIT/UnifiStockTracker`
   - Useful concepts: targeted monitoring and alerts instead of noisy broad notifications.
   - Improve with: ticker/event watchlists, priority scoring, alert deduplication, risk-aware notifications.

## Required Documentation Files

Create these files first:

```text
README.md
MASTER_AI_PROMPT.md
SKILLS.md
WORKFLOW.md
ARCHITECTURE.md
DATA_SOURCES.md
MARKET_FACTOR_CHECKLIST.md
PRODUCT_REQUIREMENTS.md
ROADMAP.md
.env.example
.github/workflows/market_prediction.yml
```

## Required Engineering Architecture

Use this layered architecture:

```text
1. Scheduler Layer
2. Source Connectors Layer
3. Ingestion Layer
4. Normalization Layer
5. Entity Resolution Layer
6. Evidence Store
7. Feature Store
8. Analysis Engines
9. Prediction Models
10. LLM Reasoning Layer
11. Risk Manager
12. Report Generator
13. Alerting System
14. Web Dashboard/API
15. Observability and Audit Layer
```

## Required Skill Registry

All skills must be defined in one canonical file:

```text
SKILLS.md
```

The skill file must allow future skills to be appended easily. Each skill must include:

- Skill ID
- Purpose
- Inputs
- Outputs
- Required data freshness
- Source reliability requirements
- Validation checks
- Failure behavior
- Dependencies
- Example output fields

## Required Analysis Engines

Build or design the following engines:

### 1. Market Price Engine

Analyze:

- OHLCV
- Gap up/down
- Intraday trend
- Pre-market and after-hours movement
- Relative volume
- VWAP
- Moving averages
- Support/resistance
- Momentum
- Mean reversion
- Volatility expansion/contraction

### 2. Technical Indicator Engine

Compute:

- SMA/EMA
- MACD
- RSI
- Bollinger Bands
- ATR
- ADX/DMI
- OBV
- VWAP
- Stochastic RSI
- CCI
- MFI
- Supertrend
- Ichimoku where possible
- Candlestick patterns

### 3. Options Intelligence Engine

Analyze:

- Options chain
- Implied volatility
- Historical volatility
- IV rank/percentile
- Put/call ratio
- Open interest
- Volume/open-interest anomalies
- Gamma exposure estimate
- Delta exposure estimate
- Skew
- Term structure
- Expected move
- Earnings IV crush risk
- Unusual options activity
- Max pain as low-confidence contextual data only

### 4. Fundamental Engine

Analyze:

- Income statement
- Balance sheet
- Cash flow
- Revenue growth
- EPS growth
- Margins
- Debt
- Free cash flow
- Valuation ratios
- Guidance changes
- Analyst revisions if legally available
- Insider transactions if publicly disclosed
- 10-K, 10-Q, 8-K, S-1, DEF 14A, 13F, Form 4

### 5. SEC Filing Engine

Extract:

- New filings
- Material events
- Risk factors
- Management discussion
- Revenue segment changes
- Contract disclosures
- Going concern warnings
- Legal proceedings
- Insider transactions
- Restatements

### 6. Macro and Economic Engine

Analyze:

- CPI
- PPI
- PCE
- GDP
- unemployment
- payrolls
- job openings
- wages
- retail sales
- manufacturing/services PMI where available
- yield curve
- Fed funds expectations
- Treasury yields
- dollar strength
- oil/energy prices
- credit spreads where available

### 7. Government and Policy Engine

Monitor:

- Federal Reserve
- Treasury
- SEC
- CFTC
- BLS
- BEA
- Census
- White House
- Congress
- FTC/DOJ antitrust updates
- FDA approvals for healthcare stocks
- DOE/EIA for energy
- DOD contracts for defense stocks
- Commerce export controls for semiconductor/AI stocks

### 8. News and Event Engine

Analyze:

- Breaking news
- Company announcements
- Earnings news
- Product launches
- Contracts and agreements
- M&A rumors vs confirmed news
- Lawsuits and investigations
- Regulatory approvals/rejections
- Layoffs/hiring expansions
- Supply chain events
- International events

### 9. Social Sentiment Engine

Analyze public/legal sources only:

- X/Twitter official API if available
- Reddit API where permitted
- StockTwits if available
- News comments only when allowed
- Sentiment polarity
- emotion intensity
- bot/spam likelihood
- volume spike vs baseline
- influencer/source credibility

### 10. Cross-Market Correlation Engine

Compare:

- U.S. indexes
- Sector ETFs
- Bonds and yields
- VIX
- Dollar index proxies
- Oil
- Gold
- Global indexes
- Related competitors
- Supplier/customer stocks
- Semiconductor index for AI/tech names
- Bank index for financial names

### 11. Prediction Engine

Produce:

- Direction probability
- Expected move
- Risk-adjusted score
- Confidence interval
- Feature importance
- Scenario analysis
- Contradictory evidence

Models may include:

- Logistic regression baseline
- Random forest
- XGBoost/LightGBM if available
- Time-series models
- Anomaly detection
- Ensemble voting
- LLM reasoning as explanation layer only, not the sole predictor

### 12. Backtesting Engine

Required:

- Walk-forward validation
- No lookahead bias
- No survivorship bias where avoidable
- Slippage model
- Transaction costs
- Options bid/ask spread assumptions
- Sharpe/Sortino/drawdown/win rate
- Confusion matrix for directional predictions
- Calibration curve for probabilities

### 13. Risk Manager

Must enforce:

- Avoid low-liquidity options
- Avoid overconcentration
- Avoid earnings IV crush traps
- Avoid trading when news is stale or contradictory
- Flag high-risk events
- Require invalidation levels
- Show position-sizing warning
- Show “no trade” when signal quality is weak

### 14. Report Generator

Generate:

- Markdown report
- HTML dashboard
- JSON output
- CSV summary
- Watchlist alerts
- Daily market brief
- Premarket brief
- After-market review
- Weekly trend review

## Required Scoring System

Use a transparent weighted score:

```text
Total Score =
  15% technical structure
+ 15% price/volume/momentum
+ 15% fundamentals
+ 15% options intelligence
+ 10% macro regime
+ 10% news/events
+ 10% sentiment
+ 5% cross-market correlation
+ 5% risk penalty adjustment
```

Allow weights to be configurable by strategy:

- Intraday
- Swing trading
- Earnings
- Long-term investment
- Options premium buying
- Options premium selling
- Index trend following

## Required Output Example

For every analyzed asset, output this schema:

```json
{
  "ticker": "AAPL",
  "asset_type": "equity",
  "time_horizon": "5D",
  "direction": "neutral_to_bullish",
  "total_score": 72,
  "confidence": 64,
  "expected_move_pct": "-2.1% to +4.8%",
  "technical_score": 70,
  "fundamental_score": 78,
  "options_score": 66,
  "macro_score": 62,
  "news_score": 75,
  "sentiment_score": 68,
  "risk_level": "medium",
  "key_bullish_evidence": [],
  "key_bearish_evidence": [],
  "catalysts": [],
  "invalidation_conditions": [],
  "data_freshness": {},
  "source_links": [],
  "disclaimer": "Research only, not financial advice."
}
```

## Required Automation Workflow

Create scheduled workflows:

1. Premarket scan
2. Market open volatility scan
3. Midday update
4. Power-hour scan
5. After-market earnings/filings scan
6. Weekend deep research scan
7. Event-triggered urgent alert

Use GitHub Actions first, then optionally Docker, local cron, FastAPI, and cloud deployment.

## Required Source Priority

Prefer:

1. Official government APIs
2. Exchange or issuer data
3. SEC filings
4. Company investor relations
5. Reputable financial news APIs
6. Paid market data APIs if configured
7. Public social APIs
8. General web search as fallback only

## Required Quality Guardrails

Before producing any prediction:

- Check data freshness.
- Check source reliability.
- Check conflicting evidence.
- Check event calendar.
- Check earnings date.
- Check market regime.
- Check liquidity.
- Check options spread.
- Check abnormal volatility.
- Check whether the signal was backtested.
- Check whether model confidence is calibrated.

## Required Developer Tasks

Build the project in phases:

### Phase 1: Documentation and architecture

- Create all Markdown files.
- Create `.env.example`.
- Create GitHub Actions workflow skeleton.
- Create source connector interfaces.

### Phase 2: MVP data pipeline

- Load ticker watchlist.
- Pull market data.
- Pull fundamentals.
- Pull SEC filings.
- Pull macro data.
- Store raw and normalized data.

### Phase 3: Scoring and report

- Implement scoring functions.
- Generate Markdown/HTML report.
- Add JSON output.
- Add evidence links.

### Phase 4: Options and risk

- Add options chain ingestion.
- Add IV/Greeks/open interest analytics.
- Add risk filters.

### Phase 5: Backtesting and ML

- Add walk-forward backtest.
- Add baseline models.
- Add calibration.
- Add feature importance.

### Phase 6: Dashboard and alerts

- Add FastAPI.
- Add dashboard.
- Add Slack/Discord/Telegram/email alerts.

### Phase 7: Agentic workflow

- Add LLM agent to read evidence store.
- Add structured reasoning.
- Add contradiction detection.
- Add final research memo generator.

## Final Instruction

Start by creating the documentation files exactly as specified. Then generate a clean Python project skeleton with tests. Keep modules small, testable, and replaceable. Never hard-code secrets. Every prediction must be evidence-backed, risk-adjusted, and non-guaranteed.
