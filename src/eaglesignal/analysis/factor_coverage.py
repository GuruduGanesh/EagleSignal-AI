"""Factor-coverage auditor (SKILL-161 / MARKET_FACTOR_CHECKLIST gap #1).

Maps every prediction onto the 23 factor groups in ``MARKET_FACTOR_CHECKLIST.md``
and reports, honestly, which groups had REAL data today and which did not. This
is the non-manipulative answer to "why is confidence capped around 70?": the
system only has live connectors for a subset of the 23 groups, so the evidence
base — and therefore the trustworthy confidence ceiling — is bounded by coverage.

It returns:
* ``factor_coverage`` / ``missing_factor_groups`` — the checklist's required outputs
* ``coverage_pct`` — fraction of the 23 groups with usable data today
* ``confidence_ceiling`` — the highest confidence the available data can justify
* ``ceiling_reason`` — plain-English "add X, Y, Z to raise this"

Adding the missing connectors (earnings transcripts, analyst revisions, 13F /
institutional flows, alt-data, …) is what genuinely lifts the ceiling — never a
formula tweak.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a heavy import at module load
    from ..schemas import PredictionResult

# The 23 checklist groups. ``wired`` flags groups for which the project has *any*
# live connector today; the rest are honestly reported as not-yet-collected.
FACTOR_GROUPS: list[tuple[str, str]] = [
    ("company_fundamentals", "Revenue, EPS, margins, guidance (SEC/company facts)"),
    ("valuation", "P/E, EV/EBITDA, growth-adjusted valuation"),
    ("macroeconomic", "Rates, inflation, growth regime (FRED/keyless macro)"),
    ("government_policy", "Fed, Treasury, regulators, tariffs, contracts"),
    ("geopolitical", "Wars, sanctions, supply-chain, global shocks"),
    ("sector_industry", "Sector rotation & relative strength"),
    ("sentiment_psychology", "News tone + social sentiment"),
    ("technical", "Price/volume structure, indicators, patterns"),
    ("options_market", "IV, OI, put/call, expected move, Greeks"),
    ("liquidity_structure", "Tradeable liquidity, spreads, OI depth"),
    ("institutional_flows", "13F, fund flows, short interest, dark pools"),
    ("bonds_yields_credit", "Yield curve, credit spreads, real rates"),
    ("currency", "USD strength & FX revenue exposure"),
    ("commodities", "Oil, gold, copper, input costs"),
    ("global_correlation", "Overseas indexes confirming risk-on/off"),
    ("news_events", "Breaking catalysts, filings, M&A, legal"),
    ("earnings_calls", "Transcripts, guidance, demand commentary"),
    ("seasonal_calendar", "OpEx, earnings windows, rebalancing"),
    ("volatility_risk", "VIX, expected move, risk regime"),
    ("alternative_data", "Web traffic, app/card spend, job postings"),
    ("ai_technology", "AI/GPU/cloud/data-center demand signals"),
    ("index_factors", "Index weighting, ETF flows, concentration"),
    ("black_swan", "Crisis / extreme-event detector"),
]

# Groups with NO live connector yet (the engineering gap list). Surfaced verbatim
# so the user can see exactly what data would raise the confidence ceiling.
_NO_CONNECTOR = {
    "institutional_flows", "earnings_calls", "alternative_data", "black_swan",
}


def audit_factor_coverage(p: "PredictionResult") -> dict:
    cs = p.component_scores or {}
    missing_data = set(p.missing_data or [])
    fresh = p.data_freshness or {}
    trace = p.confidence_trace or {}
    idea = p.options_trade_idea or {}

    def comp_ok(name: str) -> bool:
        return name in cs and name not in missing_data

    macro_ok = comp_ok("macro_regime") and "macro" not in missing_data
    options_ok = comp_ok("options_intelligence") and "options" not in missing_data
    news_ok = int(fresh.get("news_items") or 0) > 0
    global_ok = bool(p.global_correlations)
    event_impact = trace.get("economic_event_impact") or getattr(p, "economic_event_impact", {}) or {}
    has_calendar = bool(trace.get("event_calendar")) or bool(event_impact.get("event_count"))
    regime_ok = bool((trace.get("market_regime") or {}).get("available"))

    covered: dict[str, bool] = {
        "company_fundamentals": comp_ok("fundamentals"),
        "valuation": comp_ok("fundamentals"),
        "macroeconomic": macro_ok,
        "government_policy": bool(p.policy_impacts) or fresh.get("government") == "available",
        "geopolitical": global_ok,
        "sector_industry": False,           # no dedicated sector-RS engine yet
        "sentiment_psychology": comp_ok("sentiment"),
        "technical": comp_ok("technical_structure"),
        "options_market": options_ok,
        "liquidity_structure": options_ok,
        "institutional_flows": False,
        "bonds_yields_credit": macro_ok,
        "currency": macro_ok,
        "commodities": macro_ok,
        "global_correlation": global_ok or regime_ok,
        "news_events": news_ok,
        "earnings_calls": False,            # date only; no transcript/guidance feed
        "seasonal_calendar": has_calendar,
        "volatility_risk": options_ok or macro_ok,
        "alternative_data": False,
        "ai_technology": False,
        "index_factors": global_ok or regime_ok,
        "black_swan": False,
    }

    label_by_key = dict(FACTOR_GROUPS)
    covered_keys = [k for k, v in covered.items() if v]
    missing_keys = [k for k, v in covered.items() if not v]
    coverage_pct = round(100.0 * len(covered_keys) / len(FACTOR_GROUPS), 0)

    # Honest ceiling: with only part of the 23-group picture, the most confidence
    # the data can justify scales with coverage. ~9/23 groups ⇒ ceiling ≈ 67,
    # which is exactly why production confidence has been stuck below ~70.
    confidence_ceiling = round(50.0 + 0.45 * coverage_pct, 0)

    # Directional read per group from the underlying component scores.
    bullish, bearish = [], []
    score_map = {
        "technical": cs.get("technical_structure"),
        "sentiment_psychology": cs.get("sentiment"),
        "macroeconomic": cs.get("macro_regime"),
        "options_market": cs.get("options_intelligence"),
        "company_fundamentals": cs.get("fundamentals"),
        "global_correlation": cs.get("cross_market_correlation"),
    }
    for key, sc in score_map.items():
        if sc is None or not covered.get(key):
            continue
        if sc >= 56:
            bullish.append(key)
        elif sc <= 44:
            bearish.append(key)

    # The highest-value missing groups to add next (those with no connector).
    next_to_add = [label_by_key[k] for k in missing_keys if k in _NO_CONNECTOR][:6]
    if confidence_ceiling >= round(p.confidence_score):
        ceiling_reason = (
            f"Confidence ceiling ~{confidence_ceiling:.0f} (data covers "
            f"{len(covered_keys)}/{len(FACTOR_GROUPS)} factor groups). "
            "Headroom remains; the call is currently limited by signal conviction, not data."
        )
    else:
        ceiling_reason = (
            f"Confidence is capped near {confidence_ceiling:.0f} because data covers only "
            f"{len(covered_keys)}/{len(FACTOR_GROUPS)} factor groups. To raise it (not manipulate it), "
            "add: " + ("; ".join(next_to_add) if next_to_add else "deeper coverage of the missing groups") + "."
        )

    return {
        "factor_coverage": covered_keys,
        "missing_factor_groups": missing_keys,
        "missing_factor_labels": [label_by_key[k] for k in missing_keys],
        "coverage_pct": coverage_pct,
        "covered_count": len(covered_keys),
        "total_groups": len(FACTOR_GROUPS),
        "confidence_ceiling": confidence_ceiling,
        "ceiling_reason": ceiling_reason,
        "bullish_factor_groups": bullish,
        "bearish_factor_groups": bearish,
        "next_data_to_add": next_to_add,
    }
