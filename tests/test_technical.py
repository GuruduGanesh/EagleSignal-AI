import numpy as np
import pandas as pd

from eaglesignal.analysis import technical as ta


def test_rsi_bounds(uptrend_df):
    r = ta.rsi(uptrend_df["close"])
    assert r.dropna().between(0, 100).all()


def test_sma_ema_basic():
    s = pd.Series([1, 2, 3, 4, 5], dtype=float)
    assert ta.sma(s, 2).iloc[-1] == 4.5
    assert ta.ema(s, 2).iloc[-1] > 0


def test_atr_positive(uptrend_df):
    a = ta.atr(uptrend_df)
    assert a.dropna().ge(0).all()


def test_technical_signal_uptrend_bullish(uptrend_df):
    comp = ta.technical_signal(uptrend_df)
    assert comp.score > 55
    assert comp.name == "technical_structure"


def test_technical_signal_downtrend_bearish(downtrend_df):
    comp = ta.technical_signal(downtrend_df)
    assert comp.score < 45


def test_relative_volume_spike():
    n = 40
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    vol = np.full(n, 1_000_000.0)
    vol[-1] = 5_000_000.0
    df = pd.DataFrame({"close": np.arange(n, dtype=float), "volume": vol}, index=idx)
    assert ta.relative_volume(df) > 3
