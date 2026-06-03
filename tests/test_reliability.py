import json
from datetime import datetime, timezone

import pandas as pd

from eaglesignal.config import Settings
from eaglesignal.ingestion.market_data import MarketData
from eaglesignal.reliability import (
    apply_confidence_calibration,
    build_feature_label_dataset,
    build_options_premium_scorecard,
    build_reliability_scorecard,
)
from eaglesignal.schemas import AssetType, Direction, PredictionResult


def test_reliability_scorecard_empty_snapshot_store(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        historical_snapshots_dir=str(tmp_path / "historical_snapshots"),
    )

    scorecard = build_reliability_scorecard(settings)

    assert scorecard["status"] == "ok"
    assert scorecard["snapshot_rows_checked"] == 0
    assert scorecard["scored"] == 0
    assert scorecard["pending"] == 0
    assert scorecard["hit_rate_pct"] is None


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_options_premium_scorecard_uses_future_contract_marks(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        historical_snapshots_dir=str(tmp_path / "historical_snapshots"),
    )
    base = tmp_path / "historical_snapshots"
    _write_jsonl(
        base / "options_chain_snapshots.jsonl",
        [
            {
                "as_of": "2026-06-01T14:00:00+00:00",
                "ticker": "NVDA",
                "reference_contract": "NVDA260619C00120000",
                "reference_option_price": 5.0,
                "action": "BUY CALL",
                "expiration": "2026-06-19",
                "days_to_expiry": 18,
                "confidence": 82,
                "risk_gate": "high",
                "underlying_price": 120.0,
            },
            {
                "as_of": "2026-06-04T14:00:00+00:00",
                "ticker": "NVDA",
                "reference_contract": "NVDA260619C00120000",
                "reference_option_price": 7.5,
                "action": "BUY CALL",
                "expiration": "2026-06-19",
                "days_to_expiry": 15,
                "confidence": 82,
                "risk_gate": "high",
                "underlying_price": 125.0,
            },
        ],
    )

    scorecard = build_options_premium_scorecard(settings, target_days=3)

    assert scorecard["scored"] == 1
    assert scorecard["hit_rate_pct"] == 100.0
    assert scorecard["avg_premium_return_pct"] == 50.0
    assert scorecard["recent_scored"][-1]["premium_return_pct"] == 50.0


def test_feature_label_dataset_joins_features_to_matured_outcomes(tmp_path, monkeypatch):
    settings = Settings(
        data_dir=tmp_path,
        historical_snapshots_dir=str(tmp_path / "historical_snapshots"),
    )
    base = tmp_path / "historical_snapshots"
    _write_jsonl(
        base / "feature_snapshots.jsonl",
        [{"prediction_id": "p1", "ticker": "NVDA", "confidence_score": 80}],
    )
    _write_jsonl(
        base / "prediction_snapshots.jsonl",
        [
            {
                "prediction_id": "p1",
                "as_of": "2026-06-01T14:00:00+00:00",
                "ticker": "NVDA",
                "direction": "bullish",
                "horizon": "3D",
                "confidence_score": 80,
                "market_snapshot": {"current_price": 100.0},
            }
        ],
    )
    bars = pd.DataFrame(
        {"open": [100], "high": [110], "low": [99], "close": [108], "volume": [1_000_000]},
        index=pd.to_datetime(["2026-06-04"], utc=True),
    )
    monkeypatch.setattr(
        "eaglesignal.reliability.fetch_history",
        lambda *_args, **_kwargs: MarketData(ticker="NVDA", bars=bars, source="test"),
    )

    labels = build_feature_label_dataset(settings)

    assert labels["labelled_rows"] == 1
    assert labels["recent_labels"][-1]["label_hit"] is True
    assert labels["recent_labels"][-1]["feature"]["confidence_score"] == 80


def test_apply_confidence_calibration_adjusts_only_with_enough_bucket_history(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        historical_snapshots_dir=str(tmp_path / "historical_snapshots"),
    )
    pred = PredictionResult(
        prediction_id="live",
        ticker="NVDA",
        asset_type=AssetType.equity,
        direction=Direction.bullish,
        opportunity_score=82,
        confidence_score=80,
        risk_score=30,
        confidence_trace={},
    )
    profile = {
        "usable": True,
        "min_samples": 2,
        "buckets": {
            "75-84": {
                "usable": True,
                "count": 6,
                "hit_rate_pct": 60.0,
                "avg_confidence": 80.0,
                "avg_side_return_pct": -1.2,
            }
        },
    }

    summary = apply_confidence_calibration([pred], settings, profile=profile)

    assert summary["predictions_adjusted"] == 1
    assert pred.confidence_score < 80
    assert pred.confidence_trace["raw_confidence_score"] == 80
    assert pred.confidence_trace["calibration"]["available"] is True
