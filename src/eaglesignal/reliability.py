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
from .schemas import Direction, PredictionResult, Severity
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


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


def _confidence_bucket(confidence: float | int | None) -> str:
    try:
        c = float(confidence)
    except Exception:
        return "unknown"
    if c < 50:
        return "00-49"
    if c < 65:
        return "50-64"
    if c < 75:
        return "65-74"
    if c < 85:
        return "75-84"
    return "85-100"


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


def _row_key(row: dict[str, Any]) -> str:
    return str(row.get("prediction_id") or f"{row.get('run_id')}|{row.get('ticker')}")


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
            "prediction_id": row.get("prediction_id"),
            "confidence_bucket": _confidence_bucket(row.get("confidence_score")),
        }
    except Exception as exc:
        log.warning("scorecard outcome failed for %s: %s", ticker, exc)
        return {"status": "pending", "ticker": ticker, "side": side, "error": f"{type(exc).__name__}: {exc}"}


def _prediction_outcomes(settings: Settings, limit: int = 250) -> list[dict[str, Any]]:
    rows = _read_jsonl(_base_dir(settings) / "prediction_snapshots.jsonl")[-limit:]
    return [_forward_outcome(r) for r in rows]


def _summarize_scored(scored: list[dict[str, Any]]) -> dict[str, Any]:
    hit_rate = (
        round(sum(1 for o in scored if o.get("hit")) / len(scored) * 100.0, 1)
        if scored else None
    )
    avg_side_return = (
        round(sum(float(o.get("side_return_pct", 0)) for o in scored) / len(scored), 2)
        if scored else None
    )
    return {"scored": len(scored), "hit_rate_pct": hit_rate, "avg_side_return_pct": avg_side_return}


def build_reliability_scorecard(settings: Settings, limit: int = 250) -> dict[str, Any]:
    rows = _read_jsonl(_base_dir(settings) / "prediction_snapshots.jsonl")[-limit:]
    outcomes = [_forward_outcome(r) for r in rows]
    scored = [o for o in outcomes if o.get("status") == "scored"]
    pending = [o for o in outcomes if o.get("status") == "pending"]
    not_actionable = [o for o in outcomes if o.get("status") == "not_actionable"]
    summary = _summarize_scored(scored)
    by_side: dict[str, dict[str, Any]] = {}
    for side in ("long", "short"):
        items = [o for o in scored if o.get("side") == side]
        by_side[side] = _summarize_scored(items)
    by_confidence_bucket: dict[str, dict[str, Any]] = {}
    for bucket in ("00-49", "50-64", "65-74", "75-84", "85-100"):
        items = [o for o in scored if o.get("confidence_bucket") == bucket]
        by_confidence_bucket[bucket] = _summarize_scored(items)
    return {
        "status": "ok",
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "snapshot_rows_checked": len(rows),
        "scored": len(scored),
        "pending": len(pending),
        "not_actionable": len(not_actionable),
        "hit_rate_pct": summary["hit_rate_pct"],
        "avg_side_return_pct": summary["avg_side_return_pct"],
        "by_side": by_side,
        "by_confidence_bucket": by_confidence_bucket,
        "recent_scored": scored[-25:],
        "recent_pending": pending[-25:],
        "note": "Fresh recommendations remain pending until enough future bars exist. Research only, not financial advice.",
    }


def _option_target_row(
    row: dict[str, Any],
    by_contract: dict[str, list[dict[str, Any]]],
    target_days: int,
) -> dict[str, Any]:
    ticker = str(row.get("ticker", "")).upper()
    contract = str(row.get("reference_contract", "")).upper()
    action = str(row.get("action") or "").upper()
    as_of = _parse_time(row.get("as_of"))
    entry = row.get("reference_option_price")
    if not ticker or not contract or not as_of or not entry or "BUY" not in action:
        return {"status": "not_actionable", "ticker": ticker, "contract": contract}
    try:
        entry_price = float(entry)
    except Exception:
        return {"status": "not_actionable", "ticker": ticker, "contract": contract}
    if entry_price <= 0:
        return {"status": "not_actionable", "ticker": ticker, "contract": contract}

    target_ord = as_of.date().toordinal() + max(1, target_days)
    candidates = []
    interval_marks = []
    for candidate in by_contract.get(contract, []):
        ctime = _parse_time(candidate.get("as_of"))
        mark = candidate.get("reference_option_price")
        if not ctime or mark is None:
            continue
        try:
            mark_f = float(mark)
        except Exception:
            continue
        if ctime <= as_of:
            continue
        if ctime.date().toordinal() >= target_ord:
            candidates.append((ctime, mark_f, candidate))
        else:
            interval_marks.append(mark_f)
    if not candidates:
        return {
            "status": "pending",
            "ticker": ticker,
            "contract": contract,
            "target_days": target_days,
            "reason": "no future option snapshot yet",
        }
    exit_time, exit_price, exit_row = sorted(candidates, key=lambda item: item[0])[0]
    interval_marks.append(exit_price)
    premium_return = (exit_price / entry_price - 1.0) * 100.0
    return {
        "status": "scored",
        "ticker": ticker,
        "contract": contract,
        "action": action,
        "target_days": target_days,
        "as_of": as_of.isoformat(),
        "exit_as_of": exit_time.isoformat(),
        "entry_option_price": round(entry_price, 4),
        "exit_option_price": round(exit_price, 4),
        "premium_return_pct": round(premium_return, 2),
        "hit": premium_return > 0,
        "entry_underlying": row.get("underlying_price"),
        "exit_underlying": exit_row.get("underlying_price"),
        "expiration": row.get("expiration"),
        "days_to_expiry": row.get("days_to_expiry"),
        "confidence": row.get("confidence"),
        "risk_gate": row.get("risk_gate"),
        "readiness": row.get("readiness"),
        "bid_ask_spread_pct": row.get("bid_ask_spread_pct"),
        "max_mark_pct": round((max(interval_marks) / entry_price - 1.0) * 100.0, 2) if interval_marks else None,
        "min_mark_pct": round((min(interval_marks) / entry_price - 1.0) * 100.0, 2) if interval_marks else None,
        "run_id": row.get("run_id"),
    }


