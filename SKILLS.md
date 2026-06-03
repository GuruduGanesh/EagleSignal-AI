# SKILLS.md

This is the single canonical skill registry for **USA-Stock-Market-prediction / EagleSignal AI**.

Add every new capability to this file before implementing it. Each skill should be small, testable, observable, and replaceable.

## Skill Template

```yaml
skill_id: SKILL-000
name: Short skill name
purpose: What this skill does
inputs: Required inputs
outputs: Required outputs
freshness: Required data freshness
source_reliability: Official / high / medium / low
validation_checks: Checks before output is accepted
failure_behavior: What to do when data is missing or stale
dependencies: Other skills required
example_output_fields: Key fields returned
```

---

# A. Core System Skills

## SKILL-001: Watchlist Loader

- **Purpose:** Load ticker, ETF, index, and option watchlists from YAML/CSV/JSON.
- **Inputs:** `watchlist.yml`, ticker symbols, asset type, strategy profile.
- **Outputs:** Normalized asset list with metadata.
- **Freshness:** Static; reload every run.
- **Source reliability:** User-defined.
- **Validation checks:** Valid ticker format, supported market, duplicate removal.
- **Failure behavior:** Skip invalid symbols and log warning.
- **Dependencies:** None.
- **Example output fields:** `ticker`, `asset_type`, `exchange`, `sector`, `strategy_tags`.

## SKILL-002: Entity Resolution

- **Purpose:** Resolve ticker to company, CIK, exchange, sector, industry, and related ETFs.
- **Inputs:** Ticker list.
- **Outputs:** Canonical entity map.
- **Freshness:** Weekly or when ticker list changes.
- **Source reliability:** Official exchange/SEC/company metadata preferred.
- **Validation checks:** Ticker-CIK mapping, active/inactive status.
- **Failure behavior:** Mark as unresolved and continue with price-only analysis.
- **Dependencies:** SKILL-001.
- **Example output fields:** `ticker`, `cik`, `company_name`, `sector`, `industry`, `related_etfs`.

## SKILL-003: Evidence Store Writer

- **Purpose:** Store every claim, source link, timestamp, and extracted evidence.
- **Inputs:** Raw documents, source URLs, parsed signals.
- **Outputs:** Evidence records.
- **Freshness:** Every run.
- **Source reliability:** All levels, but ranked.
- **Validation checks:** Source URL, timestamp, duplicate hash.
- **Failure behavior:** Do not allow final LLM reasoning without evidence.
- **Dependencies:** All ingestion skills.
- **Example output fields:** `source`, `url`, `retrieved_at`, `entity`, `claim`, `confidence`, `hash`.

## SKILL-004: Data Freshness Guard

- **Purpose:** Reject or downgrade stale data.
- **Inputs:** Data record timestamps.
- **Outputs:** Freshness score and warning.
- **Freshness:** Every run.
- **Source reliability:** Not applicable.
- **Validation checks:** Compare retrieved timestamp with freshness SLA.
- **Failure behavior:** Penalize score or block prediction.
- **Dependencies:** All data skills.
- **Example output fields:** `freshness_status`, `age_minutes`, `penalty`.

## SKILL-005: Source Reliability Ranker

- **Purpose:** Rank evidence by authority and reliability.
- **Inputs:** Evidence records.
- **Outputs:** Reliability scores.
- **Freshness:** Every run.
- **Source reliability:** Official > primary > reputable news > social > unknown.
- **Validation checks:** Source domain, author, publication time, duplication.
- **Failure behavior:** Low-quality sources cannot dominate final prediction.
- **Dependencies:** SKILL-003.
- **Example output fields:** `source_rank`, `source_type`, `reliability_score`.

---

# B. Market Data Skills

## SKILL-010: OHLCV Data Collector

- **Purpose:** Pull open, high, low, close, adjusted close, and volume data.
- **Inputs:** Ticker, date range, interval.
- **Outputs:** OHLCV time series.
- **Freshness:** Intraday for live scans; daily for after-market.
- **Source reliability:** Exchange/paid API/high-quality public API.
- **Validation checks:** Missing candles, split adjustments, abnormal gaps.
- **Failure behavior:** Retry alternate source; if still missing, mark incomplete.
- **Dependencies:** SKILL-001, SKILL-002.
- **Example output fields:** `timestamp`, `open`, `high`, `low`, `close`, `volume`, `adjusted_close`.

## SKILL-011: Premarket and After-Hours Collector

- **Purpose:** Collect extended-hours price movement.
- **Inputs:** Ticker, session date.
- **Outputs:** Premarket/after-hours change, volume, gaps.
- **Freshness:** 1-15 minutes during extended session.
- **Source reliability:** Broker/exchange/market data API.
- **Validation checks:** Liquidity threshold, delayed-data flag.
- **Failure behavior:** Use as contextual only if source is delayed.
- **Dependencies:** SKILL-010.
- **Example output fields:** `premarket_change_pct`, `after_hours_change_pct`, `extended_volume`.

## SKILL-012: Relative Volume Analyzer

- **Purpose:** Detect abnormal volume vs baseline.
- **Inputs:** Intraday or daily volume history.
- **Outputs:** Relative volume score.
- **Freshness:** Intraday/daily.
- **Source reliability:** High.
- **Validation checks:** Enough historical periods.
- **Failure behavior:** Return null and do not penalize.
- **Dependencies:** SKILL-010.
- **Example output fields:** `relative_volume`, `volume_zscore`, `volume_signal`.

## SKILL-013: VWAP Analyzer

- **Purpose:** Determine price behavior vs volume-weighted average price.
- **Inputs:** Intraday candles.
- **Outputs:** VWAP trend score.
- **Freshness:** Intraday.
- **Source reliability:** High.
- **Validation checks:** Intraday data availability.
- **Failure behavior:** Skip for daily-only analysis.
- **Dependencies:** SKILL-010.
- **Example output fields:** `vwap`, `price_above_vwap`, `distance_from_vwap`.

