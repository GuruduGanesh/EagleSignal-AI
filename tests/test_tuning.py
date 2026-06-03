from eaglesignal.tuning import (
    DEFAULT_HORIZON_DAYS,
    PROFILE_HORIZON_DAYS,
    REPLAYABLE,
    horizon_for_profile,
    write_fitted,
)


def test_profile_horizon_mapping_is_multi_horizon():
    assert horizon_for_profile("intraday") == 1
    assert horizon_for_profile("swing") == 5
    assert horizon_for_profile("options_buying") == 5
    assert horizon_for_profile("long_term") == 20
    assert horizon_for_profile("index_trend") == 20
    # Unknown profile falls back to the default horizon.
    assert horizon_for_profile("made_up") == DEFAULT_HORIZON_DAYS
    # Fast and slow profiles are genuinely different horizons.
    assert PROFILE_HORIZON_DAYS["intraday"] != PROFILE_HORIZON_DAYS["long_term"]


def test_write_fitted_persists_multi_horizon_metadata(tmp_path):
    result = {
        "universe_size": 3,
        "horizon_days": None,
        "horizons": {"intraday": 1, "swing": 5},
        "profiles": {
            "intraday": {c: 10.0 for c in REPLAYABLE},
            "swing": {c: 12.0 for c in REPLAYABLE},
        },
        "note": "test",
    }
    out = tmp_path / "weights.fitted.yml"
    path = write_fitted(result, path=str(out))
    text = out.read_text(encoding="utf-8")
    assert "intraday" in text and "swing" in text
    assert "_horizons" in text
    assert str(path).endswith("weights.fitted.yml")