def build_options_premium_scorecard(settings: Settings, limit: int = 500, target_days: int = 3) -> dict[str, Any]:
    """Score option recommendations from stored future contract marks.

    This uses only point-in-time option snapshots produced by successful scans.
    It does not fabricate premiums and it remains pending until a later scan has
    the same contract.
    """
    rows = _read_jsonl(_base_dir(settings) / "options_chain_snapshots.jsonl")[-limit:]
    by_contract: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        contract = str(row.get("reference_contract", "")).upper()
        if contract:
            by_contract.setdefault(contract, []).append(row)
    for items in by_contract.values():
        items.sort(key=lambda r: str(r.get("as_of", "")))

    outcomes = [_option_target_row(row, by_contract, target_days) for row in rows]
    scored = [o for o in outcomes if o.get("status") == "scored"]
    pending = [o for o in outcomes if o.get("status") == "pending"]
    not_actionable = [o for o in outcomes if o.get("status") == "not_actionable"]
    hit_rate = round(sum(1 for o in scored if o.get("hit")) / len(scored) * 100.0, 1) if scored else None
    avg_return = (
        round(sum(float(o.get("premium_return_pct", 0)) for o in scored) / len(scored), 2)
        if scored else None
    )
    by_gate: dict[str, dict[str, Any]] = {}
    for gate in sorted({str(o.get("risk_gate") or "unknown") for o in scored}):
        items = [o for o in scored if str(o.get("risk_gate") or "unknown") == gate]
        by_gate[gate] = {
            "scored": len(items),
            "hit_rate_pct": round(sum(1 for o in items if o.get("hit")) / len(items) * 100.0, 1) if items else None,
            "avg_premium_return_pct": round(sum(float(o.get("premium_return_pct", 0)) for o in items) / len(items), 2) if items else None,
        }
    return {
        "status": "ok",
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target_days": target_days,
        "snapshot_rows_checked": len(rows),
        "scored": len(scored),
        "pending": len(pending),
        "not_actionable": len(not_actionable),
        "hit_rate_pct": hit_rate,
        "avg_premium_return_pct": avg_return,
        "by_gate": by_gate,
        "recent_scored": scored[-25:],
        "recent_pending": pending[-25:],
        "note": "Option scorecard uses later stored option-chain marks for the same contract. It is pending until enough future scans exist.",
    }


def build_feature_label_dataset(settings: Settings, limit: int = 1000) -> dict[str, Any]:
    """Join point-in-time features to matured equity labels.

    This prepares the clean training table for future GPU ML. Rows stay out of
    the labelled set until the forward outcome is known.
    """
    base = _base_dir(settings)
    features = _read_jsonl(base / "feature_snapshots.jsonl")[-limit:]
    feature_by_key = {_row_key(row): row for row in features}
    outcomes = _prediction_outcomes(settings, limit=limit)
    labels: list[dict[str, Any]] = []
    pending = 0
    for out in outcomes:
        key = _row_key(out)
        feature = feature_by_key.get(key)
        if not feature:
            continue
        if out.get("status") != "scored":
            pending += 1
            continue
        labels.append({
            "prediction_id": key,
            "ticker": out.get("ticker"),
            "as_of": out.get("as_of"),
            "horizon_days": out.get("horizon_days"),
            "label_hit": out.get("hit"),
            "label_side_return_pct": out.get("side_return_pct"),
            "label_return_pct": out.get("return_pct"),
            "feature": feature,
        })
    return {
        "status": "ok",
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "feature_rows_checked": len(features),
        "labelled_rows": len(labels),
        "pending_rows": pending,
        "recent_labels": labels[-25:],
        "note": "Labels are joined only after forward bars exist, so GPU training avoids lookahead bias.",
    }


