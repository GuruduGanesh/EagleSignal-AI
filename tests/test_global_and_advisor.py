import numpy as np
import pandas as pd

from eaglesignal.analysis.global_correlation import global_correlations
from eaglesignal.advisor import advise, parse_portfolio
from eaglesignal.config import Settings


def _rules_settings() -> Settings:
    """Force the deterministic rule-based backend so these tests are independent
    of any local .env (e.g. a configured Ollama)."""
    return Settings(advisor_provider="rules")


def _series(seed: int, n: int = 120) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=n, freq="B")
    close = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.012, n)))
    return pd.DataFrame({"close": close}, index=idx)


def test_global_correlations_self_is_one():
    df = _series(1)
    corr = global_correlations(df, {"SELF": df, "OTHER": _series(2)})
    assert abs(corr["SELF"] - 1.0) < 1e-6
    assert -1.0 <= corr["OTHER"] <= 1.0


def test_global_correlations_sorted_by_abs():
    df = _series(1)
    corr = global_correlations(df, {"SELF": df, "OTHER": _series(2), "OTHER2": _series(3)})
    vals = [abs(v) for v in corr.values()]
    assert vals == sorted(vals, reverse=True)


def test_global_correlations_empty_inputs():
    assert global_correlations(pd.DataFrame(), {}) == {}


def _preds():
    return [
        {"ticker": "AAPL", "direction": "neutral_to_bullish", "opportunity_score": 62,
         "confidence_score": 85, "risk_score": 30, "risk": {"risk_level": "low", "warnings": []},
         "severity": "P2", "expected_move": {"low_pct": -1.2, "high_pct": 1.2},
         "forecast": {"prob_up": 0.6, "p05_return_pct": -3, "p95_return_pct": 4},
         "catalysts": ["SEC 10-Q filed"], "policy_impacts": [], "global_correlations": {"S&P 500": 0.6},
         "invalidation_conditions": ["Close below 300"], "market_snapshot": {"current_price": 312}},
        {"ticker": "XYZ", "direction": "bearish", "opportunity_score": 30,
         "confidence_score": 70, "risk_score": 70, "risk": {"risk_level": "high", "warnings": ["earnings risk"]},
         "severity": "P3", "expected_move": {"low_pct": -5, "high_pct": 5},
         "forecast": {"prob_up": 0.4, "p05_return_pct": -8, "p95_return_pct": 6},
         "catalysts": [], "policy_impacts": [], "global_correlations": {},
         "invalidation_conditions": ["Close above 50"], "market_snapshot": {"current_price": 40}},
    ]


def test_advisor_buy_intent_ranks_supported_ideas():
    res = advise("what should I buy?", predictions=_preds(), settings=_rules_settings())
    assert res["backend"] == "rules"
    assert "AAPL" in res["answer"]
    assert "XYZ" not in res["answer"]  # bearish/high-risk excluded from buy list
    assert "not financial advice" in res["answer"].lower()


def test_advisor_portfolio_review():
    res = advise("review my holdings", predictions=_preds(), portfolio=parse_portfolio("AAPL:10, XYZ:3"),
                 settings=_rules_settings())
    assert "AAPL" in res["answer"] and "XYZ" in res["answer"]
    assert "avoid" in res["answer"].lower()  # bearish XYZ flagged


def test_advisor_no_signals():
    res = advise("what should I buy?", predictions=[])
    assert res["used_signals"] == 0


def test_parse_portfolio_formats():
    assert parse_portfolio("AAPL:10, MSFT:5") == [
        {"ticker": "AAPL", "quantity": 10.0}, {"ticker": "MSFT", "quantity": 5.0}]
    assert parse_portfolio("NVDA 2; TSLA 1") == [
        {"ticker": "NVDA", "quantity": 2.0}, {"ticker": "TSLA", "quantity": 1.0}]
    assert parse_portfolio(None) == []
