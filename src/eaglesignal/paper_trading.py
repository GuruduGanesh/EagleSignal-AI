"""Paper trading ledger for dummy live-market validation.

This module never sends broker orders. It opens or updates tiny notional dummy
positions so each pipeline run can show how a suggested script is performing
against the latest market price.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import Direction, PredictionResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _side(direction: Direction) -> str | None:
    if direction in (Direction.bullish, Direction.neutral_to_bullish):
        return "long"
    if direction in (Direction.bearish, Direction.neutral_to_bearish):
        return "short"
    return None


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"positions": {}, "closed": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"positions": {}, "closed": []}


def _save(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def update_paper_trades(
    predictions: list[PredictionResult],
    data_dir: Path,
    notional: float = 1000.0,
) -> dict[str, Any]:
    """Open/update dummy positions and attach mark-to-market data to predictions."""
    path = data_dir / "paper_trades.json"
    ledger = _load(path)
    positions = ledger.setdefault("positions", {})
    changed = False

    for pred in predictions:
        price = pred.market_snapshot.get("current_price")
        if not price:
            continue
        side = _side(pred.direction)
        pos = positions.get(pred.ticker)

        if pos is None and side and not pred.risk.block_trade:
            qty = round(notional / float(price), 6)
            pos = {
                "ticker": pred.ticker,
                "actor": "EagleSignal simulated paper ledger",
                "trade_type": "system_generated_dummy_stock_position",
                "side": side,
                "entry_price": float(price),
                "quantity": qty,
                "notional": round(qty * float(price), 2),
                "opened_at": _now(),
                "entry_direction": pred.direction.value,
                "entry_opportunity_score": pred.opportunity_score,
                "entry_confidence_score": pred.confidence_score,
            }
            positions[pred.ticker] = pos
            changed = True

        if pos:
            entry = float(pos["entry_price"])
            current = float(price)
            raw_pct = (current / entry - 1) * 100 if entry else 0.0
            pnl_pct = raw_pct if pos["side"] == "long" else -raw_pct
            pnl_dollars = float(pos["notional"]) * pnl_pct / 100
            pos.update({
                "last_price": current,
                "last_marked_at": _now(),
                "unrealized_pnl_pct": round(pnl_pct, 2),
                "unrealized_pnl_dollars": round(pnl_dollars, 2),
                "latest_direction": pred.direction.value,
                "latest_opportunity_score": pred.opportunity_score,
                "latest_confidence_score": pred.confidence_score,
                "latest_risk_score": pred.risk_score,
            })
            simulated_action = (
                "SIMULATED BUY (test long)" if pos["side"] == "long"
                else "SIMULATED SELL / SHORT (test short)"
            )
            pred.paper_trade = {
                "mode": "paper_only",
                "actor": pos.get("actor", "EagleSignal simulated paper ledger"),
                "trade_type": pos.get("trade_type", "system_generated_dummy_stock_position"),
                "side": pos["side"],
                "simulated_action": simulated_action,
                "side_meaning": (
                    "EagleSignal opened this hypothetical position to score its OWN call. "
                    "long = simulated buy; short = simulated sell/short. This is NOT a company "
                    "buyback, NOT insider buying, NOT another person's trade, and NOT a real order."
                ),
                "entry_price": pos["entry_price"],
                "current_price": current,
                "quantity": pos["quantity"],
                "quantity_basis": f"${notional:,.0f} fixed test notional / entry {pos['entry_price']} = {pos['quantity']} shares (fractional)",
                "notional": pos["notional"],
                "opened_at": pos["opened_at"],
                "unrealized_pnl_pct": pos["unrealized_pnl_pct"],
                "unrealized_pnl_dollars": pos["unrealized_pnl_dollars"],
                "note": "Dummy paper trade only; no broker order was sent.",
            }
            changed = True

    ledger["updated_at"] = _now()
    if changed:
        _save(path, ledger)
    return ledger
