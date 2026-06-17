"""Broad stock-market prediction engine.

This complements single-name scoring with a market-wide read that explicitly
tracks risk-on/risk-off pressure from VIX, oil, dollar, global breadth,
government events, geopolitical headlines, and scheduled economic events.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np


GEO_TERMS = (
    "war", "missile", "attack", "iran", "israel", "gaza", "russia", "ukraine",
    "china", "taiwan", "sanction", "ofac", "tariff", "export control",
    "shipping", "red sea", "strait", "hormuz", "defense",
)
OIL_TERMS = ("oil", "crude", "wti", "brent", "opec", "gasoline", "energy")
POLICY_TERMS = ("white house", "treasury", "federal reserve", "fed", "labor", "jobs", "cpi", "pce", "fomc")


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        v = float(value)
        return v if np.isfinite(v) else None
    except Exception:
        return None


def _event_texts(events: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for ev in events or []:
        title = getattr(ev, "title", None) or (ev.get("title") if isinstance(ev, dict) else None)
        source = getattr(ev, "source", None) or (ev.get("source") if isinstance(ev, dict) else None)
        kind = getattr(ev, "kind", None) or (ev.get("kind") if isinstance(ev, dict) else None)
        text = " ".join(str(x) for x in (title, source, kind) if x)
        if text:
            out.append(text.lower())
    return out


def predict_stock_market(
    *,
    market_regime: dict[str, Any] | None = None,
    macro_values: dict[str, float] | None = None,
    gov_events: Iterable[Any] | None = None,
    global_correlations: dict[str, float] | None = None,
    economic_event_impact: dict[str, Any] | None = None,
    news_providers: list[str] | None = None,
    news_items: int = 0,
) -> dict[str, Any]:
    """Return one inspectable market-wide prediction context."""
    regime = market_regime or {}
    macro = macro_values or {}
    econ = economic_event_impact or {}
    score = float(regime.get("score") or 50.0)
    bullish: list[str] = []
    bearish: list[str] = []
    risk_drivers: list[str] = []

    if regime.get("summary"):
        (bullish if score >= 56 else bearish if score <= 44 else risk_drivers).append(str(regime["summary"])[:180])

    vix = _as_float(macro.get("vix") or regime.get("vix"))
    if vix is not None:
        if vix >= 25:
            score -= 9
            bearish.append(f"VIX {vix:.1f}: elevated fear, option premiums and whipsaws likely.")
        elif vix <= 15:
            score += 4
            bullish.append(f"VIX {vix:.1f}: calmer volatility backdrop.")

    oil = _as_float(macro.get("wti_oil"))
    if oil is not None:
        if oil >= 90:
            score -= 5
            risk_drivers.append(f"WTI oil ${oil:.1f}: inflation/geopolitical pressure risk.")
        elif oil <= 65:
            score += 2
            bullish.append(f"WTI oil ${oil:.1f}: lower energy inflation pressure.")

    dollar = _as_float(macro.get("dollar_index"))
    if dollar is not None:
        if dollar >= 108:
            score -= 4
            risk_drivers.append(f"Dollar index {dollar:.1f}: strong USD can pressure multinationals/risk assets.")
        elif dollar <= 102:
            score += 2

    event_text = " ".join(_event_texts(gov_events or []))
    geo_hits = sum(1 for term in GEO_TERMS if term in event_text)
    oil_hits = sum(1 for term in OIL_TERMS if term in event_text)
    policy_hits = sum(1 for term in POLICY_TERMS if term in event_text)
    if geo_hits:
        penalty = min(12, 3 * geo_hits)
        score -= penalty
        risk_drivers.append(f"{geo_hits} geopolitical/war-policy clue(s) in official/news feeds.")
    if oil_hits:
        score -= min(6, 2 * oil_hits)
        risk_drivers.append(f"{oil_hits} oil/energy disruption clue(s) in official/news feeds.")
    if policy_hits:
        risk_drivers.append(f"{policy_hits} policy/calendar clue(s) from official feeds.")

    if global_correlations:
        avg_abs_corr = float(np.mean([abs(float(v)) for v in global_correlations.values() if v is not None]))
        if avg_abs_corr >= 0.65 and score < 50:
            score -= 4
            risk_drivers.append("High global correlation: overseas weakness can transmit quickly into US indexes.")

    econ_level = str(econ.get("risk_level") or "quiet")
    if econ_level in ("extreme", "high"):
        score -= 7 if econ_level == "high" else 11
        risk_drivers.append(f"Scheduled economic/company calendar risk is {econ_level}.")
    elif econ_level == "medium":
        score -= 3

    score = float(np.clip(score, 0, 100))
    if score >= 64:
        direction = "risk_on"
        action = "bullish_index_bias"
    elif score <= 36:
        direction = "risk_off"
        action = "bearish_index_bias"
    elif score <= 44:
        direction = "cautious_risk_off"
        action = "prefer_defined_risk_or_put_research"
    elif score >= 56:
        direction = "constructive"
        action = "selective_call_research"
    else:
        direction = "neutral"
        action = "wait_for_cleaner_index_move"

    summary = (
        f"Stock-market engine {direction.replace('_', ' ')} ({score:.0f}/100): "
        + ("; ".join((bearish + bullish + risk_drivers)[:3]) or "no dominant macro/geopolitical edge")
    )
    return {
        "available": True,
        "score": round(score, 1),
        "direction": direction,
        "action": action,
        "summary": summary,
        "bullish_drivers": bullish[:5],
        "bearish_drivers": bearish[:5],
        "risk_drivers": risk_drivers[:6],
        "geopolitical_event_count": geo_hits,
        "oil_event_count": oil_hits,
        "policy_calendar_event_count": policy_hits,
        "news_items": int(news_items or 0),
        "news_providers": news_providers or [],
    }
