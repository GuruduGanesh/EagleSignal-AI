"""Index option STRATEGIES with per-strategy confidence (SKILL-164).

The product's primary focus. Reuses the per-expiry analysis already computed by
``analyze_expiries`` (which folds in the full engine context: technicals,
momentum, IV, liquidity, macro regime, news, government/geopolitical/oil) and
turns it into ranked option strategies under the user's hard rules:

* underlying must be a supported US cash index option ticker,
* option premium < ``max_option_price`` (default $35),
* estimated option profit ≥ ``min_profit_pct`` (default 10%),
* prefer LOWER premium + HIGHER volume + HIGHER (direction-aligned) momentum,
* STRICT actionable gate: underlying expected move ≥ 50 index points AND
  option profit ≥ 10%.

Every field is populated; rows that miss the strict gate are SHOWN with a clear
status rather than hidden, so the table never looks empty.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .index_options import INDEX_MARKET_ALIASES, INDEX_OPTION_UNDERLYINGS, is_index_option_ticker

if TYPE_CHECKING:
    from ..schemas import PredictionResult

INDEX_LABEL = {
    **{k: v.replace(" options", "") for k, v in INDEX_OPTION_UNDERLYINGS.items()},
}

UNDERLYING_MOVE_RULE_POINTS = 50.0
MIN_PROFIT_RULE_PCT = 10.0
# Realistic best-case ceiling on the estimated option profit, and the minimum
# options confidence a row needs before it can be called ACTIONABLE. These keep
# implausible far-OTM estimates and near-zero-confidence rows out of the green.
PROFIT_CAP_PCT = 250.0
MIN_ACTIONABLE_CONFIDENCE = 35.0


def is_index_strategy_ticker(p: "PredictionResult") -> bool:
    if is_index_option_ticker(getattr(p, "ticker", None)):
        return True
    return str(getattr(p, "asset_type", "")).endswith("index")


def _strategy_name(action: str, strategy_label: Optional[str]) -> str:
    sl = (strategy_label or "").lower()
    if "iron condor" in sl:
        return "Iron Condor (defined-risk range)"
    if "bull put" in sl or "put credit" in sl:
        return "Bull Put Credit Spread"
    if "bear call" in sl or "call credit" in sl:
        return "Bear Call Credit Spread"
    if "bull call" in sl or "call debit" in sl:
        return "Bull Call Debit Spread"
    if "bear put" in sl or "put debit" in sl:
        return "Bear Put Debit Spread"
    if action == "BUY CALL":
        return "Long Call"
    if action == "BUY PUT":
        return "Long Put"
    return "No directional edge"


def _safe(v, d=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def build_index_strategies(
    predictions: list["PredictionResult"],
    *,
    max_option_price: float = 35.0,
    min_profit_pct: float = 10.0,
    per_index: int = 3,
) -> list[dict]:
    """Return ranked index option strategies (all values populated)."""
    rows: list[dict] = []
    for p in predictions:
        if not is_index_strategy_ticker(p):
            continue
        snap = p.market_snapshot or {}
        current = _safe(snap.get("current_price"))
        target = _safe(p.target_price)
        underlying_move_pct = _safe(p.expected_percent, 0.0) or 0.0
        underlying_move_points = _safe(getattr(p, "expected_points", None))
        if underlying_move_points is None and current is not None and target is not None:
            underlying_move_points = target - current
        underlying_move_points = underlying_move_points or 0.0
        momentum = _safe((p.component_scores or {}).get("price_volume_momentum"), 50.0) or 50.0
        regime = (p.market_regime or {}).get("label", "n/a")
        label = INDEX_LABEL.get(p.ticker, p.ticker)
        min_move_points = _safe(
            ((p.options_trade_idea or {}).get("min_index_option_move_points")),
            UNDERLYING_MOVE_RULE_POINTS,
        ) or UNDERLYING_MOVE_RULE_POINTS
        drivers = []
        if p.trend_impact.get("summary"):
            drivers.append(str(p.trend_impact["summary"]))
        if p.catalysts:
            drivers.append(str(p.catalysts[0]))
        why_base = f"regime {regime}; " + ("; ".join(drivers[:2]) or "macro/technical blend")

        idea = p.options_trade_idea or {}
        snapshots = idea.get("all_expiry_snapshots") or idea.get("top_expiries") or []
        per_rows: list[dict] = []
        for ex in snapshots:
            action = ex.get("action") or "NO TRADE"
            premium = _safe(ex.get("reference_option_price"))
            if premium is None or premium <= 0 or premium >= max_option_price:
                continue
            delta = _safe(ex.get("delta")) or 0.0
            if current is not None and target is not None and delta:
                opt_exit = premium + abs(delta) * abs(target - current)
            else:
                opt_exit = premium * 1.25
            # Cap the estimate at a realistic best-case multiple. A cheap far-OTM
            # index contract cannot plausibly 10x-30x from a few-percent index move;
            # the linear delta×move estimate over-shoots when the snapshot delta is
            # the ATM reference rather than the cheap contract's own delta.
            opt_exit = min(opt_exit, premium * (1.0 + PROFIT_CAP_PCT / 100.0))
            profit_pct = (opt_exit - premium) / premium * 100.0 if premium else 0.0
            profit_capped = profit_pct >= PROFIT_CAP_PCT - 0.01
            mult = ex.get("contract_multiplier") or 100
            profit_per_contract = (opt_exit - premium) * mult
            volume = ex.get("exact_contract_volume")
            if volume in (None, "", "—"):
                volume = ex.get("total_volume") or 0
            volume = int(_safe(volume, 0) or 0)
            confidence = _safe(ex.get("confidence"), 0.0) or 0.0
            direction = ex.get("direction", "neutral")
            aligned_mom = momentum if direction == "up" else (100 - momentum) if direction == "down" else 50.0
            directionless = action == "NO TRADE" or direction == "neutral"

            move_ok = abs(underlying_move_points) >= min_move_points
            profit_ok = profit_pct >= min_profit_pct
            both_ok = move_ok and profit_ok
            # A row is ACTIONABLE only when it clears the strict gate AND is a real
            # directional/structured trade with usable confidence — never a
            # "no directional edge" or near-zero-confidence row.
            actionable = both_ok and not directionless and confidence >= MIN_ACTIONABLE_CONFIDENCE
            if directionless:
                status, status_color = "👀 no directional edge", "#6b7280"
            elif actionable:
                status, status_color = "✅ ACTIONABLE", "#16a34a"
            elif both_ok and confidence < MIN_ACTIONABLE_CONFIDENCE:
                status, status_color = f"⚠️ confidence <{MIN_ACTIONABLE_CONFIDENCE:.0f}", "#b45309"
            elif profit_ok and not move_ok:
                status, status_color = f"⚠️ needs >={min_move_points:.0f} index pts", "#b45309"
            elif move_ok and not profit_ok:
                status, status_color = f"⚠️ option profit <{min_profit_pct:.0f}%", "#b45309"
            else:
                status, status_color = "👀 watch", "#6b7280"

            price_score = max(0.0, (max_option_price - premium) / max_option_price) * 100.0
            vol_score = min(100.0, (volume / 1000.0) * 100.0) if volume else 0.0
            select_score = round(
                0.34 * confidence + 0.24 * price_score + 0.24 * vol_score + 0.18 * aligned_mom, 1
            )

            per_rows.append({
                "index": p.ticker,
                "index_label": label,
                "tradeable": p.ticker,
                "is_proxy": False,
                "strategy": _strategy_name(action, ex.get("strategy_label")),
                "action": action,
                "direction": direction,
                "arrow": ex.get("arrow", ""),
                "confidence": round(confidence, 0),
                "select_score": select_score,
                "contract": ex.get("reference_contract") or "—",
                "expiration": ex.get("expiration") or "—",
                "dte": ex.get("days_to_expiry"),
                "strike": ex.get("atm_strike"),
                "entry_premium": round(premium, 2),
                "est_exit": round(opt_exit, 2),
                "profit_pct": round(profit_pct, 1),
                "profit_capped": profit_capped,
                "profit_per_contract": round(profit_per_contract, 0),
                "actionable": actionable,
                "volume": volume,
                "open_interest": ex.get("exact_contract_oi") or ex.get("total_oi") or 0,
                "iv": ex.get("avg_iv"),
                "spread_pct": ex.get("bid_ask_spread_pct"),
                "delta": ex.get("delta"),
                "theta_per_day": ex.get("theta_per_day"),
                "gate": ex.get("risk_gate") or ex.get("readiness") or "watch",
                "momentum": round(momentum, 0),
                "underlying_current": round(current, 2) if current is not None else None,
                "underlying_target": round(target, 2) if target is not None else None,
                "underlying_move_points": round(underlying_move_points, 2),
                "underlying_move_pct": round(underlying_move_pct, 2),
                "min_index_move_points": round(min_move_points, 0),
                "move_ok": move_ok,
                "profit_ok": profit_ok,
                "both_ok": both_ok,
                "status": status,
                "status_color": status_color,
                "regime": regime,
                "market_symbol": INDEX_MARKET_ALIASES.get(p.ticker, p.ticker),
                "why": (f"{why_base}; option conf {confidence:.0f}, premium ${premium:.2f}, "
                        f"vol {volume:,}, momentum {momentum:.0f}, "
                        f"expected move {underlying_move_points:+.1f} pts"),
            })

        per_rows.sort(key=lambda r: (r["actionable"], r["select_score"]), reverse=True)
        rows.extend(per_rows[:per_index])

    rows.sort(key=lambda r: (r["actionable"], r["select_score"]), reverse=True)
    return rows
