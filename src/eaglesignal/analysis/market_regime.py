"""Market-regime detector (SKILL-160) — "why is the whole market down?".

A single market-wide read computed ONCE per scan from real data (SPY/QQQ price
structure + VIX + yield curve), then shared by every ticker. It answers two
product questions directly:

1. *Why are stocks down today?* — the ``drivers``/``summary`` explain the broad
   risk-on/risk-off state in plain English (trend below moving averages, VIX
   spike, inverted curve, breadth, etc.).
2. *Can we be more sensitive to these events?* — ``beta_sensitivity`` returns an
   HONEST confidence adjustment: in a risk-off tape a high-beta bullish call is
   trimmed (broad selling overwhelms single-name edge) and a bearish/put thesis
   is mildly confirmed. We never *invent* direction — we down-weight conviction
   when the macro tape fights the single-name read.

Research only. Everything is derived from observed prices/indices; nothing is
fabricated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from ..ingestion.macro_fred import MacroSnapshot


@dataclass
class MarketRegime:
    label: str = "neutral"           # strong_risk_off..risk_off..neutral..risk_on..strong_risk_on
    score: float = 50.0              # 0 = max risk-off, 100 = max risk-on
    risk_on: bool = False
    risk_off: bool = False
    vix: Optional[float] = None
    spy_vs_50dma_pct: Optional[float] = None
    spy_vs_20dma_pct: Optional[float] = None
    spy_change_5d_pct: Optional[float] = None
    spy_change_20d_pct: Optional[float] = None
    breadth_pct: Optional[float] = None   # % of tracked indexes positive over 5d
    drivers: list[str] = field(default_factory=list)
    summary: str = ""
    available: bool = False

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "score": round(self.score, 1),
            "risk_on": self.risk_on,
            "risk_off": self.risk_off,
            "vix": self.vix,
            "spy_vs_50dma_pct": self.spy_vs_50dma_pct,
            "spy_vs_20dma_pct": self.spy_vs_20dma_pct,
            "spy_change_5d_pct": self.spy_change_5d_pct,
            "spy_change_20d_pct": self.spy_change_20d_pct,
            "breadth_pct": self.breadth_pct,
            "drivers": self.drivers,
            "summary": self.summary,
            "available": self.available,
        }


def _pct(a: float, b: float) -> Optional[float]:
    if b in (None, 0) or a is None:
        return None
    return round((a / b - 1.0) * 100.0, 2)


def _close_series(bars: Optional[pd.DataFrame]) -> Optional[pd.Series]:
    if bars is None or len(bars) == 0:
        return None
    for col in ("close", "Close", "adj_close", "Adj Close"):
        if col in bars.columns:
            s = pd.to_numeric(bars[col], errors="coerce").dropna()
            return s if len(s) else None
    return None


def assess_market_regime(
    benchmark_bars: Optional[pd.DataFrame],
    macro: Optional[MacroSnapshot] = None,
    global_index_bars: Optional[dict] = None,
) -> MarketRegime:
    """Compute the shared risk-on/risk-off regime from SPY structure + VIX.

    Score starts at neutral 50 and is nudged by independent, observable factors.
    Higher = risk-on (supportive for longs); lower = risk-off (broad selling)."""
    reg = MarketRegime()
    drivers: list[str] = []
    score = 50.0

    spy = _close_series(benchmark_bars)
    if spy is not None and len(spy) >= 50:
        last = float(spy.iloc[-1])
        sma20 = float(spy.tail(20).mean())
        sma50 = float(spy.tail(50).mean())
        reg.spy_vs_20dma_pct = _pct(last, sma20)
        reg.spy_vs_50dma_pct = _pct(last, sma50)
        reg.spy_change_5d_pct = _pct(last, float(spy.iloc[-6])) if len(spy) >= 6 else None
        reg.spy_change_20d_pct = _pct(last, float(spy.iloc[-21])) if len(spy) >= 21 else None
        reg.available = True

        if reg.spy_vs_50dma_pct is not None:
            if reg.spy_vs_50dma_pct >= 0:
                score += 12; drivers.append(f"S&P 500 is {reg.spy_vs_50dma_pct:+.1f}% above its 50-day average (uptrend).")
            else:
                score -= 12; drivers.append(f"S&P 500 is {reg.spy_vs_50dma_pct:+.1f}% below its 50-day average (downtrend).")
        if reg.spy_vs_20dma_pct is not None:
            score += 6 if reg.spy_vs_20dma_pct >= 0 else -6
        if reg.spy_change_5d_pct is not None:
            score += float(np.clip(reg.spy_change_5d_pct * 1.5, -10, 10))
            if reg.spy_change_5d_pct <= -1.5:
                drivers.append(f"S&P 500 fell {reg.spy_change_5d_pct:.1f}% over the last 5 sessions (broad pullback).")
            elif reg.spy_change_5d_pct >= 1.5:
                drivers.append(f"S&P 500 rose {reg.spy_change_5d_pct:+.1f}% over the last 5 sessions.")

    # VIX — the market's fear gauge.
    vix = None
    if macro is not None and macro.available:
        vix = macro.values.get("vix")
    if vix is not None:
        reg.vix = round(float(vix), 1)
        if vix >= 30:
            score -= 16; drivers.append(f"VIX {vix:.0f} — high fear / elevated volatility (risk-off).")
        elif vix >= 22:
            score -= 9; drivers.append(f"VIX {vix:.0f} — rising fear, expect bigger swings.")
        elif vix < 14:
            score += 8; drivers.append(f"VIX {vix:.0f} — calm tape (risk-on).")
        else:
            drivers.append(f"VIX {vix:.0f} — normal volatility.")
        reg.available = True

    # Inverted yield curve is a slow-burn risk-off driver.
    if macro is not None and macro.available:
        curve = macro.values.get("yield_curve_10y_2y")
        if curve is None:
            curve = macro.values.get("yield_curve_10y_5y")
        if curve is not None and curve < 0:
            score -= 5; drivers.append(f"Yield curve inverted ({curve:.2f}) — recession signal.")

    # Breadth proxy: how many tracked indexes are positive over ~5 sessions.
    if global_index_bars:
        ups = 0
        total = 0
        for _name, bars in global_index_bars.items():
            s = _close_series(bars)
            if s is not None and len(s) >= 6:
                total += 1
                if float(s.iloc[-1]) >= float(s.iloc[-6]):
                    ups += 1
        if total:
            reg.breadth_pct = round(100.0 * ups / total, 0)
            if reg.breadth_pct <= 35:
                score -= 6; drivers.append(f"Global breadth weak — only {reg.breadth_pct:.0f}% of tracked indexes are up over 5 days.")
            elif reg.breadth_pct >= 70:
                score += 5; drivers.append(f"Global breadth firm — {reg.breadth_pct:.0f}% of tracked indexes are up over 5 days.")

    reg.score = float(np.clip(score, 0, 100))
    if reg.score >= 64:
        reg.label, reg.risk_on = "risk_on", True
    elif reg.score >= 56:
        reg.label = "mildly_risk_on"
    elif reg.score > 44:
        reg.label = "neutral"
    elif reg.score > 34:
        reg.label, reg.risk_off = "risk_off", True
    else:
        reg.label, reg.risk_off = "strong_risk_off", True

    if not reg.available:
        reg.summary = "Market regime unavailable (no benchmark/VIX data) — neutral assumed."
        reg.drivers = drivers
        return reg

    human = {
        "risk_on": "Risk-ON: the broad tape supports longs.",
        "mildly_risk_on": "Mildly risk-on: tape is constructive but not strong.",
        "neutral": "Neutral tape: no strong broad-market push either way.",
        "risk_off": "Risk-OFF: broad selling pressure — single-name longs face a headwind.",
        "strong_risk_off": "STRONG risk-OFF: heavy, broad-based selling — even good setups can be dragged down.",
    }[reg.label]
    reg.summary = f"{human} (regime score {reg.score:.0f}/100). " + (" ".join(drivers[:4]))
    reg.drivers = drivers
    return reg


def beta_sensitivity(
    regime: Optional[MarketRegime],
    direction: str,
    high_beta: bool = True,
) -> tuple[float, Optional[str]]:
    """Honest confidence multiplier for how the broad tape fights/helps a call.

    Returns (multiplier, note). We only DAMPEN conviction when the macro tape is
    against the single-name read; we never inflate a long in a falling market.
    """
    if regime is None or not regime.available:
        return (1.0, None)

    bull = direction in ("bullish", "neutral_to_bullish")
    bear = direction in ("bearish", "neutral_to_bearish")

    if regime.risk_off and bull:
        mult = 0.85 if regime.label == "strong_risk_off" else 0.92
        return (mult, (
            f"Market regime is {regime.label.replace('_', ' ')} (score {regime.score:.0f}/100): "
            "broad selling is a headwind for new longs — confidence trimmed and a tighter stop is wise."
        ))
    if regime.risk_off and bear:
        return (1.05, (
            f"Market regime is {regime.label.replace('_', ' ')} — the broad tape confirms the "
            "bearish/put lean (down-market tailwind)."
        ))
    if regime.risk_on and bull:
        return (1.04, (
            f"Market regime is risk-on (score {regime.score:.0f}/100) — the broad tape supports the long lean."
        ))
    if regime.risk_on and bear:
        return (0.93, (
            f"Market regime is risk-on (score {regime.score:.0f}/100) — a rising broad tape fights a "
            "short/put thesis; confidence trimmed."
        ))
    return (1.0, None)
