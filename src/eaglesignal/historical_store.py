"""Point-in-time historical snapshot persistence.

The prediction engine must not tune non-price signals against today's news,
fundamentals, macro, sentiment, or options data. This module records each live
scan exactly as seen at run time so future backtests, IV Rank, and reliability
scorecards can replay real historical inputs instead of introducing lookahead.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .config import ROOT, Settings
from .schemas import PredictionResult
from .utils.logging import get_logger

if TYPE_CHECKING:
    from .pipeline import RunResult

log = get_logger("historical_store")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _base_dir(settings: Settings) -> Path:
    path = Path(settings.historical_snapshots_dir)
    if not path.is_absolute():
        path = ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, default=str, sort_keys=True) + "\n")


def _read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
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
    if limit is not None and limit > 0:
        return rows[-limit:]
    return rows


def load_iv_history(settings: Settings, ticker: str, limit: int = 250) -> list[dict[str, Any]]:
    """Recent point-in-time IV observations for one ticker.

    The rows are produced only by successful live scans. IV Rank/Percentile must
    be treated as unavailable until enough rows accumulate.
    """
    base = _base_dir(settings)
    symbol = ticker.strip().upper()
    rows = [
        r for r in _read_jsonl(base / "iv_snapshots.jsonl")
        if str(r.get("ticker", "")).upper() == symbol and r.get("avg_iv") is not None
    ]
    rows.sort(key=lambda r: str(r.get("as_of", "")))
    return rows[-limit:]


def load_option_contract_history(settings: Settings, ticker: str, limit: int = 1000) -> dict[str, dict[str, Any]]:
    """Latest stored option snapshot by exact contract for one ticker.

    This is intentionally point-in-time and read-only. It lets the live options
    engine compare current OI/volume to the previous successful scan without
    claiming a licensed unusual-flow feed.
    """
    base = _base_dir(settings)
    symbol = ticker.strip().upper()
    rows = [
        r for r in _read_jsonl(base / "options_chain_snapshots.jsonl", limit=limit)
        if str(r.get("ticker", "")).upper() == symbol and r.get("reference_contract")
    ]
    rows.sort(key=lambda r: str(r.get("as_of", "")))
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest[str(row.get("reference_contract", "")).upper()] = row
    return latest


def iv_rank_metrics(
    settings: Settings,
    ticker: str,
    current_iv: float | None,
    *,
    expiration: str | None = None,
    min_samples: int = 20,
) -> dict[str, Any]:
    """Compute IV Rank and IV Percentile from accumulated live snapshots.

    Uses exact-expiration history when enough rows exist; otherwise falls back
    to all stored IV rows for the ticker. Returns an ``available`` flag so the
    options engine can gate conclusions honestly.
    """
    if current_iv is None:
        return {"available": False, "reason": "current IV unavailable"}
    rows = load_iv_history(settings, ticker)
    exact = [r for r in rows if expiration and r.get("expiration") == expiration]
    sample = exact if len(exact) >= min_samples else rows
    values: list[float] = []
    for row in sample:
        try:
            values.append(float(row["avg_iv"]))
        except Exception:
            continue
    if len(values) < min_samples:
        return {
            "available": False,
            "sample_count": len(values),
            "min_samples": min_samples,
            "reason": f"needs at least {min_samples} IV snapshots",
        }
    lo, hi = min(values), max(values)
    rank = 50.0 if hi <= lo else (float(current_iv) - lo) / (hi - lo) * 100.0
    percentile = sum(1 for v in values if v <= float(current_iv)) / len(values) * 100.0
    return {
        "available": True,
        "sample_count": len(values),
        "scope": "exact_expiration" if sample is exact else "ticker",
        "iv_rank": round(max(0.0, min(100.0, rank)), 1),
        "iv_percentile": round(max(0.0, min(100.0, percentile)), 1),
        "iv_min": round(lo, 2),
        "iv_max": round(hi, 2),
    }


def _compact_option_expiry(pred: PredictionResult, expiry: dict[str, Any], run_id: str, as_of: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "as_of": as_of,
        "ticker": pred.ticker,
        "horizon": pred.horizon,
        "strategy": pred.strategy,
        "underlying_price": (pred.market_snapshot or {}).get("current_price"),
        "data_source": (pred.options_trade_idea or {}).get("data_source"),
        "expiration": expiry.get("expiration"),
        "days_to_expiry": expiry.get("days_to_expiry"),
        "action": expiry.get("action"),
        "direction": expiry.get("direction"),
        "confidence": expiry.get("confidence"),
        "readiness": expiry.get("readiness"),
        "risk_gate": expiry.get("risk_gate"),
        "atm_strike": expiry.get("atm_strike"),
        "reference_contract": expiry.get("reference_contract"),
        "reference_type": expiry.get("reference_type"),
        "reference_option_price": expiry.get("reference_option_price"),
        "reference_bid": expiry.get("reference_bid"),
        "reference_ask": expiry.get("reference_ask"),
        "bid_ask_spread_pct": expiry.get("bid_ask_spread_pct"),
        "avg_iv": expiry.get("avg_iv"),
        "realized_vol_20d": expiry.get("realized_vol_20d"),
        "iv_realized_ratio": expiry.get("iv_realized_ratio"),
        "atm_iv_skew_pct": expiry.get("atm_iv_skew_pct"),
        "skew_label": expiry.get("skew_label"),
        "term_structure_slope_pct": expiry.get("term_structure_slope_pct"),
        "term_structure_label": expiry.get("term_structure_label"),
        "put_call_ratio": expiry.get("put_call_ratio"),
        "total_oi": expiry.get("total_oi"),
        "total_volume": expiry.get("total_volume"),
        "exact_contract_oi": expiry.get("exact_contract_oi"),
        "exact_contract_volume": expiry.get("exact_contract_volume"),
        "volume_oi_ratio": expiry.get("volume_oi_ratio"),
        "unusual_activity_score": expiry.get("unusual_activity_score"),
        "unusual_activity_label": expiry.get("unusual_activity_label"),
        "previous_exact_contract_oi": expiry.get("previous_exact_contract_oi"),
        "oi_change": expiry.get("oi_change"),
        "oi_change_pct": expiry.get("oi_change_pct"),
        "delta": expiry.get("delta"),
        "gamma": expiry.get("gamma"),
        "theta_per_day": expiry.get("theta_per_day"),
        "vega_per_vol_point": expiry.get("vega_per_vol_point"),
        "breakeven_price": expiry.get("breakeven_price"),
        "breakeven_pct": expiry.get("breakeven_pct"),
        "premium_pct_spot": expiry.get("premium_pct_spot"),
        "option_quality_score": expiry.get("option_quality_score"),
        "flow_alignment": expiry.get("flow_alignment"),
        "iv_risk": expiry.get("iv_risk"),
        "reasons": expiry.get("reasons", [])[:8],
    }


def _compact_prediction(pred: PredictionResult, run_id: str, as_of: str) -> dict[str, Any]:
    forecast = pred.forecast.model_dump(mode="json") if pred.forecast else {}
    expected_move = pred.expected_move.model_dump(mode="json") if pred.expected_move else {}
    top_expiries = (pred.options_trade_idea or {}).get("top_expiries", [])[:3]
    return {
        "run_id": run_id,
        "as_of": as_of,
        "prediction_id": pred.prediction_id,
        "ticker": pred.ticker,
        "asset_type": pred.asset_type.value,
        "horizon": pred.horizon,
        "strategy": pred.strategy,
        "direction": pred.direction.value,
        "opportunity_score": pred.opportunity_score,
        "confidence_score": pred.confidence_score,
        "risk_score": pred.risk_score,
        "risk_level": pred.risk.risk_level.value,
        "severity": pred.severity.value,
        "component_scores": pred.component_scores,
        "component_weights": pred.component_weights,
        "market_snapshot": pred.market_snapshot,
        "forecast": forecast,
        "expected_move": expected_move,
        "trend_impact": pred.trend_impact,
        "event_radar": pred.event_radar,
        "final_verdict": pred.final_verdict,
        "confidence_trace": pred.confidence_trace,
        "global_correlations": pred.global_correlations,
        "data_freshness": pred.data_freshness,
        "missing_data": pred.missing_data,
        "source_links": pred.source_links[:10],
        "catalysts": pred.catalysts[:8],
        "policy_impacts": pred.policy_impacts[:8],
        "invalidation_conditions": pred.invalidation_conditions,
        "options_summary": {
            "bias": (pred.options_trade_idea or {}).get("bias"),
            "strategy": (pred.options_trade_idea or {}).get("strategy"),
            "data_source": (pred.options_trade_idea or {}).get("data_source"),
            "available_expirations": (pred.options_trade_idea or {}).get("available_expirations"),
            "algo_confluence": (pred.options_trade_idea or {}).get("algo_confluence"),
            "top_expiries": top_expiries,
        },
    }


def _compact_feature_row(pred: PredictionResult, run_id: str, as_of: str) -> dict[str, Any]:
    """Flatten the prediction into a model-training feature row.

    This is intentionally point-in-time and label-free. Labels are added later
    by the reliability module only after forward bars/option marks exist.
    """
    market = pred.market_snapshot or {}
    trace = pred.confidence_trace or {}
    trend = pred.trend_impact or {}
    radar = pred.event_radar or {}
    options = pred.options_trade_idea or {}
    top_expiry = (options.get("top_expiries") or [{}])[0] or {}
    forecast = pred.forecast.model_dump(mode="json") if pred.forecast else {}
    short_2d = (
        pred.short_horizon_forecasts.get("2D").model_dump(mode="json")
        if pred.short_horizon_forecasts.get("2D") else {}
    )
    short_3d = (
        pred.short_horizon_forecasts.get("3D").model_dump(mode="json")
        if pred.short_horizon_forecasts.get("3D") else {}
    )
    return {
        "run_id": run_id,
        "as_of": as_of,
        "prediction_id": pred.prediction_id,
        "ticker": pred.ticker,
        "asset_type": pred.asset_type.value,
        "horizon": pred.horizon,
        "strategy": pred.strategy,
        "direction": pred.direction.value,
        "opportunity_score": pred.opportunity_score,
        "confidence_score": pred.confidence_score,
        "raw_confidence_score": trace.get("raw_confidence_score", pred.confidence_score),
        "calibration_adjustment": (trace.get("calibration") or {}).get("adjustment"),
        "risk_score": pred.risk_score,
        "risk_level": pred.risk.risk_level.value,
        "severity": pred.severity.value,
        "current_price": market.get("current_price"),
        "day_change_pct": market.get("day_change_pct"),
        "last_volume": market.get("last_volume"),
        "market_source": market.get("source"),
        "component_scores": pred.component_scores,
        "component_weights": pred.component_weights,
        "directional_conviction_pct": trace.get("directional_conviction_pct"),
        "data_quality_pct": trace.get("data_quality_pct"),
        "coverage_pct": trace.get("coverage_pct"),
        "agreement_pct": trace.get("agreement_pct"),
        "evidence_count": trace.get("evidence_count"),
        "missing_data_count": len(pred.missing_data or []),
        "source_link_count": len(pred.source_links or []),
        "news_items": trend.get("news_items"),
        "avg_evidence_polarity": trend.get("avg_evidence_polarity"),
        "policy_event_count": trend.get("policy_event_count"),
        "social_net_sentiment": trend.get("social_net_sentiment"),
        "forecast_prob_up": forecast.get("prob_up"),
        "forecast_expected_return_pct": forecast.get("expected_return_pct"),
        "forecast_p05_return_pct": forecast.get("p05_return_pct"),
        "forecast_p95_return_pct": forecast.get("p95_return_pct"),
        "forecast_2d_prob_up": short_2d.get("prob_up"),
        "forecast_2d_expected_return_pct": short_2d.get("expected_return_pct"),
        "forecast_3d_prob_up": short_3d.get("prob_up"),
        "forecast_3d_expected_return_pct": short_3d.get("expected_return_pct"),
        "event_radar_verdict": radar.get("verdict"),
        "event_radar_breakout_score": radar.get("breakout_score"),
        "event_radar_exhaustion_score": radar.get("exhaustion_score"),
        "options_bias": options.get("bias"),
        "options_strategy": options.get("strategy"),
        "options_data_source": options.get("data_source"),
        "options_algo_confluence": options.get("algo_confluence"),
        "options_available_expirations": options.get("available_expirations"),
        "top_option_expiration": top_expiry.get("expiration"),
        "top_option_dte": top_expiry.get("days_to_expiry"),
        "top_option_action": top_expiry.get("action"),
        "top_option_confidence": top_expiry.get("confidence"),
        "top_option_risk_gate": top_expiry.get("risk_gate"),
        "top_option_price": top_expiry.get("reference_option_price"),
        "top_option_spread_pct": top_expiry.get("bid_ask_spread_pct"),
        "top_option_avg_iv": top_expiry.get("avg_iv"),
        "top_option_iv_rank": top_expiry.get("iv_rank"),
        "top_option_iv_realized_ratio": top_expiry.get("iv_realized_ratio"),
        "top_option_delta": top_expiry.get("delta"),
        "top_option_theta_per_day": top_expiry.get("theta_per_day"),
        "top_option_volume": top_expiry.get("exact_contract_volume"),
        "top_option_oi": top_expiry.get("exact_contract_oi"),
        "top_option_uoa_score": top_expiry.get("unusual_activity_score"),
        "top_option_oi_change_pct": top_expiry.get("oi_change_pct"),
        "final_verdict_label": (pred.final_verdict or {}).get("label"),
        "final_research_action": (pred.final_verdict or {}).get("research_action"),
    }


def _compact_evidence(result: "RunResult", run_id: str, as_of: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ev in result.evidence.all():
        rows.append({
            "run_id": run_id,
            "as_of": as_of,
            "evidence_id": ev.evidence_id,
            "entity": ev.entity,
            "source_name": ev.source_name,
            "source_type": ev.source_type,
            "url": ev.url,
            "retrieved_at": ev.retrieved_at.isoformat(),
            "published_at": ev.published_at.isoformat() if ev.published_at else None,
            "claim": ev.claim,
            "raw_excerpt": ev.raw_excerpt,
            "polarity": ev.polarity,
            "reliability_score": ev.reliability_score,
            "freshness_score": ev.freshness_score,
        })
    return rows


def persist_run_snapshots(result: "RunResult", settings: Settings) -> dict[str, Any]:
    """Persist compact point-in-time snapshots for one successful pipeline run."""
    if not settings.enable_historical_snapshots:
        return {"enabled": False, "status": "skipped"}

    as_of = _utcnow()
    run_id = f"{result.started_at.strftime('%Y%m%dT%H%M%SZ')}-{result.strategy}-{result.horizon}"
    base = _base_dir(settings)
    day_dir = base / as_of[:10]
    day_dir.mkdir(parents=True, exist_ok=True)

    prediction_rows = [_compact_prediction(p, run_id, as_of) for p in result.predictions]
    feature_rows = [_compact_feature_row(p, run_id, as_of) for p in result.predictions]
    option_rows: list[dict[str, Any]] = []
    chain_rows: list[dict[str, Any]] = []
    iv_rows: list[dict[str, Any]] = []
    for pred in result.predictions:
        all_expiries = (
            (pred.options_trade_idea or {}).get("all_expiry_snapshots")
            or (pred.options_trade_idea or {}).get("top_expiries", [])
        )
        for expiry in all_expiries[:20]:
            row = _compact_option_expiry(pred, expiry, run_id, as_of)
            option_rows.append(row)
            chain_rows.append({
                **row,
                "snapshot_type": "selected_expiry_contract",
                "available_expiration_count": (pred.options_trade_idea or {}).get("available_expirations"),
                "available_expirations": (pred.options_trade_idea or {}).get("available_expiration_list", []),
                "iv_rank": expiry.get("iv_rank"),
                "iv_percentile": expiry.get("iv_percentile"),
                "iv_history_count": expiry.get("iv_history_count"),
                "iv_history_scope": expiry.get("iv_history_scope"),
            })
            if row.get("avg_iv") is not None:
                iv_rows.append({
                    "run_id": run_id,
                    "as_of": as_of,
                    "ticker": pred.ticker,
                    "underlying_price": row.get("underlying_price"),
                    "expiration": row.get("expiration"),
                    "days_to_expiry": row.get("days_to_expiry"),
                    "avg_iv": row.get("avg_iv"),
                    "reference_contract": row.get("reference_contract"),
                    "reference_type": row.get("reference_type"),
                    "reference_option_price": row.get("reference_option_price"),
                    "realized_vol_20d": row.get("realized_vol_20d"),
                    "iv_realized_ratio": row.get("iv_realized_ratio"),
                    "iv_rank": expiry.get("iv_rank"),
                    "iv_percentile": expiry.get("iv_percentile"),
                    "iv_history_count": expiry.get("iv_history_count"),
                    "data_source": row.get("data_source"),
                })
    evidence_rows = _compact_evidence(result, run_id, as_of)

    run_doc = {
        "run_id": run_id,
        "as_of": as_of,
        "started_at": result.started_at.isoformat(),
        "strategy": result.strategy,
        "horizon": result.horizon,
        "prediction_count": len(result.predictions),
        "macro": result.macro.__dict__,
        "government": {
            "available": result.government.available,
            "providers": result.government.providers,
            "values": result.government.values,
            "event_count": len(result.government.events),
            "events": [
                {
                    "title": e.title,
                    "source": e.source,
                    "kind": e.kind,
                    "url": e.url,
                    "published_at": e.published_at.isoformat() if e.published_at else None,
                }
                for e in result.government.events[:100]
            ],
        },
        "global_markets": {
            "available": result.global_markets.available,
            "regime_note": result.global_markets.regime_note,
            "advancers": result.global_markets.advancers,
            "decliners": result.global_markets.decliners,
        },
        "evidence": evidence_rows[:2000],
        "predictions": prediction_rows,
    }

    run_path = day_dir / f"{run_id}.json"
    run_path.write_text(json.dumps(run_doc, indent=2, default=str, sort_keys=True), encoding="utf-8")

    _append_jsonl(base / "prediction_snapshots.jsonl", prediction_rows)
    _append_jsonl(base / "feature_snapshots.jsonl", feature_rows)
    _append_jsonl(base / "options_expiry_snapshots.jsonl", option_rows)
    _append_jsonl(base / "options_chain_snapshots.jsonl", chain_rows)
    _append_jsonl(base / "iv_snapshots.jsonl", iv_rows)
    _append_jsonl(base / "evidence_snapshots.jsonl", evidence_rows)

    summary = {
        "enabled": True,
        "status": "ok",
        "run_id": run_id,
        "run_file": str(run_path),
        "prediction_snapshots": len(prediction_rows),
        "feature_snapshots": len(feature_rows),
        "options_expiry_snapshots": len(option_rows),
        "options_chain_snapshots": len(chain_rows),
        "iv_snapshots": len(iv_rows),
        "evidence_snapshots": len(evidence_rows),
        "base_dir": str(base),
    }
    log.info("historical snapshots persisted: %s", summary)
    return summary


def load_snapshot_status(settings: Settings) -> dict[str, Any]:
    """Return lightweight counts/paths for historical snapshot files."""
    base = _base_dir(settings)

    def _line_count(path: Path) -> int:
        if not path.exists():
            return 0
        with path.open("r", encoding="utf-8") as fh:
            return sum(1 for _ in fh)

    runs = sorted(
        [p for p in base.glob("*/*.json") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    latest_run = runs[0] if runs else None
    return {
        "enabled": settings.enable_historical_snapshots,
        "base_dir": str(base),
        "run_files": len(runs),
        "latest_run_file": str(latest_run) if latest_run else None,
        "prediction_snapshots": _line_count(base / "prediction_snapshots.jsonl"),
        "feature_snapshots": _line_count(base / "feature_snapshots.jsonl"),
        "options_expiry_snapshots": _line_count(base / "options_expiry_snapshots.jsonl"),
        "options_chain_snapshots": _line_count(base / "options_chain_snapshots.jsonl"),
        "iv_snapshots": _line_count(base / "iv_snapshots.jsonl"),
        "evidence_snapshots": _line_count(base / "evidence_snapshots.jsonl"),
        "status": "ok",
    }
