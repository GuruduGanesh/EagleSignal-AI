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

## 6. JordiCorbilla/stock-prediction-deep-neural-learning

### Observed strengths

- TensorFlow LSTM approach for time-series forecasting
- Uses train/validation split discipline
- Newer versions separate direction and magnitude prediction
- Uses model artifacts such as saved models, scaler files, and model configuration
- Supports stochastic future trajectories with percentile bands

### What to borrow conceptually

- Predict direction and magnitude separately instead of only predicting a raw future price.
- Store model configuration, scalers, feature transforms, and model version together.
- Use return/delta targets to reduce price-level drift.
- Produce percentile bands or scenario paths instead of one overconfident number.
- Treat deep learning as one model family inside an ensemble, not the only decision engine.

### What to improve

- Do not train or infer from fabricated data.
- Do not use future generated dates as if they were market truth.
- Validate with walk-forward, out-of-sample windows and trading-cost assumptions.
- Connect model output to evidence, risk, and source freshness before it can affect recommendations.

## 7. huseinzol05/Stock-Prediction-Models

### Observed strengths

- Broad library of model families: LSTM, GRU, bidirectional models, Seq2Seq, VAE variants, attention/Transformer-style models, CNN-Seq2Seq, and dilated CNNs
- Stacking models combining neural nets, ARIMA, gradient boosting, random forests, XGBoost, and other tree ensembles
- Trading-agent experiments including turtle, moving-average, Q-learning, actor-critic, neuro-evolution, and policy-gradient agents
- Simulation notebooks including Monte Carlo and dynamic-volatility Monte Carlo
- Sentiment-consensus examples for combining text sentiment with price forecasting

### What to borrow conceptually

- Build an ensemble layer that combines rule-based signals, statistical models, tree models, and sequence models.
- Use Monte Carlo and dynamic-volatility simulations to express expected ranges and uncertainty.
- Keep trading-agent/RL ideas behind a research-only simulator until heavily validated.
- Use sentiment consensus as a separate feature family, not a standalone trade trigger.
- Compare model families under the same walk-forward evaluation harness.

### What to improve

- The repository is archived and many notebooks are experimental; copy concepts, not production code.
- Avoid crypto/forex/non-U.S. scope unless used only as macro context.
- Require point-in-time features, no lookahead leakage, source provenance, and cost/slippage assumptions.
- Do not expose automated trading agents in the MVP.

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
11. Use real market data provider fallback and local real-data cache; never fabricate runtime market data.
12. Prefer ensembles and uncertainty bands over single-price forecasts.
13. Separate direction, magnitude, confidence, and risk.