## SKILL-014: Gap Analyzer

- **Purpose:** Detect gap up/down and classify continuation vs exhaustion risk.
- **Inputs:** Prior close, current open, premarket data.
- **Outputs:** Gap classification.
- **Freshness:** Intraday/daily.
- **Source reliability:** High.
- **Validation checks:** Corporate actions, earnings/news context.
- **Failure behavior:** Mark gap unexplained.
- **Dependencies:** SKILL-010, SKILL-011, SKILL-070.
- **Example output fields:** `gap_pct`, `gap_type`, `gap_reason`.

---

# C. Technical Analysis Skills

## SKILL-020: Moving Average Engine

- **Purpose:** Compute SMA/EMA trend and crossovers.
- **Inputs:** OHLCV data.
- **Outputs:** MA trend signals.
- **Freshness:** Daily/intraday.
- **Source reliability:** High.
- **Validation checks:** Enough lookback data.
- **Failure behavior:** Return insufficient history warning.
- **Dependencies:** SKILL-010.
- **Example output fields:** `sma_20`, `sma_50`, `sma_200`, `ema_9`, `ema_21`, `ma_trend_score`.

## SKILL-021: Momentum Indicator Engine

- **Purpose:** Compute RSI, MACD, ROC, stochastic RSI.
- **Inputs:** OHLCV data.
- **Outputs:** Momentum signals.
- **Freshness:** Daily/intraday.
- **Source reliability:** High.
- **Validation checks:** Indicator lookback coverage.
- **Failure behavior:** Skip individual indicator if insufficient data.
- **Dependencies:** SKILL-010.
- **Example output fields:** `rsi`, `macd`, `macd_signal`, `roc`, `stoch_rsi`.

## SKILL-022: Volatility Indicator Engine

- **Purpose:** Compute ATR, Bollinger Bands, volatility compression/expansion.
- **Inputs:** OHLCV data.
- **Outputs:** Volatility regime.
- **Freshness:** Daily/intraday.
- **Source reliability:** High.
- **Validation checks:** Enough lookback.
- **Failure behavior:** Return partial indicators.
- **Dependencies:** SKILL-010.
- **Example output fields:** `atr`, `bollinger_width`, `volatility_regime`.

## SKILL-023: Trend Strength Engine

- **Purpose:** Compute ADX/DMI and trend-quality score.
- **Inputs:** OHLCV data.
- **Outputs:** Trend strength.
- **Freshness:** Daily/intraday.
- **Source reliability:** High.
- **Validation checks:** Enough lookback.
- **Failure behavior:** Skip trend strength.
- **Dependencies:** SKILL-010.
- **Example output fields:** `adx`, `plus_di`, `minus_di`, `trend_strength`.

## SKILL-024: Candlestick Pattern Engine

- **Purpose:** Identify common bullish/bearish candlestick patterns.
- **Inputs:** OHLCV candles.
- **Outputs:** Pattern signals.
- **Freshness:** Daily/intraday.
- **Source reliability:** High.
- **Validation checks:** Pattern must align with volume/context.
- **Failure behavior:** Mark as low-confidence if standalone.
- **Dependencies:** SKILL-010, SKILL-012.
- **Example output fields:** `pattern_name`, `pattern_direction`, `pattern_confidence`.

## SKILL-025: Support and Resistance Engine

- **Purpose:** Identify key price levels.
- **Inputs:** Price history, volume, pivots.
- **Outputs:** Support/resistance levels.
- **Freshness:** Daily/intraday.
- **Source reliability:** High.
- **Validation checks:** Minimum touches/volume confirmation.
- **Failure behavior:** Return nearest obvious levels only.
- **Dependencies:** SKILL-010, SKILL-012.
- **Example output fields:** `support_levels`, `resistance_levels`, `breakout_level`, `breakdown_level`.

---

# D. Options Intelligence Skills

## SKILL-030: Options Chain Collector

- **Purpose:** Pull calls/puts by expiration and strike.
- **Inputs:** Ticker, expiration range.
- **Outputs:** Options chain table.
- **Freshness:** Intraday for options scans.
- **Source reliability:** Broker/market data provider preferred.
- **Validation checks:** Bid/ask sanity, stale quotes, contract liquidity.
- **Failure behavior:** Do not generate options recommendation if chain is stale.
- **Dependencies:** SKILL-002.
- **Example output fields:** `expiration`, `strike`, `type`, `bid`, `ask`, `last`, `volume`, `open_interest`, `iv`, `delta`, `gamma`, `theta`, `vega`.

## SKILL-031: Implied Volatility Analyzer

- **Purpose:** Analyze IV, IV rank, IV percentile, skew, term structure.
- **Inputs:** Options chain, historical volatility.
- **Outputs:** IV regime score.
- **Freshness:** Intraday/daily.
- **Source reliability:** High.
- **Validation checks:** Compare IV to historical range.
- **Failure behavior:** Mark options score incomplete.
- **Dependencies:** SKILL-030, SKILL-022.
- **Example output fields:** `iv_rank`, `iv_percentile`, `skew`, `term_structure`, `iv_signal`.

## SKILL-032: Put/Call Ratio Analyzer

- **Purpose:** Measure options sentiment and hedging pressure.
- **Inputs:** Options volume/open interest.
- **Outputs:** Put/call ratio score.
- **Freshness:** Intraday/daily.
- **Source reliability:** High.
- **Validation checks:** Separate volume and OI ratios.
- **Failure behavior:** Contextual only if data is partial.
- **Dependencies:** SKILL-030.
- **Example output fields:** `put_call_volume_ratio`, `put_call_oi_ratio`, `options_sentiment`.

## SKILL-033: Unusual Options Activity Detector

