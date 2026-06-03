"""SKILL-150 Risk manager.

Blocks or downgrades risky outputs (illiquid options, low equity volume, thin
options OI, conflicting/low-confidence evidence). Produces a RiskDecision and a
risk_penalty (0..1) that the scoring layer subtracts as the configured
risk_penalty_adjustment weight.
"""
from __future__ import annotations

from typing import Optional

from ..analysis.options import OptionsAnalytics
from ..config import Settings
from ..ingestion.market_data import MarketData
from ..schemas import RiskDecision, RiskLevel, SignalComponent


def assess_risk(
    settings: Settings,
    market: MarketData,
    components: list[SignalComponent],
    options: Optional[OptionsAnalytics],
    confidence: float,
    is_option_setup: bool = False,
) -> tuple[RiskDecision, float]:
    penalties: list[str] = []
    warnings: list[str] = []
    risk = 30.0
    block = False

    if market.source == "unavailable":
        risk += 25; penalties.append("Live market data unavailable after provider fallback (do not trade).")
        block = True

    # Liquidity (equity)
    if not market.is_synthetic and market.last_volume < settings.min_equity_daily_volume:
        risk += 12; penalties.append(
            f"Daily volume {market.last_volume:,.0f} < {settings.min_equity_daily_volume:,} min (thin liquidity)."
        )

    # Options liquidity
    if is_option_setup and options is not None:
        if options.illiquid or options.total_oi < settings.min_option_open_interest:
            risk += 15; penalties.append(f"Options open interest {options.total_oi} below threshold (illiquid).")
        if options.avg_iv is not None and options.avg_iv > 90:
            risk += 10; warnings.append("Very high IV — earnings IV-crush risk for long options.")

    # Evidence conflict: components straddling bullish and bearish
    avail = [c for c in components if c.available]
    if avail:
        hi = max(c.score for c in avail)
        lo = min(c.score for c in avail)
        if hi - lo > 45:
            risk += 10; warnings.append("Conflicting signals across engines — wait for confirmation.")

    if confidence < 40:
        risk += 12; warnings.append("Low confidence (sparse or disagreeing evidence).")

    risk = max(0, min(100, risk))
    if risk >= 80:
        level, block = RiskLevel.extreme, True
    elif risk >= 60:
        level = RiskLevel.high
    elif risk >= 40:
        level = RiskLevel.medium
    else:
        level = RiskLevel.low

    decision = RiskDecision(
        risk_level=level, risk_score=risk, penalties=penalties,
        block_trade=block, warnings=warnings,
    )
    risk_penalty = risk / 100.0  # 0..1, fed into scoring
    return decision, risk_penalty
