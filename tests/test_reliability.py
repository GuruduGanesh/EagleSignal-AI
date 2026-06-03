from eaglesignal.config import Settings
from eaglesignal.reliability import build_reliability_scorecard


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
