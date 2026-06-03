from eaglesignal.config import Settings
from eaglesignal.historical_store import iv_rank_metrics, load_snapshot_status, persist_run_snapshots
from eaglesignal.pipeline import RunResult
from eaglesignal.schemas import AssetType, Direction, PredictionResult


def test_persist_run_snapshots_writes_prediction_options_and_iv_rows(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        historical_snapshots_dir=str(tmp_path / "historical_snapshots"),
    )
    pred = PredictionResult(
        prediction_id="p1",
        ticker="NVDA",
        asset_type=AssetType.equity,
        direction=Direction.bullish,
        opportunity_score=82,
        confidence_score=78,
        risk_score=35,
        market_snapshot={"current_price": 120.0, "source": "test"},
        options_trade_idea={
            "bias": "bullish",
            "strategy": "long_call_or_call_debit_spread",
            "data_source": "test",
            "available_expirations": 1,
            "algo_confluence": 5,
            "top_expiries": [
                {
                    "expiration": "2026-06-19",
                    "days_to_expiry": 17,
                    "action": "BUY CALL",
                    "direction": "up",
                    "confidence": 81,
                    "readiness": "high",
                    "risk_gate": "high",
                    "atm_strike": 120.0,
                    "reference_contract": "NVDA260619C00120000",
                    "reference_type": "call",
                    "reference_option_price": 5.25,
                    "avg_iv": 42.0,
                    "realized_vol_20d": 35.0,
                    "iv_realized_ratio": 1.2,
                    "iv_rank": 40.0,
                    "iv_percentile": 50.0,
                    "iv_history_count": 20,
                    "total_oi": 1000,
                    "total_volume": 500,
                    "reasons": ["test reason"],
                }
            ],
        },
    )
    result = RunResult(predictions=[pred], strategy="swing", horizon="5D")

    summary = persist_run_snapshots(result, settings)
    status = load_snapshot_status(settings)

    assert summary["status"] == "ok"
    assert summary["prediction_snapshots"] == 1
    assert summary["feature_snapshots"] == 1
    assert summary["options_expiry_snapshots"] == 1
    assert summary["options_chain_snapshots"] == 1
    assert summary["iv_snapshots"] == 1
    assert summary["evidence_snapshots"] == 0
    assert status["run_files"] == 1
    assert status["prediction_snapshots"] == 1
    assert status["feature_snapshots"] == 1
    assert status["options_expiry_snapshots"] == 1
    assert status["options_chain_snapshots"] == 1
    assert status["iv_snapshots"] == 1
    assert status["evidence_snapshots"] == 0


def test_iv_rank_metrics_from_accumulated_snapshots(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        historical_snapshots_dir=str(tmp_path / "historical_snapshots"),
    )
    base = tmp_path / "historical_snapshots"
    base.mkdir()
    rows = []
    for i in range(20):
        rows.append(
            {
                "as_of": f"2026-06-{i + 1:02d}T00:00:00+00:00",
                "ticker": "NVDA",
                "expiration": "2026-07-17",
                "avg_iv": 30 + i,
            }
        )
    (base / "iv_snapshots.jsonl").write_text(
        "\n".join(__import__("json").dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )

    metrics = iv_rank_metrics(settings, "NVDA", 45.0, expiration="2026-07-17")

    assert metrics["available"] is True
    assert metrics["sample_count"] == 20
    assert metrics["scope"] == "exact_expiration"
    assert 70 <= metrics["iv_rank"] <= 85
