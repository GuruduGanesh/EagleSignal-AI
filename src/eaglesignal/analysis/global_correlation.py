"""SKILL-082 Global cross-market correlation.

Computes each watched name's rolling daily-return correlation to a set of world
indexes (US/Europe/Asia). Pure pandas over REAL price history. Correlations are
*context* — they explain how globally-tied a name is and which regions move it —
and are surfaced per prediction without adding a new scoring weight (keeps the
existing weight scheme stable; cross_market.py already carries the SPY beta).
"""
from __future__ import annotations

import pandas as pd


def global_correlations(df: pd.DataFrame, index_bars: dict[str, pd.DataFrame], window: int = 60) -> dict[str, float]:
    if df is None or df.empty or not index_bars:
        return {}
    asset_ret = df["close"].pct_change()
    out: dict[str, float] = {}
    for name, bars in index_bars.items():
        if bars is None or len(bars) < 30:
            continue
        joined = pd.concat(
            [asset_ret.rename("a"), bars["close"].pct_change().rename("b")], axis=1
        ).dropna()
        if len(joined) < 30:
            continue
        tail = joined.tail(window)
        corr = float(tail["a"].corr(tail["b"]))
        if corr == corr:  # exclude NaN
            out[name] = round(corr, 2)
    # Sort by absolute correlation, strongest linkages first.
    return dict(sorted(out.items(), key=lambda kv: abs(kv[1]), reverse=True))
