"""End-to-end orchestrator (WORKFLOW.md section 2).

Scheduler -> connectors -> evidence/feature -> engines -> prediction -> risk ->
report -> alerts. Designed to run from the CLI, FastAPI, GitHub Actions, or a
Docker container. Network/data failures degrade gracefully and are surfaced in
each prediction's missing-data + freshness sections.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from time import sleep

import pandas as pd

from .config import Settings, get_settings, load_watchlist, load_weights
from .historical_store import persist_run_snapshots
from .ingestion.global_markets import GlobalMarketsSnapshot, fetch_global_indexes
from .ingestion.government import GovSnapshot, fetch_government
from .ingestion.macro_fred import MacroSnapshot, fetch_macro
from .ingestion.market_data import fetch_history
from .ingestion.options_chain import fetch_options
from .ingestion.sec_edgar import SecData, fetch_sec
from .manual_trading import mark_manual_trades
from .paper_trading import update_paper_trades
from .prediction.engine import predict
from .reliability import apply_confidence_calibration
from .schemas import AssetEntity, AssetType, PredictionResult
from .utils.evidence import EvidenceStore
from .utils.logging import get_logger

log = get_logger("pipeline")


@dataclass
class RunResult:
    predictions: list[PredictionResult] = field(default_factory=list)
    evidence: EvidenceStore = field(default_factory=EvidenceStore)
    macro: MacroSnapshot = field(default_factory=MacroSnapshot)
    government: GovSnapshot = field(default_factory=GovSnapshot)
    global_markets: GlobalMarketsSnapshot = field(default_factory=GlobalMarketsSnapshot)
    started_at: datetime = field(default_factory=datetime.utcnow)
    strategy: str = "swing"
    horizon: str = "5D"
    snapshots: dict = field(default_factory=dict)


def run_pipeline(
    *,
    strategy: str = "swing",
    horizon: str = "5D",
    tickers: list[str] | None = None,
    settings: Settings | None = None,
) -> RunResult:
    settings = settings or get_settings()
    weights = load_weights(strategy)
    assets, _strategies = load_watchlist()
    if tickers:
        wanted = {t.upper() for t in tickers}
        existing = {a.ticker for a in assets}
        assets = [a for a in assets if a.ticker in wanted]
        missing = wanted - existing
        if missing and settings.strict_watchlist_only:
            log.warning("Ignoring tickers outside watchlist because STRICT_WATCHLIST_ONLY=true: %s", sorted(missing))
        elif missing:
            for t in missing:  # allow ad-hoc tickers only when explicitly configured
                assets.append(AssetEntity(ticker=t, asset_type=AssetType.equity))

    store = EvidenceStore()
    macro = fetch_macro()
    log.info("Macro snapshot available=%s", macro.available)

    gov = fetch_government()
    log.info("Government snapshot available=%s providers=%s", gov.available, gov.providers)
    # Policy/government events are market-wide context — store once under MARKET.
    for ev in gov.events[:20]:
        store.add(entity="MARKET", source_name=ev.source, source_type="official",
                  claim=ev.title, url=ev.url, published_at=ev.published_at, data_type="news")

    # Benchmark fetched once and reused for cross-market correlation.
    benchmark = fetch_history("SPY").bars

    # Global markets (US + Europe + Asia) fetched once for correlation context.
    global_markets = fetch_global_indexes() if settings.enable_global_markets else GlobalMarketsSnapshot()
    global_index_bars = global_markets.bars_map() if global_markets.available else {}
    log.info("Global markets available=%s (%s indexes)", global_markets.available, len(global_index_bars))

    result = RunResult(evidence=store, macro=macro, government=gov,
                       global_markets=global_markets, strategy=strategy, horizon=horizon)

    def analyze_asset(asset: AssetEntity) -> PredictionResult | None:
        max_attempts = max(1, settings.per_ticker_retries + 1)
        for attempt in range(1, max_attempts + 1):
            log.info("Analyzing %s (%s), attempt %d/%d", asset.ticker, asset.asset_type.value, attempt, max_attempts)
            try:
                market = fetch_history(asset.ticker)
                if not market.ok:
                    if attempt < max_attempts:
                        log.warning("Retrying %s: insufficient bars on attempt %d/%d", asset.ticker, attempt, max_attempts)
                        sleep(max(0.0, settings.per_ticker_retry_delay_seconds))
                        continue
                    log.warning("Skipping %s: insufficient bars after %d attempts", asset.ticker, max_attempts)
                    return None

                sec = fetch_sec(asset.ticker) if asset.asset_type == AssetType.equity else SecData(ticker=asset.ticker)
                if sec.recent_filings:
                    for f in sec.recent_filings[:5]:
                        store.add(entity=asset.ticker, source_name="SEC EDGAR", source_type="official",
                                  claim=f.title, url=f.url, data_type="sec_filing")
                if sec.company_name:
                    asset.company_name = sec.company_name
                    asset.cik = sec.cik
                    asset.resolved = True

                opt_enabled = asset.asset_type in (AssetType.equity, AssetType.etf)
                chain = (
                    fetch_options(asset.ticker, market.last_close, min_days=settings.min_option_days_to_expiry)
                    if opt_enabled
                    else fetch_options(asset.ticker, min_days=settings.min_option_days_to_expiry)
                )

                pred = predict(
                    asset=asset, market=market, sec=sec, macro=macro,
                    options_chain=chain, benchmark=benchmark, store=store,
                    settings=settings, weights=weights, horizon=horizon, strategy=strategy,
                    gov=gov, global_index_bars=global_index_bars,
                )
                return pred
            except Exception as exc:  # one ticker's failure must not abort the whole run
                if attempt < max_attempts:
                    log.warning("Retrying %s after error on attempt %d/%d: %s", asset.ticker, attempt, max_attempts, exc)
                    sleep(max(0.0, settings.per_ticker_retry_delay_seconds))
                    continue
                log.warning("Skipping %s due to error after %d attempts: %s", asset.ticker, max_attempts, exc)
                return None
        return None

    # Ticker analysis is intentionally parallel: each asset fetches its own
    # market, SEC, options, news, social, technical, forecast, and risk inputs.
    max_workers = min(max(1, settings.pipeline_max_workers), max(1, len(assets)))
    log.info("Analyzing %d focused watchlist assets with %d parallel workers", len(assets), max_workers)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(analyze_asset, asset): asset for asset in assets}
        for fut in as_completed(futures):
            pred = fut.result()
            if pred:
                result.predictions.append(pred)

    calibration_summary = apply_confidence_calibration(result.predictions, settings)
    result.snapshots["confidence_calibration"] = calibration_summary

    # Rank by opportunity score, strongest setups first.
    result.predictions.sort(key=lambda p: p.opportunity_score, reverse=True)
    update_paper_trades(result.predictions, settings.data_dir)
    mark_manual_trades(result.predictions, settings.data_dir)
    snapshot_summary = persist_run_snapshots(result, settings)
    result.snapshots = {**result.snapshots, **snapshot_summary}
    log.info("Pipeline complete: %d predictions", len(result.predictions))
    return result
