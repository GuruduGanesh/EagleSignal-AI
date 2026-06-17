"""SKILL-120 Multi-factor scoring (transparent weighted blend).

Pure functions, fully unit-testable (the discipline borrowed from
investdaytip). The opportunity score, confidence score, and direction are kept
distinct (ARCHITECTURE.md section 5):

* opportunity = weighted blend of component scores (how attractive)
* confidence  = how much evidence/coverage backs the blend (how reliable)
* direction   = bucketed from the opportunity score
"""
from __future__ import annotations

from typing import Optional

from ..schemas import Direction, SignalComponent

# Maps weight-file keys -> component names emitted by the engines.
WEIGHT_KEY_TO_COMPONENT = {
    "technical_structure": "technical_structure",
    "price_volume_momentum": "price_volume_momentum",
    "fundamentals": "fundamentals",
    "options_intelligence": "options_intelligence",
    "macro_regime": "macro_regime",
    "news_events": "sentiment",  # news/events folded into sentiment engine in MVP
    "sentiment": "sentiment",  # social sentiment is blended into this component (capped)
    "cross_market_correlation": "cross_market_correlation",
    "ensemble_forecast": "ensemble_forecast",  # Monte-Carlo + trend-agent ensemble
}


def apply_weights(components: list[SignalComponent], weights: dict[str, float]) -> list[SignalComponent]:
    """Attach each component's weight. Weight for missing components is
    redistributed proportionally across available ones so coverage gaps don't
    silently drag the score to 50."""
    by_name = {c.name: c for c in components}
    raw: dict[str, float] = {}
    for wkey, w in weights.items():
        if wkey == "risk_penalty_adjustment":
            continue
        comp_name = WEIGHT_KEY_TO_COMPONENT.get(wkey)
        if not comp_name:
            continue
        comp = by_name.get(comp_name)
        if comp and comp.available:
            raw[comp_name] = raw.get(comp_name, 0.0) + w

    total = sum(raw.values()) or 1.0
    for c in components:
        c.weight = raw.get(c.name, 0.0) / total
    return components


def opportunity_score(components: list[SignalComponent]) -> float:
    return round(sum(c.score * c.weight for c in components), 1)


def evidence_quality(components: list[SignalComponent]) -> float:
    """Data-quality score (0..100): how much fresh, *agreeing* evidence backs the
    blend. Rises with (a) coverage of available engines and (b) agreement among
    them (low dispersion). This is NOT the user-facing confidence — it answers
    "is the data good?", not "is there a tradeable edge?". Used by the risk
    manager and as one input to the directional confidence below."""
    available = [c for c in components if c.available]
    if not available:
        return 20.0
    coverage = len(available) / max(1, len(components))
    mean = sum(c.score for c in available) / len(available)
    dispersion = (sum((c.score - mean) ** 2 for c in available) / len(available)) ** 0.5
    agreement = max(0.0, 1 - dispersion / 35)  # 35pts std -> 0 agreement
    return round(100 * (0.55 * coverage + 0.45 * agreement), 1)


def conviction(opportunity: Optional[float]) -> float:
    """Directional conviction in [0,1] from how far opportunity sits from the
    neutral 50 line. A ~4pt dead-zone around 50 keeps genuinely neutral setups at
    zero conviction; full conviction is reached by the time the score enters the
    clearly bullish/bearish zone (~+/-22 from neutral)."""
    if opportunity is None:
        return 1.0  # caller wants pure data-quality (e.g. unit tests)
    dist = abs(float(opportunity) - 50.0)
    return max(0.0, min(1.0, (dist - 4.0) / 18.0))


def directional_alignment(components: list[SignalComponent], opportunity: float) -> float:
    """Fraction (0..1) of weighted evidence that does NOT oppose the call's side.

    This is the honest driver of confidence: a setup where the factors that *have
    data* lean the same way (or stay neutral) is trustworthy, even if they measure
    different dimensions and therefore differ in magnitude. We only subtract credit
    for components that actively point the OTHER way — not for benign, orthogonal
    spread between factors (the flaw that capped the old evidence-quality term)."""
    avail = [c for c in components if c.available]
    if not avail:
        return 0.5
    bullish = opportunity >= 50.0
    support = 0.0
    total = 0.0
    for c in avail:
        w = c.weight if c.weight > 0 else 1.0
        total += w
        lean = c.score - 50.0  # >0 bullish, <0 bearish
        # 0 when fully aligned/neutral, 1 when ~25pts against the call's side.
        against = (-lean) if bullish else lean
        opp_frac = max(0.0, min(1.0, against / 25.0))
        support += w * (1.0 - opp_frac)
    return support / total if total else 0.5


def confidence_score(components: list[SignalComponent], opportunity: Optional[float] = None) -> float:
    """User-facing confidence (0..100): conviction in an ACTIONABLE buy/sell call.

    confidence = (0.45*coverage + 0.55*directional_alignment) * (0.20 + 0.80*conviction)

    A neutral setup (opportunity ~50) has ~zero conviction, so its confidence is
    intentionally low — "no edge to trade". High confidence requires a clear
    directional lean (conviction) backed by broad coverage AND factors that agree
    on the *direction* (alignment). Confidence is then capped by the engine's
    factor-coverage ceiling so it can never exceed what the available real data
    supports. When ``opportunity`` is omitted this collapses to evidence quality
    (used by tests/callers that only compare agreement)."""
    if opportunity is None:
        return round(evidence_quality(components), 1)
    avail = [c for c in components if c.available]
    coverage = len(avail) / max(1, len(components))
    align = directional_alignment(components, opportunity)
    conv = conviction(opportunity)
    base = 100.0 * (0.45 * coverage + 0.55 * align)
    return round(base * (0.20 + 0.80 * conv), 1)


def to_direction(score: float) -> Direction:
    if score >= 70:
        return Direction.bullish
    if score >= 58:
        return Direction.neutral_to_bullish
    if score > 42:
        return Direction.neutral
    if score > 30:
        return Direction.neutral_to_bearish
    return Direction.bearish
