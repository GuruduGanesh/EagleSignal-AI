"""Recommendation reliability scorecard.

Confidence should be measured after the fact. This module reads point-in-time
prediction snapshots and, when enough future bars exist, marks whether the
directional call was right at the requested horizon. Fresh calls stay pending.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ROOT, Settings
from .ingestion.market_data import fetch_history
from .utils.logging import get_logger

log = get_logger("reliability")


def _base_dir(settings: Settings) -> Path:
    path = Path(settings.historical_snapshots_dir)
    if not path.is_absolute():
        path = ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _horizon_days(row: dict[str, Any]) -> int:
    raw = str(row.get("horizon") or "").upper()
    if raw == "INTRADAY":
        return 1
    if raw.endswith("D"):
        try:
            return max(1, int(raw[:-1]))
        except ValueError:
            pass
    return 5


def _side(direction: str) -> str:
    if direction in {"bullish", "neutral_to_bullish"}:
        return "long"
    if direction in {"bearish", "neutral_to_bearish"}:
        return "short"
    return "neutral"


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _forward_outcome(row: dict[str, Any]) -> dict[str, Any]:
    ticker = str(row.get("ticker", "")).upper()
    as_of = _parse_time(row.get("as_of"))
    entry = (row.get("market_snapshot") or {}).get("current_price")
    side = _side(str(row.get("direction", "")))
    days = _horizon_days(row)
    if not ticker or not as_of or not entry or side == "neutral":
        return {"status": "not_actionable", "ticker": ticker, "side": side}
    try:
        market = fetch_history(ticker, period="2y")
        df = market.bars
        if df is None or df.empty:
            return {"status": "pending", "ticker": ticker, "side": side, "reason": "no bars"}
        target = as_of.date().toordinal() + days
        eligible = [idx for idx in df.index if getattr(idx, "date", lambda: idx)().toordinal() >= target]
        if not eligible:
            return {"status": "pending", "ticker": ticker, "side": side, "horizon_days": days}
        idx = eligible[0]
        exit_price = float(df.loc[idx, "close"])
        entry_price = float(entry)
        ret = (exit_price / entry_price - 1.0) * 100.0
        side_ret = ret if side == "long" else -ret
        return {
            "status": "scored",
            "ticker": ticker,
            "side": side,
            "horizon_days": days,
            "as_of": as_of.isoformat(),
            "exit_date": str(getattr(idx, "date", lambda: idx)()),
            "entry_price": round(entry_price, 4),
            "exit_price": round(exit_price, 4),
            "return_pct": round(ret, 2),
            "side_return_pct": round(side_ret, 2),
            "hit": side_ret > 0,
            "direction": row.get("direction"),
            "opportunity_score": row.get("opportunity_score"),
            "confidence_score": row.get("confidence_score"),
            "risk_score": row.get("risk_score"),
            "run_id": row.get("run_id"),
        }
    except Exception as exc:
        log.warning("scorecard outcome failed for %s: %s", ticker, exc)
        return {"status": "pending", "ticker": ticker, "side": side, "error": f"{type(exc).__name__}: {exc}"}


def build_reliability_scorecard(settings: Settings, limit: int = 250) -> dict[str, Any]:
    rows = _read_jsonl(_base_dir(settings) / "prediction_snapshots.jsonl")[-limit:]
    outcomes = [_forward_outcome(r) for r in rows]
    scored = [o for o in outcomes if o.get("status") == "scored"]
    pending = [o for o in outcomes if o.get("status") == "pending"]
    not_actionable = [o for o in outcomes if o.get("status") == "not_actionable"]
    hit_rate = (
        round(sum(1 for o in scored if o.get("hit")) / len(scored) * 100.0, 1)
        if scored else None
    )
    avg_side_return = (
        round(sum(float(o.get("side_return_pct", 0)) for o in scored) / len(scored), 2)
        if scored else None
    )
    by_side: dict[str, dict[str, Any]] = {}
    for side in ("long", "short"):
        items = [o for o in scored if o.get("side") == side]
        by_side[side] = {
            "scored": len(items),
            "hit_rate_pct": round(sum(1 for o in items if o.get("hit")) / len(items) * 100.0, 1) if items else None,
            "avg_side_return_pct": round(sum(float(o.get("side_return_pct", 0)) for o in items) / len(items), 2) if items else None,
        }
    return {
        "status": "ok",
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot_rows_checked": len(rows),
        "scored": len(scored),
        "pending": len(pending),
        "not_actionable": len(not_actionable),
        "hit_rate_pct": hit_rate,
        "avg_side_return_pct": avg_side_return,
        "by_side": by_side,
        "recent_scored": scored[-25:],
        "recent_pending": pending[-25:],
        "note": "Fresh recommendations remain pending until enough future bars exist. Research only, not financial advice.",
    }