- **Purpose:** Detect abnormal options volume, sweeps, OI changes, and directional pressure.
- **Inputs:** Options chain, historical options data if available.
- **Outputs:** UOA signal.
- **Freshness:** Intraday.
- **Source reliability:** High.
- **Validation checks:** Volume vs OI, spread width, underlying news.
- **Failure behavior:** Flag as speculative unless confirmed by other signals.
- **Dependencies:** SKILL-030, SKILL-070, SKILL-012.
- **Example output fields:** `unusual_contracts`, `direction_hint`, `liquidity_score`, `confidence`.

## SKILL-034: Expected Move Calculator

- **Purpose:** Estimate expected move from options IV and/or straddle pricing.
- **Inputs:** ATM options, IV, expiration.
- **Outputs:** Expected move range.
- **Freshness:** Intraday/daily.
- **Source reliability:** High.
- **Validation checks:** Use liquid contracts only.
- **Failure behavior:** Use historical ATR fallback and label clearly.
- **Dependencies:** SKILL-030, SKILL-031, SKILL-022.
- **Example output fields:** `expected_move_dollars`, `expected_move_pct`, `range_low`, `range_high`.

## SKILL-035: Earnings IV Crush Risk Analyzer

- **Purpose:** Warn when options premium may collapse after earnings/events.
- **Inputs:** Earnings date, options IV, term structure.
- **Outputs:** IV crush risk.
- **Freshness:** Daily/intraday during earnings.
- **Source reliability:** High.
- **Validation checks:** Confirm earnings date from multiple sources.
- **Failure behavior:** High caution if earnings date uncertain.
- **Dependencies:** SKILL-030, SKILL-031, SKILL-080.
- **Example output fields:** `earnings_date`, `iv_crush_risk`, `safer_strategy_notes`.

---

# E. Fundamental and SEC Skills

## SKILL-040: SEC Company Facts Collector

- **Purpose:** Pull structured XBRL facts for U.S. companies.
- **Inputs:** CIK.
- **Outputs:** Financial facts.
- **Freshness:** On filing update; daily check.
- **Source reliability:** Official SEC.
- **Validation checks:** CIK match, period match, restatement flags.
- **Failure behavior:** Use latest cached facts but mark stale.
- **Dependencies:** SKILL-002.
- **Example output fields:** `revenue`, `net_income`, `assets`, `liabilities`, `cash`, `debt`, `shares`.

## SKILL-041: SEC Latest Filing Monitor

- **Purpose:** Detect new 10-K, 10-Q, 8-K, Form 4, S-1, DEF 14A, 13F and other filings.
- **Inputs:** CIK, filing types.
- **Outputs:** New filing alerts and metadata.
- **Freshness:** Daily or event-triggered.
- **Source reliability:** Official SEC.
- **Validation checks:** Accession number, accepted timestamp.
- **Failure behavior:** Retry and alert if SEC unavailable.
- **Dependencies:** SKILL-002.
- **Example output fields:** `filing_type`, `accepted_at`, `accession_no`, `filing_url`.

## SKILL-042: Filing Material Event Extractor

- **Purpose:** Extract material events and risk from SEC filings.
- **Inputs:** Filing text/HTML/XBRL.
- **Outputs:** Structured event summary.
- **Freshness:** On filing release.
- **Source reliability:** Official SEC.
- **Validation checks:** Section mapping, source paragraph citation.
- **Failure behavior:** Store filing but mark extraction incomplete.
- **Dependencies:** SKILL-041, SKILL-003.
- **Example output fields:** `event_type`, `summary`, `risk_level`, `quoted_section_ref`.

## SKILL-043: Financial Ratio Calculator

- **Purpose:** Compute valuation, profitability, leverage, liquidity, and growth ratios.
- **Inputs:** Financial facts, price, shares.
- **Outputs:** Ratio table and score.
- **Freshness:** Daily price + latest filing fundamentals.
- **Source reliability:** Official filing + market data.
- **Validation checks:** Negative denominators, outliers, missing values.
- **Failure behavior:** Return partial ratios with warnings.
- **Dependencies:** SKILL-040, SKILL-010.
- **Example output fields:** `pe`, `ps`, `pb`, `ev_ebitda`, `gross_margin`, `fcf_margin`, `debt_to_equity`.

## SKILL-044: Earnings Report Analyzer

- **Purpose:** Analyze earnings results, guidance, surprise, and management commentary.
- **Inputs:** Earnings press release, SEC 8-K, transcript if available.
- **Outputs:** Earnings signal.
- **Freshness:** Same day as earnings.
- **Source reliability:** Company IR/SEC/reputable transcript provider.
- **Validation checks:** Confirm actual vs estimate source.
- **Failure behavior:** Label estimate data as optional if unavailable.
- **Dependencies:** SKILL-041, SKILL-070, SKILL-003.
- **Example output fields:** `eps_surprise`, `revenue_surprise`, `guidance_change`, `tone`, `earnings_score`.

## SKILL-045: Company Contract and Agreement Monitor

- **Purpose:** Detect new contracts, partnerships, government awards, and major customer deals.
- **Inputs:** SEC filings, company news, government award databases where available.
- **Outputs:** Contract event signal.
- **Freshness:** Daily/event-triggered.
- **Source reliability:** Official filing/company/government preferred.
- **Validation checks:** Confirm amount, duration, parties, materiality.
- **Failure behavior:** Mark rumor vs confirmed.
- **Dependencies:** SKILL-041, SKILL-070, SKILL-060.
- **Example output fields:** `contract_party`, `value`, `duration`, `confirmed`, `stock_impact_estimate`.

---

# F. Macro, Government, and Policy Skills

## SKILL-050: FRED Macro Collector

