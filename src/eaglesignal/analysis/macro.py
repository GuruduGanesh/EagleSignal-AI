"""SKILL-040/041 Macro & regime engine + SKILL-054/055/060 Government/policy.

Converts the FRED snapshot (plus the keyless government/fiscal snapshot) into a
market-regime score shared across all tickers (risk-on vs risk-off). Neutral when
no macro/government data is available.
"""
from __future__ import annotations

from typing import Optional

from ..ingestion.government import GovSnapshot
from ..ingestion.macro_fred import MacroSnapshot
from ..schemas import SignalComponent


def _apply_government(score: float, gov: Optional[GovSnapshot], notes: list[str]) -> float:
    if gov is None or not gov.available:
        return score
    gv = gov.values
    rate = gv.get("treasury_avg_interest_rate")
    if rate is not None:
        notes.append(f"Treasury avg interest rate on public debt {rate:.2f}%.")
        if rate > 3.5:
            score -= 2; notes.append("Elevated federal debt-service cost — mild risk-off.")
    unrate = gv.get("unemployment")
    if unrate is not None and "unemployment" not in [n.lower() for n in notes]:
        notes.append(f"BLS unemployment {unrate:.1f}%.")
    if gov.events:
        kinds = sorted({e.kind for e in gov.events})
        notes.append(f"{len(gov.events)} recent government items reviewed ({', '.join(kinds)}).")
    if gov.providers:
        notes.append("Government sources: " + ", ".join(gov.providers) + ".")
    return score


def macro_signal(macro: MacroSnapshot, gov: Optional[GovSnapshot] = None) -> SignalComponent:
    notes: list[str] = []
    if not macro.available and (gov is None or not gov.available):
        return SignalComponent(
            name="macro_regime", score=50.0, weight=0.0, available=False,
            rationale=[macro.note or "Macro/government data unavailable; neutral regime assumed."],
        )

    v = macro.values
    score = 50.0
    if macro.source:
        notes.append(f"Macro source: {macro.source}.")

    # Prefer the official 10y-2y curve; fall back to the keyless 10y-5y proxy.
    curve = v.get("yield_curve_10y_2y")
    curve_label = "10y-2y"
    if curve is None and v.get("yield_curve_10y_5y") is not None:
        curve = v.get("yield_curve_10y_5y")
        curve_label = "10y-5y"
    if curve is not None:
        if curve < 0:
            score -= 10; notes.append(f"Yield curve inverted ({curve_label} {curve:.2f}) — recession signal, risk-off.")
        else:
            score += 5; notes.append(f"Yield curve positive ({curve_label} {curve:.2f}) — risk-on.")

    ten_y = v.get("treasury_10y")
    if ten_y is not None:
        notes.append(f"10Y Treasury {ten_y:.2f}%.")
        if ten_y > 4.5:
            score -= 3; notes.append("Elevated long rates — valuation headwind for growth/tech.")

    vix = v.get("vix")
    if vix is not None:
        if vix > 25:
            score -= 8; notes.append(f"VIX {vix:.0f} (fear/high volatility).")
        elif vix < 15:
            score += 6; notes.append(f"VIX {vix:.0f} (calm/risk-on).")
        else:
            notes.append(f"VIX {vix:.0f} (normal).")

    unrate = v.get("unemployment")
    if unrate is not None:
        notes.append(f"Unemployment {unrate:.1f}%.")
        if unrate > 5:
            score -= 4

    ff = v.get("fed_funds")
    if ff is not None:
        notes.append(f"Fed funds {ff:.2f}%.")
        if ff > 5:
            score -= 3; notes.append("Restrictive policy headwind.")

    score = _apply_government(score, gov, notes)
    return SignalComponent(name="macro_regime", score=max(0, min(100, score)), weight=0.0, rationale=notes)
