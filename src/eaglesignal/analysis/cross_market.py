"""SKILL-080 Cross-market correlation engine.

Measures a name's recent relative strength vs a market benchmark (SPY) and its
correlation. Leaders in an up-tape score higher; laggards lower. Benchmark bars
are fetched once and reused for all tickers in a run.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..schemas import SignalComponent


def cross_market_signal(df: pd.DataFrame, benchmark: pd.DataFrame | None) -> SignalComponent:
    notes: list[str] = []
    if benchmark is None or len(benchmark) < 30:
        return SignalComponent(
            name="cross_market_correlation", score=50.0, weight=0.0, available=False,
            rationale=["Benchmark (SPY) data unavailable."],
        )

    # Align on common dates
    joined = pd.concat(
        [df["close"].rename("asset"), benchmark["close"].rename("bench")], axis=1
    ).dropna()
    if len(joined) < 30:
        return SignalComponent(name="cross_market_correlation", score=50.0, weight=0.0,
                               available=False, rationale=["Insufficient overlap with benchmark."])

    window = min(20, len(joined) - 1)
    asset_ret = joined["asset"].iloc[-1] / joined["asset"].iloc[-window] - 1
    bench_ret = joined["bench"].iloc[-1] / joined["bench"].iloc[-window] - 1
    rs = (asset_ret - bench_ret) * 100  # relative strength in pct points
    corr = float(joined["asset"].pct_change().corr(joined["bench"].pct_change()))

    score = 50 + np.clip(rs * 1.2, -20, 20)
    notes.append(f"{window}-day relative strength vs SPY: {rs:+.1f}pp.")
    notes.append(f"Correlation to SPY: {corr:.2f}.")
    if rs > 0:
        notes.append("Outperforming the market (leader).")
    else:
        notes.append("Underperforming the market (laggard).")

    return SignalComponent(name="cross_market_correlation", score=float(max(0, min(100, score))),
                           weight=0.0, rationale=notes)
