"""Event-radar heuristics for outsized winners and breakdown candidates.

This is built for names like SNDK where the useful question is not just
"is the chart up?" but "is there a real event chain behind the move, and is it
still early enough or already crowded?"
"""
from __future__ import annotations

import math
from typing import Any

import pandas as pd


def _pct(a: float, b: float) -> float | None:
    if b == 0 or math.isnan(a) or math.isnan(b):
        return None
    return (a / b - 1) * 100


def detect_event_radar(df: pd.DataFrame, *, news_items: int = 0, policy_links: int = 0) -> dict[str, Any]:
    """Return a compact bullish/bearish event-read from real price/volume bars.

    Signals are intentionally transparent. The model flags:
    - explosive acceleration (5/20/60 day returns)
    - volume confirmation (latest volume vs 20-day average)
    - trend stage (near high / far above moving averages)
    - reversal risk when the move is too stretched without enough confirmation
    """
    if df is None or df.empty or len(df) < 30:
        return {"available": False, "reason": "Need at least 30 real bars for event radar."}

    close = df["close"].astype(float)
    volume = df["volume"].astype(float) if "volume" in df else pd.Series([], dtype=float)
    last = float(close.iloc[-1])
    ret_5 = _pct(last, float(close.iloc[-6])) if len(close) >= 6 else None
    ret_20 = _pct(last, float(close.iloc[-21])) if len(close) >= 21 else None
    ret_60 = _pct(last, float(close.iloc[-61])) if len(close) >= 61 else None
    ret_252 = _pct(last, float(close.iloc[-253])) if len(close) >= 253 else None
    high_252 = float(close.tail(min(len(close), 252)).max())
    drawdown_from_high = _pct(last, high_252)
    ma20 = float(close.tail(20).mean())
    ma50 = float(close.tail(min(len(close), 50)).mean())
    above_ma20 = _pct(last, ma20)
    above_ma50 = _pct(last, ma50)

    vol_ratio = None
    if len(volume) >= 21 and float(volume.tail(20).mean()) > 0:
        vol_ratio = float(volume.iloc[-1] / volume.tail(20).mean())

    bullish: list[str] = []
    bearish: list[str] = []
    if ret_20 is not None and ret_20 >= 25:
        bullish.append(f"20D acceleration {ret_20:+.1f}%")
    if ret_60 is not None and ret_60 >= 60:
        bullish.append(f"60D momentum {ret_60:+.1f}%")
    if ret_252 is not None and ret_252 >= 150:
        bullish.append(f"multi-month winner {ret_252:+.1f}%")
    if vol_ratio is not None and vol_ratio >= 1.8:
        bullish.append(f"volume expansion {vol_ratio:.1f}x 20D average")
    if news_items >= 3:
        bullish.append(f"{news_items} fresh news items")
    if policy_links:
        bullish.append(f"{policy_links} government/policy link(s)")

    if ret_5 is not None and ret_5 <= -8:
        bearish.append(f"short-term breakdown {ret_5:+.1f}% over 5D")
    if drawdown_from_high is not None and drawdown_from_high <= -15:
        bearish.append(f"{drawdown_from_high:+.1f}% below recent high")
    if above_ma20 is not None and above_ma20 >= 25 and (vol_ratio is None or vol_ratio < 1.2):
        bearish.append("price stretched above 20D average without matching volume")
    if above_ma50 is not None and above_ma50 >= 45:
        bearish.append(f"extended {above_ma50:+.1f}% above 50D average")

    breakout_score = 0.0
    for value, scale in ((ret_5, 10), (ret_20, 30), (ret_60, 80), (ret_252, 250)):
        if value is not None and value > 0:
            breakout_score += min(20, value / scale * 20)
    if vol_ratio is not None:
        breakout_score += min(15, max(0, vol_ratio - 1) * 10)
    breakout_score += min(10, news_items * 2)
    breakout_score += min(10, policy_links * 3)

    exhaustion_score = 0.0
    if drawdown_from_high is not None:
        exhaustion_score += min(25, max(0, -drawdown_from_high))
    if above_ma20 is not None:
        exhaustion_score += min(25, max(0, above_ma20 - 15))
    if above_ma50 is not None:
        exhaustion_score += min(25, max(0, above_ma50 - 30))
    if ret_5 is not None and ret_5 < 0:
        exhaustion_score += min(20, abs(ret_5) * 2)
    if vol_ratio is not None and vol_ratio < 0.8 and ret_20 is not None and ret_20 > 20:
        exhaustion_score += 10

    if breakout_score >= 55 and exhaustion_score < 45:
        verdict = "bullish_event_watch"
    elif exhaustion_score >= 55:
        verdict = "bearish_exhaustion_watch"
    elif breakout_score >= 40:
        verdict = "early_event_watch"
    else:
        verdict = "no_major_event"

    return {
        "available": True,
        "verdict": verdict,
        "breakout_score": round(min(100, breakout_score), 1),
        "exhaustion_score": round(min(100, exhaustion_score), 1),
        "returns": {
            "5d_pct": round(ret_5, 2) if ret_5 is not None else None,
            "20d_pct": round(ret_20, 2) if ret_20 is not None else None,
            "60d_pct": round(ret_60, 2) if ret_60 is not None else None,
            "252d_pct": round(ret_252, 2) if ret_252 is not None else None,
            "drawdown_from_252d_high_pct": round(drawdown_from_high, 2) if drawdown_from_high is not None else None,
        },
        "volume_ratio_20d": round(vol_ratio, 2) if vol_ratio is not None else None,
        "distance_from_ma20_pct": round(above_ma20, 2) if above_ma20 is not None else None,
        "distance_from_ma50_pct": round(above_ma50, 2) if above_ma50 is not None else None,
        "bullish_clues": bullish,
        "bearish_clues": bearish,
    }