- **Purpose:** Pull macroeconomic time series from FRED.
- **Inputs:** Series IDs.
- **Outputs:** Macro time series.
- **Freshness:** According to release calendar.
- **Source reliability:** Official/regional Fed data.
- **Validation checks:** Release date, revision/vintage.
- **Failure behavior:** Use latest cached but mark stale.
- **Dependencies:** None.
- **Example output fields:** `series_id`, `value`, `date`, `release_name`.

## SKILL-051: BLS Labor Market Collector

- **Purpose:** Pull jobs, unemployment, wages, CPI/PPI series from BLS where relevant.
- **Inputs:** BLS series IDs.
- **Outputs:** Labor and inflation data.
- **Freshness:** Release calendar.
- **Source reliability:** Official BLS.
- **Validation checks:** Series ID, seasonal adjustment, revision.
- **Failure behavior:** Mark macro score incomplete.
- **Dependencies:** None.
- **Example output fields:** `nonfarm_payrolls`, `unemployment_rate`, `average_hourly_earnings`, `cpi`.

## SKILL-052: BEA Economic Growth Collector

- **Purpose:** Pull GDP, personal income, spending, and national account data.
- **Inputs:** BEA dataset/table/line.
- **Outputs:** Growth and spending indicators.
- **Freshness:** Release calendar.
- **Source reliability:** Official BEA.
- **Validation checks:** Estimate number, revision date.
- **Failure behavior:** Use prior release with stale warning.
- **Dependencies:** None.
- **Example output fields:** `gdp_growth`, `pce`, `personal_income`, `savings_rate`.

## SKILL-053: Federal Reserve Policy Monitor

- **Purpose:** Track FOMC decisions, speeches, minutes, and rate expectations context.
- **Inputs:** Fed releases, FOMC calendar, yield data.
- **Outputs:** Fed policy signal.
- **Freshness:** Event-driven and daily.
- **Source reliability:** Official Fed.
- **Validation checks:** Date/time of release, speaker relevance.
- **Failure behavior:** Do not infer policy from social rumor.
- **Dependencies:** SKILL-050, SKILL-070.
- **Example output fields:** `policy_bias`, `rate_risk`, `statement_tone`, `market_impact`.

## SKILL-054: Treasury and Yield Curve Analyzer

- **Purpose:** Analyze Treasury yields, auctions, curve inversion/steepening.
- **Inputs:** Treasury/FRED yields.
- **Outputs:** Yield curve regime.
- **Freshness:** Daily/intraday if available.
- **Source reliability:** Official Treasury/FRED.
- **Validation checks:** Maturity alignment.
- **Failure behavior:** Mark macro risk incomplete.
- **Dependencies:** SKILL-050.
- **Example output fields:** `2y`, `10y`, `2s10s`, `curve_signal`, `rate_sensitive_sector_risk`.

## SKILL-055: U.S. Government News Monitor

- **Status:** Implemented in `ingestion/government.py` — Treasury FiscalData, BLS, Federal Register (presidential docs), openFDA drug/device recalls, DOJ Antitrust + FTC actions, and GDELT policy news. Keyless except optional `BLS_API_KEY`.
- **Purpose:** Monitor official U.S. government sources for market-moving policy/news.
- **Inputs:** Agency RSS/API/pages.
- **Outputs:** Policy event records.
- **Freshness:** Event-driven/daily.
- **Source reliability:** Official government.
- **Validation checks:** Official domain, timestamp, agency relevance.
- **Failure behavior:** Alert only if official confirmation exists.
- **Dependencies:** SKILL-003.
- **Example output fields:** `agency`, `event_type`, `affected_sectors`, `impact_score`.

## SKILL-056: Sector Policy Impact Mapper

