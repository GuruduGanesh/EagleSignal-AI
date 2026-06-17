"""Economic-event impact analysis for short-term equity/options calls.

The calendar connector answers "what scheduled events are inside the trade
horizon?"  This module answers the next question: "how can those events change
the trade?"  It is intentionally deterministic and source-driven; dates come
from ``ingestion.calendars`` and live earnings data, not from guesses.
"""
from __future__ import annotations

from typing import Any, Iterable

from ..ingestion.calendars import CalendarEvent


_KIND_DETAILS: dict[str, dict[str, str]] = {
    "fomc": {
        "channel": "rates / yields / dollar / broad-market liquidity",
        "effect": "Fed guidance can reprice growth multiples, indexes, VIX, and option IV in minutes.",
        "time": "usually 2:00 PM ET, press conference days continue after",
    },
    "nfp": {
        "channel": "labor market / wages / Fed expectations / Treasury yields",
        "effect": "Jobs surprises can move yields and index futures before the cash open.",
        "time": "usually 8:30 AM ET",
    },
    "jobless_claims": {
        "channel": "labor cooling or overheating / growth risk",
        "effect": "Claims are lower impact than NFP but can still shift rate-cut and recession expectations.",
        "time": "usually Thursday 8:30 AM ET",
    },
    "cpi": {
        "channel": "inflation / rates / real yields",
        "effect": "Inflation surprises can dominate high-beta tech, semis, and long-duration AI names.",
        "time": "usually 8:30 AM ET",
    },
    "ppi": {
        "channel": "producer inflation / margins / rates",
        "effect": "PPI can change inflation expectations and sector margin assumptions.",
        "time": "usually 8:30 AM ET",
    },
    "pce": {
        "channel": "Fed-preferred inflation / consumer income-spending",
        "effect": "Core PCE can reprice Fed path expectations and option IV.",
        "time": "usually 8:30 AM ET",
    },
    "gdp": {
        "channel": "growth / profits / recession risk",
        "effect": "GDP and corporate-profits revisions affect market regime and cyclical demand.",
        "time": "usually 8:30 AM ET",
    },
    "retail_sales": {
        "channel": "consumer demand / inflation mix",
        "effect": "Retail-sales surprises affect demand-sensitive stocks, yields, and indexes.",
        "time": "usually 8:30 AM ET",
    },
    "ism_pmi": {
        "channel": "manufacturing/services demand / supply chain",
        "effect": "PMI surprises can change cyclical, chip, storage, and industrial demand reads.",
        "time": "usually 10:00 AM ET",
    },
    "earnings": {
        "channel": "company gap risk / guidance / post-event IV crush",
        "effect": "Earnings can overpower technical/news signals and crush long option premium after the report.",
        "time": "company-specific",
    },
}


def _event_points(event: CalendarEvent) -> int:
    impact = (event.impact or "").lower()
    days = 99 if event.days_away is None else int(event.days_away)
    base = 30 if impact == "high" else 16 if impact == "medium" else 7
    if days <= 0:
        base += 18
    elif days <= 1:
        base += 14
    elif days <= 3:
        base += 8
    elif days <= 5:
        base += 4
    if event.scope == "ticker":
        base += 8
    return min(base, 55)


def _level(score: float) -> str:
    if score >= 75:
        return "extreme"
    if score >= 55:
        return "high"
    if score >= 30:
        return "medium"
    if score > 0:
        return "low"
    return "quiet"


def _direction_text(direction: str, risk_level: str) -> str:
    bull = direction in ("bullish", "neutral_to_bullish")
    bear = direction in ("bearish", "neutral_to_bearish")
    if risk_level in ("high", "extreme"):
        if bull:
            return "Bullish thesis is event-sensitive; a hot inflation/jobs/Fed shock can pull it down even if company news is good."
        if bear:
            return "Bearish/put thesis may benefit from risk-off surprises, but relief prints can reverse it sharply."
        return "No directional edge; scheduled events are large enough to wait for confirmation."
    if bull:
        return "Calendar risk is present but not dominant; keep the long thesis tied to confirmation and stops."
    if bear:
        return "Calendar risk is present but not dominant; bearish thesis needs confirmation after the release."
    return "Calendar is not the main driver for this neutral/no-trade call."


def analyze_economic_event_impact(
    events: Iterable[CalendarEvent],
    *,
    direction: str,
    horizon_days: int,
    market_regime: dict[str, Any] | None = None,
    macro_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a compact scheduled-event risk/impact object for one prediction."""
    event_list = list(events or [])
    if not event_list:
        return {
            "available": True,
            "event_count": 0,
            "high_impact_count": 0,
            "risk_score": 0,
            "risk_level": "quiet",
            "bias": "quiet_calendar",
            "action": "normal_process",
            "summary": f"No scheduled economic/company event inside the {horizon_days}D horizon.",
            "events": [],
        }

    enriched: list[dict[str, Any]] = []
    total = 0
    high = 0
    for ev in event_list:
        kind = (ev.kind or "event").lower()
        details = _KIND_DETAILS.get(kind, {
            "channel": "scheduled market event",
            "effect": "Can change liquidity, volatility, sentiment, or the market regime around the release.",
            "time": "release-time varies",
        })
        pts = _event_points(ev)
        total += pts
        if (ev.impact or "").lower() == "high":
            high += 1
        d = ev.to_dict()
        d.update({
            "risk_points": pts,
            "channel": details["channel"],
            "trade_effect": details["effect"],
            "typical_release_time": details["time"],
        })
        enriched.append(d)

    score = min(100, round(total * 0.75 + max(0, high - 1) * 8, 1))
    level = _level(score)
    first = enriched[0]
    bias = "binary_event_risk" if level in ("high", "extreme") else "event_watch"
    action = (
        "prefer_defined_risk_options_or_wait"
        if level in ("high", "extreme")
        else "keep_smaller_size_and_confirm_after_release"
        if level == "medium"
        else "normal_process"
    )

    macro_bits: list[str] = []
    mv = macro_values or {}
    if mv.get("vix") is not None:
        macro_bits.append(f"VIX {float(mv['vix']):.1f}")
    curve = mv.get("yield_curve_10y_2y") if mv.get("yield_curve_10y_2y") is not None else mv.get("yield_curve_10y_5y")
    if curve is not None:
        macro_bits.append(f"yield curve {float(curve):+.2f}")
    reg = market_regime or {}
    if reg.get("label"):
        macro_bits.append(f"market regime {reg.get('label')} ({reg.get('score', 'n/a')}/100)")

    summary = (
        f"{level.upper()} scheduled-event risk: {first.get('title')} in "
        f"{first.get('days_away')}d ({first.get('date')}); "
        f"{high} high-impact event(s), {len(enriched)} total inside {horizon_days}D. "
        f"Main channel: {first.get('channel')}. {_direction_text(direction, level)}"
    )
    if macro_bits:
        summary += " Current macro context: " + ", ".join(macro_bits[:3]) + "."

    return {
        "available": True,
        "event_count": len(enriched),
        "high_impact_count": high,
        "risk_score": score,
        "risk_level": level,
        "bias": bias,
        "action": action,
        "summary": summary,
        "directional_effect": _direction_text(direction, level),
        "events": enriched,
        "confidence_policy": (
            "High-impact scheduled events inside the horizon keep the existing 0.85 confidence haircut; "
            "this object explains the channel and trade action."
        ),
    }
