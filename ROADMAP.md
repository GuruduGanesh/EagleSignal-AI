# ROADMAP.md

## Roadmap and GitHub Issues

Use this as the first GitHub project board.

## Milestone 0: Repository Foundation

- [ ] Create repository structure
- [ ] Add README.md
- [ ] Add MASTER_AI_PROMPT.md
- [ ] Add SKILLS.md
- [ ] Add WORKFLOW.md
- [ ] Add ARCHITECTURE.md
- [ ] Add DATA_SOURCES.md
- [ ] Add PRODUCT_REQUIREMENTS.md
- [ ] Add ROADMAP.md
- [ ] Add .env.example
- [ ] Add GitHub Actions skeleton
- [ ] Add license
- [ ] Add contributing guide

## Milestone 1: MVP Data Pipeline

- [x] Implement watchlist loader
- [x] Narrow default watchlist to the current focused AI/memory/semiconductor/cloud/energy names instead of all scripts
- [ ] Implement ticker/entity resolver
- [ ] Implement OHLCV collector
- [ ] Implement SEC company facts connector
- [ ] Implement latest filing monitor
- [ ] Implement FRED connector
- [ ] Implement BLS connector
- [ ] Implement BEA connector
- [ ] Implement news connector interface
- [ ] Add source registry loader for `config/analysis_source_registry.yml`
- [ ] Store raw data locally
- [ ] Normalize data into schemas

## Milestone 2: Scoring Engine

- [ ] Add technical indicator engine
- [ ] Add price/volume score
- [ ] Add fundamental ratio score
- [ ] Add macro regime score
- [ ] Add news sentiment score
- [ ] Add cross-market score
- [ ] Add risk penalty
- [ ] Add total 0-100 score
- [ ] Add confidence score separate from opportunity score
- [ ] Add contradiction detector
- [ ] Add 23-factor coverage auditor from `MARKET_FACTOR_CHECKLIST.md`
- [ ] Add source-priority coverage auditor from `config/analysis_source_registry.yml`
- [ ] Penalize confidence when critical factor groups are stale, missing, or contradictory

## Milestone 3: Reports

- [ ] Generate Markdown report
- [ ] Generate JSON signals
- [ ] Generate CSV summary
- [ ] Add evidence links
- [ ] Add missing-data section
- [ ] Add risk and disclaimer section
- [ ] Upload reports as GitHub Actions artifacts

## Milestone 4: Options Intelligence

- [ ] Add options chain connector
- [ ] Add IV analyzer
- [ ] Add IV rank/percentile
- [ ] Add put/call ratio
- [ ] Add expected move calculator
- [ ] Add unusual options detector
- [ ] Add options liquidity filter
- [ ] Add earnings IV crush warning

## Milestone 5: Backtesting

- [ ] Add historical feature builder
- [ ] Add walk-forward backtest
- [ ] Add no-lookahead checks
- [ ] Add slippage/transaction-cost assumptions
- [ ] Add metrics: returns, Sharpe, Sortino, max drawdown, win rate
- [ ] Add probability calibration tracking
- [ ] Add prediction outcome logger

## Milestone 6: Alerting

- [ ] Add alert rules
- [ ] Add alert severity P0-P3
- [ ] Add deduplication
- [ ] Add email alerts
- [ ] Add Slack alerts
- [ ] Add Discord alerts
- [ ] Add Telegram alerts
- [ ] Add webhook alerts

## Milestone 7: Dashboard/API

- [ ] Add FastAPI service
- [ ] Add `/signals` endpoint
- [ ] Add `/ticker/{symbol}` endpoint
- [ ] Add `/reports/latest` endpoint
- [ ] Add dashboard UI
- [ ] Add filters and sorting
- [ ] Add historical prediction view
- [x] Add manual trade journal view with current-price P/L
- [x] Add Bull/Bear Verdicts dashboard tab
- [x] Add SNDK-style Event Radar dashboard tab
- [x] Add local scheduled collection job with retry and browser manual trigger
- [ ] Add trends/news-impact view
- [ ] Add policy theme watchlist view

## Milestone 8: Advanced AI Agent

- [ ] Add evidence retrieval agent
- [ ] Add LLM report writer
- [ ] Add contradiction review agent
- [ ] Add risk review agent
- [ ] Add source reliability critique
- [ ] Add “ask about ticker” chat mode
- [x] Add Trump/admin policy monitor and impact summarizer

## Suggested First 10 GitHub Issues

1. Create canonical `SKILLS.md` registry
2. Build watchlist loader with YAML support
3. Implement OHLCV data collector interface
4. Implement SEC CIK/entity resolver
5. Implement SEC company facts collector
6. Implement technical indicator engine
7. Implement multi-factor scoring function
8. Generate Markdown daily report
9. Add GitHub Actions scheduled workflow
10. Add prediction audit log

## Label System

```text
area:data-ingestion
area:technical-analysis
area:options
area:fundamentals
area:macro
area:news
area:sentiment
area:ml
area:backtesting
area:risk
area:reports
area:alerts
area:devops
priority:p0
priority:p1
priority:p2
good-first-issue
help-wanted
research-needed
```