- **Status:** Implemented in `analysis/impact.py`. Two tiers: `direct` (distinctive brand token from `company_name` appears in the event title — generic words like "Medical"/"Digital" are dropped to prevent over-matching) and `thematic` (broad `policy` headlines matched to the asset's strategy-tag sector keywords, treated as neutral context). Direct FDA/antitrust hits add a negative polarity, become ticker evidence, surface as `policy_impacts`, and raise an event-risk warning. Unrelated recalls/consent orders do NOT attach.
- **Purpose:** Map government and macro events to affected sectors/tickers.
- **Inputs:** Government events (FDA/DOJ/FTC/Federal Register/GDELT), watchlist `company_name` + `strategy_tags`.
- **Outputs:** Per-ticker `policy_impacts` list, ticker-level evidence, and event-risk warnings.
- **Freshness:** Event-driven (per run).
- **Source reliability:** Official government; direct match high-confidence, thematic match context-only.
- **Validation checks:** Avoid overbroad mapping (brand-token + generic-word stoplist; unit-tested for false positives).
- **Failure behavior:** Empty list when no confident link exists (verified live: NVDA returned `[]` when the day's feed named no related entity).
- **Dependencies:** SKILL-055, SKILL-002.
- **Example output fields:** `match_kind`, `polarity`, `event.kind`, `event.title`, `policy_impacts`.

---

# G. News, Geopolitical, and Sentiment Skills

## SKILL-070: News Collector

- **Purpose:** Collect market, company, sector, political, and international news.
- **Inputs:** Ticker/company/sector keywords, approved APIs.
- **Outputs:** News articles and metadata.
- **Freshness:** Near-real-time/daily.
- **Source reliability:** Reputable news API/search API/company IR.
- **Validation checks:** Timestamp, duplicate clustering, source quality.
- **Failure behavior:** If low-quality only, do not use for high-confidence prediction.
- **Dependencies:** SKILL-002, SKILL-003, SKILL-005.
- **Example output fields:** `headline`, `url`, `published_at`, `source`, `entities`, `summary`.

## SKILL-071: News Sentiment Analyzer

- **Purpose:** Score news tone, uncertainty, urgency, and market impact.
- **Inputs:** News text and metadata.
- **Outputs:** News sentiment score.
- **Freshness:** Every news run.
- **Source reliability:** Uses rank from SKILL-005.
- **Validation checks:** Do not score headlines only when body is required.
- **Failure behavior:** Return low confidence.
- **Dependencies:** SKILL-070, SKILL-005.
- **Example output fields:** `sentiment`, `urgency`, `uncertainty`, `impact_direction`.

## SKILL-072: Geopolitical Risk Engine

- **Purpose:** Map geopolitical events to sectors and indexes.
- **Inputs:** International news, commodity/yield/index data.
- **Outputs:** Geopolitical risk score.
- **Freshness:** Event-driven/daily.
- **Source reliability:** Reputable global news/official sources.
- **Validation checks:** Cross-source confirmation.
- **Failure behavior:** Flag as watch-only until confirmed.
- **Dependencies:** SKILL-070, SKILL-090.
- **Example output fields:** `event_region`, `affected_sectors`, `risk_direction`, `confidence`.

## SKILL-073: Social Sentiment Collector

- **Purpose:** Collect public social data only where API/terms allow.
- **Inputs:** Ticker cashtags, company names, hashtags.
- **Outputs:** Social posts metadata and text.
- **Freshness:** Intraday/daily.
- **Source reliability:** Social = lower reliability by default.
- **Validation checks:** Bot/spam detection, source deduplication, rate limits.
- **Failure behavior:** Never allow social sentiment alone to trigger strong signal.
- **Dependencies:** SKILL-002, SKILL-003.
- **Example output fields:** `platform`, `post_id`, `created_at`, `author_quality`, `text`, `engagement`.

## SKILL-074: Social Sentiment Analyzer

- **Purpose:** Analyze social mood, fear/greed, controversy, volume spikes.
- **Inputs:** Social posts.
- **Outputs:** Social sentiment signal.
- **Freshness:** Intraday/daily.
- **Source reliability:** Low-medium.
- **Validation checks:** Compare with normal mention volume.
- **Failure behavior:** Contextual only when sample is small.
- **Dependencies:** SKILL-073.
- **Example output fields:** `mention_volume_zscore`, `sentiment_score`, `bot_risk`, `confidence`.

## SKILL-075: Rumor vs Confirmed Event Classifier

- **Purpose:** Separate confirmed events from rumors/speculation.
- **Inputs:** News/social/evidence records.
- **Outputs:** Confirmation status.
- **Freshness:** Event-driven.
- **Source reliability:** Official/primary source required for confirmed.
- **Validation checks:** Require primary source or multiple reputable sources.
- **Failure behavior:** Label rumor and reduce score contribution.
- **Dependencies:** SKILL-003, SKILL-005, SKILL-070, SKILL-073.
- **Example output fields:** `confirmation_status`, `evidence_count`, `confidence`.

---

# H. Cross-Market and Sector Skills

## SKILL-090: Global Market Correlation Engine

- **Status:** Implemented in `ingestion/global_markets.py` (SKILL-081 collector: 14 US/Europe/Asia indexes via the real-data chain — S&P 500, Nasdaq 100, Dow, Russell 2000, VIX, DAX, CAC 40, FTSE 100, Euro Stoxx 50, Nikkei 225, Hang Seng, Shanghai, NSE Nifty 50, KOSPI) and `analysis/global_correlation.py` (per-ticker 60-day rolling correlation, surfaced as `global_correlations` and in the dashboard "Global Markets" tab + a global risk-on/off breadth read). `GLOBAL_INDEXES` overrides the set.
- **Purpose:** Compare U.S. assets with global indexes, commodities, yields, VIX, and sector ETFs.
- **Inputs:** Asset prices and related market proxies.
- **Outputs:** Correlation/risk regime.
- **Freshness:** Daily/intraday.
- **Source reliability:** High.
- **Validation checks:** Rolling windows, enough history.
- **Failure behavior:** Skip correlations with insufficient data.
- **Dependencies:** SKILL-010.
- **Example output fields:** `rolling_correlation`, `beta`, `risk_on_off`, `divergence_signal`.

## SKILL-091: Sector Rotation Engine

- **Purpose:** Detect money flow into/out of sectors.
- **Inputs:** Sector ETF performance, relative strength.
- **Outputs:** Sector rotation signal.
- **Freshness:** Daily/intraday.
- **Source reliability:** High.
- **Validation checks:** Compare to SPY/QQQ/IWM.
- **Failure behavior:** Return neutral if signal is mixed.
- **Dependencies:** SKILL-010, SKILL-090.
- **Example output fields:** `leading_sectors`, `lagging_sectors`, `sector_score`.

## SKILL-092: Competitor and Supply Chain Mapper

- **Purpose:** Identify related companies that may move together.
- **Inputs:** Company metadata, sector, product lines, supplier/customer info.
- **Outputs:** Related ticker graph.
- **Freshness:** Monthly/quarterly.
- **Source reliability:** Company filings and reliable datasets preferred.
- **Validation checks:** Relationship evidence.
- **Failure behavior:** Mark relationship as inferred.
- **Dependencies:** SKILL-002, SKILL-040, SKILL-070.
- **Example output fields:** `related_tickers`, `relationship_type`, `evidence`.

## SKILL-200: AI Investment Advisor (research only)

- **Status:** Implemented in `advisor.py` with `/advisor` API endpoint, `eaglesignal advise` CLI, and a dashboard "AI Advisor" chat tab.
- **Purpose:** Conversational layer that explains signals, answers "what should I buy", and reviews a user portfolio — strictly research-only.
- **Inputs:** User message, optional holdings string (`AAPL:10, MSFT:5`), latest `signals.json`.
- **Outputs:** Natural-language answer + backend + signal count.
- **Backends:** LLM (OpenAI/Anthropic) when `ADVISOR_PROVIDER`/keys allow; otherwise a deterministic rule-based advisor over the report JSON (always available, offline-safe).
- **Source reliability:** Reasons ONLY over pipeline outputs from real data; never invents prices/news.
- **Validation checks:** Research-only disclaimer appended; "no trade" when confidence low / risk high; no insider/non-public info; LLM errors fall back to rules.
- **Failure behavior:** Returns a "run a scan first" notice when no signals exist.
- **Dependencies:** SKILL-100, SKILL-101, SKILL-130, SKILL-133, SKILL-134.
- **Example output fields:** `answer`, `backend`, `used_signals`, `disclaimer`.

---

# I. Scoring and Prediction Skills

## SKILL-100: Multi-Factor Score Calculator

- **Purpose:** Combine signals into transparent 0-100 score.
- **Inputs:** Technical, fundamental, options, macro, news, sentiment, correlation, risk signals.
- **Outputs:** Total score and component scores.
- **Freshness:** Every report.
- **Source reliability:** Mixed but weighted.
- **Validation checks:** Missing-signal handling, weight sum = 100%.
- **Failure behavior:** Return score with reduced confidence.
- **Dependencies:** All analysis skills.
- **Example output fields:** `total_score`, `component_scores`, `missing_components`, `confidence`.

## SKILL-101: Direction Prediction Engine

- **Purpose:** Predict bullish/bearish/neutral direction by horizon.
- **Inputs:** Feature set and model outputs.
- **Outputs:** Direction probabilities.
- **Freshness:** Every report.
- **Source reliability:** Based on feature sources.
- **Validation checks:** Calibration, no leakage, model version.
- **Failure behavior:** Use rule-based fallback and label lower confidence.
- **Dependencies:** SKILL-100, SKILL-120.
- **Example output fields:** `prob_up`, `prob_down`, `prob_neutral`, `predicted_direction`.

## SKILL-102: Scenario Generator

- **Purpose:** Produce best/base/worst-case scenarios.
- **Inputs:** Signals, risks, catalysts, options expected move.
- **Outputs:** Scenario analysis.
- **Freshness:** Every report.
- **Source reliability:** Uses evidence store.
- **Validation checks:** Each scenario must cite evidence or logic.
- **Failure behavior:** Output conservative scenarios.
- **Dependencies:** SKILL-003, SKILL-034, SKILL-100.
- **Example output fields:** `best_case`, `base_case`, `worst_case`.

## SKILL-103: Contradiction Detector

- **Purpose:** Detect conflicting signals and reduce confidence.
- **Inputs:** Component signals and evidence.
- **Outputs:** Conflict summary.
- **Freshness:** Every report.
- **Source reliability:** Weighted by source.
- **Validation checks:** Bullish vs bearish evidence count and quality.
- **Failure behavior:** Force neutral/avoid if contradiction is severe.
- **Dependencies:** SKILL-003, SKILL-100.
- **Example output fields:** `conflict_level`, `bullish_evidence`, `bearish_evidence`, `confidence_penalty`.

## SKILL-104: Invalidation Level Generator

- **Purpose:** Define conditions that invalidate the trade thesis.
- **Inputs:** Support/resistance, volatility, news, risk.
- **Outputs:** Invalidation levels and event triggers.
- **Freshness:** Every report.
- **Source reliability:** High.
- **Validation checks:** Must be measurable.
- **Failure behavior:** Mark recommendation incomplete if no invalidation exists.
- **Dependencies:** SKILL-025, SKILL-034, SKILL-110.
- **Example output fields:** `price_invalidation`, `event_invalidation`, `time_invalidation`.

## SKILL-105: Market Factor Coverage Auditor

- **Purpose:** Verify that every ticker recommendation considered the required 23 factor groups from `MARKET_FACTOR_CHECKLIST.md`.
- **Inputs:** Prediction components, evidence records, source freshness, market snapshot, options analytics, macro/government/news/social/fundamental/technical context.
- **Outputs:** Considered factor groups, missing factor groups, bullish factor groups, bearish factor groups, stale factor groups, and confidence adjustment.
- **Freshness:** Per source SLA in `DATA_SOURCES.md`.
- **Source reliability:** Use SKILL-005.
- **Validation checks:** No factor group may be marked considered unless at least one real source, computed feature, or explicit unavailable status exists.
- **Failure behavior:** Reduce confidence and show missing groups in the trace.
- **Example output fields:** `factor_coverage`, `missing_factor_groups`, `bullish_factor_groups`, `bearish_factor_groups`, `blocked_factor_groups`, `factor_confidence_adjustment`.

## SKILL-106: Source Priority Registry Auditor

- **Purpose:** Verify that every recommendation uses the source priority rules in `config/analysis_source_registry.yml`.
- **Inputs:** Evidence records, provider status, source URLs, source timestamps, API key availability, source reliability ranks.
- **Outputs:** Implemented sources used, manual/reference sources, API-gated sources, paid/licensed sources, context-only sources, and missing high-priority sources.
- **Freshness:** Every prediction and every scheduled source refresh.
- **Source reliability:** Official primary sources and licensed providers outrank dashboards, commentary, and social feeds.
- **Validation checks:** High-confidence recommendations must not rely only on dashboard, social, opinion, delayed, or rumor sources.
- **Failure behavior:** Lower confidence, mark source gaps in the trace, and keep the verdict as watch/no-trade if critical verification is missing.
- **Example output fields:** `source_priority_trace`, `primary_sources_used`, `reference_sources_used`, `missing_primary_sources`, `source_confidence_adjustment`.

## SKILL-125: Ensemble Forecast Engine (Monte-Carlo + Trend Agents)

- **Status:** Implemented in `src/eaglesignal/analysis/forecast.py`.
- **Purpose:** Produce an uncertainty-aware forward view that separates direction,
  magnitude, and confidence (techniques borrowed from JordiCorbilla's LSTM repo and
  huseinzol05's Monte-Carlo + trading-agent collection) without copying their code.
- **Inputs:** Real downloaded OHLCV history only (daily log-returns drift/vol).
- **Outputs:** `prob_up`, median return, p05/p95 return bands, and per-agent votes
  (turtle/Donchian breakout, MA crossover, momentum) folded into an
  `ensemble_forecast` 0-100 component.
- **Method:** Geometric-Brownian-motion Monte Carlo (default 4000 paths, seeded for
  reproducibility) over the horizon, plus rule-based trend-agent voting. Pure NumPy —
  no TensorFlow, so it runs anywhere the Docker image runs and is unit-tested.
- **Freshness:** Every prediction.
- **Source reliability:** Derived from real market history; bands are a forward
  *simulation of uncertainty*, never presented as observed prices.
- **Validation checks:** p05 ≤ median ≤ p95; deterministic under fixed seed;
  `available=false` when history < 30 bars.
- **Failure behavior:** Degrade to trend-agent-only score, then to neutral/unavailable.
- **Dependencies:** SKILL-010 (market data), SKILL-100 (scoring), SKILL-120 (backtest).
- **Example output fields:** `prob_up`, `expected_return_pct`, `p05_return_pct`,
  `p95_return_pct`, `agent_votes`, `method`, `n_paths`.

---

# J. Backtesting and Model Quality Skills

## SKILL-120: Walk-Forward Backtester

- **Purpose:** Test strategies using time-series-safe validation.
- **Inputs:** Historical features, predictions, prices.
- **Outputs:** Backtest metrics.
- **Freshness:** After model/strategy changes.
- **Source reliability:** Historical market data.
- **Validation checks:** No lookahead bias, no future leakage.
- **Failure behavior:** Block strategy promotion.
- **Dependencies:** SKILL-010, SKILL-100, SKILL-101.
- **Example output fields:** `return`, `max_drawdown`, `win_rate`, `sharpe`, `sortino`, `calibration`.

## SKILL-121: Probability Calibration Checker

- **Purpose:** Verify predicted probabilities match realized outcomes.
- **Inputs:** Prediction history and realized outcomes.
- **Outputs:** Calibration metrics.
- **Freshness:** Weekly/monthly.
- **Source reliability:** Internal prediction logs.
- **Validation checks:** Sample size threshold.
- **Failure behavior:** Penalize model confidence.
- **Dependencies:** SKILL-101, SKILL-130.
- **Example output fields:** `brier_score`, `calibration_curve`, `confidence_adjustment`.

## SKILL-122: Feature Importance Reporter

- **Purpose:** Explain which factors drove a prediction.
- **Inputs:** Model features, scores, SHAP/permutation importance if available.
- **Outputs:** Feature importance summary.
- **Freshness:** Every model prediction.
- **Source reliability:** Internal model.
- **Validation checks:** Feature names mapped to user-friendly labels.
- **Failure behavior:** Provide score-based explanation fallback.
- **Dependencies:** SKILL-101.
- **Example output fields:** `top_positive_features`, `top_negative_features`.

---

# K. Risk and Compliance Skills

## SKILL-130: Prediction Audit Logger

- **Purpose:** Log every prediction, input version, model version, and evidence.
- **Inputs:** Final prediction payload.
- **Outputs:** Audit record.
- **Freshness:** Every prediction.
- **Source reliability:** Internal.
- **Validation checks:** Required fields present.
- **Failure behavior:** Block report if audit logging fails in production.
- **Dependencies:** SKILL-003, SKILL-100, SKILL-101.
- **Example output fields:** `prediction_id`, `created_at`, `model_version`, `evidence_ids`.

## SKILL-131: Liquidity Risk Filter

- **Purpose:** Avoid illiquid stocks/options.
- **Inputs:** Volume, spread, open interest, market cap.
- **Outputs:** Liquidity risk score.
- **Freshness:** Intraday/daily.
- **Source reliability:** High.
- **Validation checks:** Minimum thresholds by strategy.
- **Failure behavior:** Force avoid/no-trade.
- **Dependencies:** SKILL-010, SKILL-030.
- **Example output fields:** `liquidity_score`, `spread_pct`, `avoid_reason`.

## SKILL-132: Event Risk Filter

- **Purpose:** Warn around earnings, FOMC, CPI, jobs report, FDA, court rulings, major votes.
- **Inputs:** Event calendar, news, macro release schedule.
- **Outputs:** Event risk score.
- **Freshness:** Daily/event-driven.
- **Source reliability:** Official/reliable calendars.
- **Validation checks:** Date/time confirmation.
- **Failure behavior:** Increase risk/avoid if uncertain.
- **Dependencies:** SKILL-035, SKILL-050, SKILL-055, SKILL-070.
- **Example output fields:** `event_name`, `event_time`, `risk_level`, `affected_assets`.

## SKILL-133: Investment Advice Guardrail

- **Purpose:** Ensure system outputs are research-only and not guaranteed advice.
- **Inputs:** Final report text.
- **Outputs:** Compliance-cleared report.
- **Freshness:** Every report.
- **Source reliability:** Internal.
- **Validation checks:** No guaranteed profit, no misleading certainty.
- **Failure behavior:** Rewrite/flag unsafe language.
- **Dependencies:** Report generator.
- **Example output fields:** `compliance_status`, `rewritten_sections`.

## SKILL-134: Non-Public Information Guardrail

- **Purpose:** Prevent use of private/inside information.
- **Inputs:** Sources and evidence.
- **Outputs:** Compliance decision.
- **Freshness:** Every evidence ingestion.
- **Source reliability:** Must be public/legal.
- **Validation checks:** Source accessibility and terms.
- **Failure behavior:** Exclude questionable evidence.
- **Dependencies:** SKILL-003, SKILL-005.
- **Example output fields:** `public_source_confirmed`, `excluded_evidence`.

---

# L. Reporting and Alerting Skills

## SKILL-150: Markdown Report Generator

- **Purpose:** Generate daily/premarket/after-market Markdown research reports.
- **Inputs:** Prediction payloads and evidence.
- **Outputs:** Markdown file.
- **Freshness:** Every scheduled run.
- **Source reliability:** Based on evidence.
- **Validation checks:** Required sections, citations/source links.
- **Failure behavior:** Generate partial report with missing-data section.
- **Dependencies:** SKILL-100, SKILL-101, SKILL-102, SKILL-130.
- **Example output fields:** `report_path`, `summary`, `top_candidates`.

## SKILL-151: HTML Dashboard Generator

- **Purpose:** Generate interactive report with filters and sorting.
- **Inputs:** Prediction JSON/CSV.
- **Outputs:** HTML dashboard.
- **Freshness:** Every report.
- **Source reliability:** Internal.
- **Validation checks:** Sortable fields, filter integrity.
- **Failure behavior:** Fall back to Markdown/CSV.
- **Dependencies:** SKILL-150.
- **Example output fields:** `dashboard_path`, `asset_count`.

## SKILL-152: Alert Deduplicator

- **Purpose:** Prevent repeated noisy alerts.
- **Inputs:** Alert candidate, alert history.
- **Outputs:** Send/suppress decision.
- **Freshness:** Every alert.
- **Source reliability:** Internal.
- **Validation checks:** Similarity hash and cooldown window.
- **Failure behavior:** Prefer suppressing duplicates.
- **Dependencies:** SKILL-130.
- **Example output fields:** `alert_hash`, `suppressed`, `reason`.

## SKILL-153: Notification Sender

- **Purpose:** Send alerts to email, Slack, Discord, Telegram, or webhook.
- **Inputs:** Approved alert payload.
- **Outputs:** Delivery status.
- **Freshness:** Event-driven.

## SKILL-133: SNDK-Style Event Radar

- **Purpose:** Detect abnormal breakout or exhaustion patterns in focused watchlist names.
- **Inputs:** Real historical price/volume bars, fresh news count, government/policy links.
- **Outputs:** Breakout score, exhaustion score, 20D/60D/252D returns, volume expansion, bullish clues, bearish clues, radar verdict.
- **Freshness:** Every scan and scheduled job.
- **Implementation:** `src/eaglesignal/analysis/event_radar.py`.
- **Source reliability:** Internal.
- **Validation checks:** Secret availability, channel configured.
- **Failure behavior:** Retry and log failure.
- **Dependencies:** SKILL-152.
- **Example output fields:** `channel`, `sent_at`, `status`.

---

# M. DevSecOps and Operations Skills

## SKILL-170: GitHub Actions Scheduler

- **Purpose:** Run scans on schedule and manual trigger.
- **Inputs:** Workflow YAML, secrets, config.
- **Outputs:** Scheduled reports and artifacts.
- **Freshness:** Scheduled.
- **Source reliability:** Internal.
- **Validation checks:** Secrets not printed, rate limit handling.
- **Failure behavior:** Fail safe and upload logs.
- **Dependencies:** All runtime skills.
- **Example output fields:** `workflow_run_id`, `artifact_paths`.

## SKILL-171: Observability Logger

- **Purpose:** Track runtime metrics, errors, source latency, and model quality.
- **Inputs:** App events.
- **Outputs:** Structured logs/metrics.
- **Freshness:** Real-time.
- **Source reliability:** Internal.
- **Validation checks:** No secrets in logs.
- **Failure behavior:** Local fallback logs.
- **Dependencies:** All skills.
- **Example output fields:** `duration_ms`, `source`, `status`, `error_type`.

## SKILL-172: Rate Limit Manager

- **Purpose:** Respect API rate limits and prevent bans.
- **Inputs:** Source config, response headers.
- **Outputs:** Throttled request schedule.
- **Freshness:** Every API call.
- **Source reliability:** Internal.
- **Validation checks:** Retry-after and quota tracking.
- **Failure behavior:** Backoff and skip optional sources.
- **Dependencies:** Source connectors.
- **Example output fields:** `remaining_quota`, `sleep_seconds`, `retry_count`.

## SKILL-173: Secret Scanner Guard

- **Purpose:** Prevent API keys from being committed or logged.
- **Inputs:** Code, config, logs.
- **Outputs:** Secret scan result.
- **Freshness:** CI and runtime.
- **Source reliability:** Internal.
- **Validation checks:** Known token patterns.
- **Failure behavior:** Fail CI.
- **Dependencies:** None.
- **Example output fields:** `secret_found`, `file`, `line`.

---

# N. Future Skills Parking Lot

Add future skills below using the same template:

- Congressional bill impact analyzer
- Trump administration policy monitor
- Local Windows scheduled collector every two hours with retry and dashboard manual trigger
- Bull/Bear Verdicts tab and SNDK-style Event Radar tab
- Manual trade journal and P/L tracker
- News-to-price trend impact analyzer
- Lobbying disclosure analyzer
- FDA approval probability tracker
- DOD contract award parser
- Semiconductor export control impact analyzer
- Airline/oil sensitivity mapper
- Bank stress/regulatory signal analyzer
- Housing/REIT macro mapper
- Insider trading pattern analyzer using public Form 4 data
- Dark-pool/off-exchange volume proxy if legal data source is available
- Institutional 13F trend analyzer
- Earnings call transcript tone drift analyzer
- Analyst revision aggregator if licensed data is available
- Patent/product launch impact analyzer
- Corporate layoff/hiring trend analyzer
- Supply chain disruption monitor
- Weather/natural disaster sector-impact mapper
- Cybersecurity incident market-impact monitor
- Antitrust/lawsuit risk engine
