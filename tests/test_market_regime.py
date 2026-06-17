import numpy as np
import pandas as pd

from eaglesignal.analysis.market_regime import (
    MarketRegime,
    assess_market_regime,
    beta_sensitivity,
)
from eaglesignal.ingestion.macro_fred import MacroSnapshot


def _bars(start: float, end: float, n: int = 60) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=n)
    return pd.DataFrame({"close": np.linspace(start, end, n)}, index=idx)


def test_risk_off_when_market_falls_and_vix_high():
    macro = MacroSnapshot(values={"vix": 30.0, "yield_curve_10y_2y": -0.3}, available=True, source="t")
    reg = assess_market_regime(_bars(500, 450), macro, {})
    assert reg.available
    assert reg.risk_off
    assert reg.score < 45
    assert any("below its 50-day" in d for d in reg.drivers)


def test_risk_on_when_market_rises_and_vix_low():
    macro = MacroSnapshot(values={"vix": 12.0, "yield_curve_10y_2y": 0.5}, available=True, source="t")
    reg = assess_market_regime(_bars(450, 510), macro, {})
    assert reg.available
    assert reg.score > 55
    assert not reg.risk_off


def test_unavailable_without_data():
    reg = assess_market_regime(None, None, {})
    assert not reg.available
    assert reg.label == "neutral"


def test_beta_sensitivity_trims_longs_in_risk_off_confirms_shorts():
    reg = MarketRegime(label="strong_risk_off", score=18, risk_off=True, available=True)
    mult_bull, note_bull = beta_sensitivity(reg, "bullish")
    mult_bear, note_bear = beta_sensitivity(reg, "bearish")
    assert mult_bull < 1.0 and note_bull
    assert mult_bear > 1.0 and note_bear
    # never inflates a long into a falling market
    assert mult_bull <= 0.9


def test_beta_sensitivity_neutral_when_regime_unavailable():
    mult, note = beta_sensitivity(MarketRegime(available=False), "bullish")
    assert mult == 1.0 and note is None
