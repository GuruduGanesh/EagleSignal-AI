# PRODUCT_REQUIREMENTS.md

## Product Requirements Document

### Product Name

EagleSignal AI / USA-Stock-Market-prediction

### Product Type

AI-powered U.S. stock market prediction, options intelligence, macro/news crawler, and decision-support dashboard.

## 1. Problem

Retail investors and engineers trying to analyze markets face too much fragmented information:

- Price charts
- Options flow
- SEC filings
- Earnings calls
- Government reports
- Political/geopolitical news
- Social sentiment
- Macro indicators
- Sector rotation

Most tools look at only one or two of these areas. The goal is to create one system that combines all of them and explains why a prediction was produced.

## 2. Users

Primary users:

- Individual market researchers
- Retail investors
- Quant learners
- Data science students
- SRE/DevOps engineers building AI automation portfolios
- Technical analysts who want AI-assisted research

Secondary users:

- Small investment clubs
- Newsletter writers
- Research automation builders

## 3. Core Jobs To Be Done

1. “Tell me which U.S. stocks/options/indexes deserve attention today.”
2. “Explain why the system is bullish/bearish/neutral.”
3. “Show evidence, sources, and confidence.”
4. “Warn me when a major filing/news/macro event changes the thesis.”
5. “Avoid noisy alerts and low-quality signals.”
6. “Backtest whether the signal has worked historically.”
7. “Track Trump/admin policy news and show whether it affects my watched symbols.”
8. “Enter my own trade price and track day-by-day profit/loss against live/current prices.”
9. “Keep the active universe small and focused on the current top niche/news-driven tickers, not all scripts.”
10. “Show both bullish and bearish/short research ideas with a final verdict.”
11. “Detect SNDK-style event moves early and warn when a move becomes exhausted.”
12. “Run collection automatically every two hours when my laptop is on, with retry and browser manual trigger.”
13. “Show which required market-factor groups were considered before the final recommendation.”
14. “Use a clear source-priority registry so monitoring dashboards, official primary sources, paid platforms, APIs, and sentiment sources are weighted correctly.”

## 4. MVP Features

- Watchlist input
- Daily price data ingestion
- Technical indicator calculation
- SEC company facts and latest filings
- Basic macro data ingestion
- News collection through configured provider
- Multi-factor scoring
- Markdown report
- JSON signal output
- GitHub Actions schedule
- Risk/disclaimer guardrails
- Trend impact table: price move, news volume/providers, evidence polarity, policy links, social signal, forecast tilt
- Bull/Bear Verdicts table: final verdict, research action, opportunity, confidence, risk, and reasons
- Event Radar table: breakout score, exhaustion score, 20D/60D/252D returns, volume expansion, bullish clues, bearish clues
- Confidence Traces table: coverage/agreement math, available/missing engines, evidence count, raw signal links, and source links
- Options Edge table: short-term bias, underlying current price, option contract/premium, bid/ask, bid/ask spread %, readiness, option-quality score, lot size, volume, OI, put/call, defined-risk strategy idea, expiration, IV, and warnings
- Options trade quick-add: directional option rows must add the selected option contract to Manual Trades with premium entry, one-contract quantity by default, underlying symbol, and 100-share multiplier
- Sortable tables in every dashboard tab
- Theme Watchlists table with live verdict/trend columns for actively scored tickers
- Manual trade journal for user-entered entry price, quantity, notes, current mark, and P/L
- Manual trade quick-add from Overview and Options Edge using the current displayed market price, with edit/delete controls preserved
- Jobs panel: run now, refresh status, latest attempt, success/failure, report paths
- Jobs panel grouped refresh: manual and scheduled runs must refresh all source groups in parallel before analysis, so one slow/failing group does not block the rest
- Refresh cadence: live/current prices every 10 minutes while the dashboard is open; grouped source jobs every 30 minutes; scheduled intraday grouped refresh plus focused re-analysis every 30 minutes during market hours
- Market factor checklist coverage based on `MARKET_FACTOR_CHECKLIST.md`, showing considered, missing, bullish, bearish, and confidence-reducing factor groups
- Source registry coverage based on `config/analysis_source_registry.yml`, showing which sources are implemented, manual/reference, API-gated, licensed/paid, or planned

## 5. V1 Features

- Options chain analytics
- IV rank/percentile
- Put/call ratio
- Expected move
- Earnings IV risk
- HTML dashboard
- Alert deduplication
- Email/Slack/Discord/Telegram alerts
- Walk-forward backtesting
- Prediction audit log
- Factor coverage auditor across the 23 required analysis groups

## 6. V2 Features

- FastAPI backend
- Streamlit/React dashboard
- Advanced ML models
- Social sentiment
- Geopolitical event engine
- Government contract mapper
- Trump/admin policy impact mapper
- Theme watchlists for policy-adjacent and AI/GPU/storage/chips/robotics/space research baskets
- Sector exposure graph
- Portfolio risk view
- Agentic Q&A over evidence store
- Scheduled local worker profiles for Windows Task Scheduler and Docker

## 7. Success Metrics

Engineering metrics:

- Data ingestion success rate > 95%
- Report generation success rate > 99%
- No secrets in logs or code
- Unit test coverage for scoring functions
- Alert deduplication reduces repeated alerts

Prediction quality metrics:

- Directional accuracy by horizon
- Calibration score
- False positive rate
- Max drawdown in backtests
- Sharpe/Sortino in strategy simulations
- Accuracy split by market regime

User metrics:

- Daily report usefulness
- Alert precision
- Time saved in research
- Reduced noisy notifications

## 8. Non-Goals

- No automatic real-money trading in MVP.
- No guaranteed profit claims.
- No insider/private data usage.
- No crypto/forex-only trading.
- No scraping behind logins or paywalls.

## 9. Risk Controls

Every recommendation must include:

- Confidence score
- Risk level
- Evidence links
- Bullish and bearish arguments
- Invalidation conditions
- Liquidity warning
- Event risk warning
- Disclaimer

## 10. User Stories

### Story 1: Premarket Research

As a user, I want a premarket report that summarizes top movers, catalysts, macro events, and risk so I can prepare before market open.

### Story 2: Options Setup

As a user, I want to know whether an options setup has acceptable liquidity, IV, expected move, and risk before I consider it.

### Story 3: SEC Filing Alert

As a user, I want to be alerted when a company on my watchlist files a material 8-K, 10-Q, 10-K, or Form 4.

### Story 4: Macro Impact

As a user, I want the system to explain how jobs, inflation, GDP, Fed, and Treasury data may affect indexes and sectors.

### Story 5: Explainable Prediction

As a user, I want every prediction to show component scores and evidence so I can trust or reject the signal.
