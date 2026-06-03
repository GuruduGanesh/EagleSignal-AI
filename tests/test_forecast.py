from eaglesignal.analysis import forecast as fc


def test_monte_carlo_bands_ordered(uptrend_df):
    mc = fc.monte_carlo(uptrend_df, horizon_days=5)
    assert mc, "expected a Monte-Carlo result from sufficient history"
    assert mc["p05_return_pct"] <= mc["expected_return_pct"] <= mc["p95_return_pct"]
    assert 0.0 <= mc["prob_up"] <= 1.0


def test_forecast_signal_uptrend_leans_long(uptrend_df):
    comp, f = fc.forecast_signal(uptrend_df, horizon_days=5)
    assert comp.available is True
    assert f.available is True
    assert comp.name == "ensemble_forecast"
    # Uptrend should not produce a bearish ensemble.
    assert comp.score >= 50
    assert "long" in f.agent_votes.values()


def test_forecast_signal_insufficient_history():
    import pandas as pd

    tiny = pd.DataFrame({"open": [1, 2], "high": [1, 2], "low": [1, 2], "close": [1, 2], "volume": [1, 1]})
    comp, f = fc.forecast_signal(tiny, horizon_days=5)
    assert comp.available is False
    assert f.available is False


def test_monte_carlo_deterministic_with_seed(uptrend_df):
    a = fc.monte_carlo(uptrend_df, horizon_days=5, seed=7)
    b = fc.monte_carlo(uptrend_df, horizon_days=5, seed=7)
    assert a["expected_return_pct"] == b["expected_return_pct"]


def test_monte_carlo_gpu_request_falls_back_without_cupy(uptrend_df):
    mc = fc.monte_carlo(uptrend_df, horizon_days=5, seed=7, use_gpu=True)
    assert mc
    assert mc["backend"] in {"cupy_gpu", "numpy_cpu_fallback"}
    assert 0.0 <= mc["prob_up"] <= 1.0


def test_forecast_signal_uses_configured_monte_carlo_paths(uptrend_df):
    comp, f = fc.forecast_signal(uptrend_df, horizon_days=5, n_paths=1234, use_gpu=False)
    assert comp.available is True
    assert f.n_paths == 1234
    assert "numpy_cpu" in f.method
