# REFERENCE_ANALYSIS.md

## Reference Repository Analysis

This file summarizes how to use the provided repositories as design references.

## 1. ZhuLinsen/daily_stock_analysis

### Observed strengths

- AI-generated decision dashboard
- Multi-source market and news aggregation
- Scheduled automation
- Multi-channel push notifications
- Markdown-style reports
- Web/API/Bot style architecture
- Support for multiple markets and sources

### What to borrow conceptually

- Daily decision dashboard format
- Multi-source fallback design
- Scheduled GitHub Actions workflow
- Multi-channel notification strategy
- “Core conclusion + score + risk + catalyst + checklist” report style

### What to improve

- Focus on U.S. equities/options/indexes
- Stronger SEC/government/macro data integration
- Better options intelligence
- Backtesting and probability calibration
- Evidence store and audit log

## 2. dfdezdom/investdaytip

### Observed strengths

- Multi-factor 0-100 scoring
- Stocks and ETFs handled separately
- Multi-region filtering
- Concurrent fetching
- CLI report output
- HTML export with filters and sorting
- Testable scoring functions
- Advisor mode

### What to borrow conceptually

- Composite score design
- Pure scoring functions
- CLI-first MVP
- HTML report export
- Advisor/research assistant mode

### What to improve

- Add options and macro/government analysis
- Separate opportunity score from confidence score
- Add event risk and contradiction detection
- Add prediction audit trail

## 3. myhhub/stock

### Observed strengths

- Many technical indicators
- Candlestick pattern recognition
- Strategy screening
- Backtesting concepts
- Scheduled jobs
- Web visualization

### English summary of relevant Chinese description

The project collects stock data, calculates technical indicators, identifies candlestick patterns, performs strategy-based stock selection, validates strategies through backtesting, and supports scheduled jobs and web visualization.

### What to borrow conceptually

- Broad technical indicator coverage
- Candlestick pattern engine
- Strategy screening templates
- Scheduled batch processing
- Backtest mindset

### What to improve

- Adapt to U.S. markets
- Do not enable automated trading by default
- Add SEC/company/macro/options evidence
- Add safer compliance and risk filters

## 4. SumanthT26/USA-Stock-Market-prediction-using-Financial-Fundamental-data

### Observed strengths

- Uses financial/fundamental features
- Emphasizes that financial statements contain many useful indicators
- Uses EDA, preprocessing, and model building

### What to borrow conceptually

- Fundamental features from financial statements
- ML model baseline
- EDA and preprocessing discipline

### What to improve

- Use live SEC company facts instead of only static old datasets
- Add time-series-safe validation
- Add model monitoring and feature drift
- Add options/news/macro/sentiment layers

## 5. EvotecIT/UnifiStockTracker

### Observed strengths

- Simple targeted monitoring
- User-specific alerts instead of broad noisy alerts
- Waiting/rechecking workflow
- Notification concept

### What to borrow conceptually

- Watch only selected assets/events
- Avoid spam alerts
- Alert only when user-defined condition is met
- Recheck on interval

### What to improve

- Apply targeted monitoring to market events, filings, options flow, and macro shocks
- Add severity levels and deduplication
- Add evidence-backed alerts

## Overall Design Lessons

1. Use multi-source data.
2. Keep scoring transparent.
3. Generate actionable dashboards.
4. Build scheduled automation first.
5. Add alert deduplication early.
6. Keep scoring functions testable.
7. Separate prediction from explanation.
8. Store evidence for every claim.
9. Add risk management and disclaimers.
10. Backtest before trusting any signal.
