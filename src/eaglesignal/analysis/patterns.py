"""SKILL-116 Candlestick pattern recognition (concept borrowed from myhhub/stock).

Lightweight rule-based detectors on the most recent candles. Returns a list of
(pattern_name, bias) where bias is +1 bullish / -1 bearish.
"""
from __future__ import annotations

import pandas as pd


def detect_patterns(df: pd.DataFrame) -> list[tuple[str, int]]:
    if len(df) < 3:
        return []
    o, h, l, c = (df[k] for k in ("open", "high", "low", "close"))
    last, prev = -1, -2
    out: list[tuple[str, int]] = []

    body = abs(c.iloc[last] - o.iloc[last])
    rng = (h.iloc[last] - l.iloc[last]) or 1e-9
    lower_wick = min(o.iloc[last], c.iloc[last]) - l.iloc[last]
    upper_wick = h.iloc[last] - max(o.iloc[last], c.iloc[last])

    # Doji
    if body <= 0.1 * rng:
        out.append(("doji", 0))
    # Hammer (bullish) / shooting star (bearish)
    if lower_wick > 2 * body and upper_wick < body:
        out.append(("hammer", 1))
    if upper_wick > 2 * body and lower_wick < body:
        out.append(("shooting_star", -1))

    # Engulfing
    prev_bull = c.iloc[prev] > o.iloc[prev]
    last_bull = c.iloc[last] > o.iloc[last]
    if last_bull and not prev_bull and c.iloc[last] >= o.iloc[prev] and o.iloc[last] <= c.iloc[prev]:
        out.append(("bullish_engulfing", 1))
    if not last_bull and prev_bull and o.iloc[last] >= c.iloc[prev] and c.iloc[last] <= o.iloc[prev]:
        out.append(("bearish_engulfing", -1))

    return out


def pattern_bias(df: pd.DataFrame) -> tuple[float, list[str]]:
    """Net bias in [-1, 1] and human-readable notes."""
    patterns = detect_patterns(df)
    if not patterns:
        return 0.0, []
    net = sum(b for _, b in patterns)
    notes = [f"Candle pattern: {name} ({'bullish' if b>0 else 'bearish' if b<0 else 'neutral'})." for name, b in patterns]
    return max(-1.0, min(1.0, net / 2)), notes
