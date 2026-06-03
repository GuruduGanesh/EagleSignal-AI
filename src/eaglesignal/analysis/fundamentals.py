"""SKILL-022 Fundamental engine.

Scores balance-sheet / income-statement health from SEC XBRL company facts
(profitability, leverage, equity). Concept borrowed from
SumanthT26/USA-Stock-Market-prediction (financial-statement features), upgraded
to live SEC data. Returns available=False when no facts were retrieved.
"""
from __future__ import annotations

from ..ingestion.sec_edgar import SecData
from ..schemas import SignalComponent


def fundamental_signal(sec: SecData) -> SignalComponent:
    facts = sec.facts or {}
    notes: list[str] = []
    score = 50.0
    available = bool(facts) and any(v is not None for v in facts.values())

    if not available:
        return SignalComponent(
            name="fundamentals", score=50.0, weight=0.0, available=False,
            rationale=["No SEC fundamentals available (index/ETF or fetch failed)."],
        )

    rev, ni = facts.get("revenue"), facts.get("net_income")
    assets, liab = facts.get("assets"), facts.get("liabilities")
    equity = facts.get("stockholders_equity")

    if rev and ni is not None:
        margin = ni / rev * 100
        if margin > 15:
            score += 12; notes.append(f"Net margin {margin:.1f}% (strong profitability).")
        elif margin > 0:
            score += 4; notes.append(f"Net margin {margin:.1f}% (profitable).")
        else:
            score -= 10; notes.append(f"Net margin {margin:.1f}% (unprofitable).")

    if liab is not None and equity:
        d_e = liab / equity if equity else 99
        if d_e < 1:
            score += 8; notes.append(f"Debt/equity {d_e:.2f} (conservative balance sheet).")
        elif d_e < 2:
            score += 2; notes.append(f"Debt/equity {d_e:.2f} (moderate leverage).")
        else:
            score -= 8; notes.append(f"Debt/equity {d_e:.2f} (high leverage).")

    if assets and liab is not None:
        if assets > liab:
            score += 4; notes.append("Assets exceed liabilities.")
        else:
            score -= 12; notes.append("Liabilities exceed assets (solvency risk).")

    return SignalComponent(name="fundamentals", score=max(0, min(100, score)), weight=0.0, rationale=notes)