def build_confidence_calibration_profile(
    settings: Settings,
    limit: int = 1000,
    min_samples: int = 20,
) -> dict[str, Any]:
    outcomes = _prediction_outcomes(settings, limit=limit)
    scored = [o for o in outcomes if o.get("status") == "scored"]
    buckets: dict[str, dict[str, Any]] = {}
    for bucket in ("00-49", "50-64", "65-74", "75-84", "85-100"):
        items = [o for o in scored if o.get("confidence_bucket") == bucket]
        avg_conf = (
            round(sum(float(o.get("confidence_score", 0)) for o in items) / len(items), 1)
            if items else None
        )
        hit_rate = (
            round(sum(1 for o in items if o.get("hit")) / len(items) * 100.0, 1)
            if items else None
        )
        avg_return = (
            round(sum(float(o.get("side_return_pct", 0)) for o in items) / len(items), 2)
            if items else None
        )
        buckets[bucket] = {
            "count": len(items),
            "avg_confidence": avg_conf,
            "hit_rate_pct": hit_rate,
            "avg_side_return_pct": avg_return,
            "usable": len(items) >= min_samples,
        }
    profile = {
        "status": "ok",
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows_checked": len(outcomes),
        "scored": len(scored),
        "min_samples": min_samples,
        "buckets": buckets,
        "usable": any(b["usable"] for b in buckets.values()),
        "note": "Calibration compares historical confidence buckets with realized hit rates. Sparse buckets do not adjust live confidence.",
    }
    _write_json(_base_dir(settings) / "confidence_calibration.profile.json", profile)
    return profile


def load_confidence_calibration_profile(settings: Settings) -> dict[str, Any]:
    profile = _read_json(_base_dir(settings) / "confidence_calibration.profile.json")
    if profile:
        return profile
    return {
        "status": "missing",
        "usable": False,
        "min_samples": 20,
        "buckets": {},
        "note": "No saved calibration profile yet. Run /reliability/calibration or use the Jobs tab button.",
    }


def _calibrated_value(confidence: float, profile: dict[str, Any]) -> dict[str, Any]:
    bucket = _confidence_bucket(confidence)
    b = (profile.get("buckets") or {}).get(bucket) or {}
    if not b.get("usable"):
        return {
            "available": False,
            "bucket": bucket,
            "raw_confidence": round(confidence, 1),
            "calibrated_confidence": round(confidence, 1),
            "adjustment": 0.0,
            "sample_count": b.get("count", 0),
            "reason": f"needs {profile.get('min_samples', 20)} matured samples in confidence bucket {bucket}",
        }
    hit_rate = float(b.get("hit_rate_pct") or confidence)
    avg_conf = float(b.get("avg_confidence") or confidence)
    reliability = min(1.0, float(b.get("count", 0)) / 60.0)
    adjustment = max(-15.0, min(8.0, (hit_rate - avg_conf) * reliability))
    calibrated = max(0.0, min(100.0, confidence + adjustment))
    return {
        "available": True,
        "bucket": bucket,
        "raw_confidence": round(confidence, 1),
        "calibrated_confidence": round(calibrated, 1),
        "adjustment": round(adjustment, 1),
        "sample_count": b.get("count", 0),
        "bucket_hit_rate_pct": b.get("hit_rate_pct"),
        "bucket_avg_confidence": b.get("avg_confidence"),
        "bucket_avg_side_return_pct": b.get("avg_side_return_pct"),
        "reason": "historical confidence bucket has enough matured outcomes",
    }


def _severity(opportunity: float, confidence: float, risk, threshold: int) -> Severity:
    if risk.block_trade:
        return Severity.P3
    strong = (opportunity >= 70 or opportunity <= 30) and confidence >= threshold
    if strong and risk.risk_level.value in ("low", "medium"):
        return Severity.P1
    if opportunity >= 60 or opportunity <= 40:
        return Severity.P2
    return Severity.P3


def apply_confidence_calibration(
    predictions: list[PredictionResult],
    settings: Settings,
    *,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mutate predictions with calibrated confidence when enough history exists."""
    profile = profile or load_confidence_calibration_profile(settings)
    adjusted = 0
    for pred in predictions:
        raw = float(pred.confidence_score)
        cal = _calibrated_value(raw, profile)
        trace = dict(pred.confidence_trace or {})
        trace["raw_confidence_score"] = round(raw, 1)
        trace["calibration"] = cal
        if cal.get("available"):
            pred.confidence_score = float(cal["calibrated_confidence"])
            pred.severity = _severity(pred.opportunity_score, pred.confidence_score, pred.risk, settings.confidence_threshold)
            adjusted += 1
        pred.confidence_trace = trace
    summary = {
        "status": "ok",
        "profile_usable": profile.get("usable", False),
        "predictions_checked": len(predictions),
        "predictions_adjusted": adjusted,
        "profile": profile,
    }
    _write_json(_base_dir(settings) / "confidence_calibration.latest.json", summary)
    return summary
