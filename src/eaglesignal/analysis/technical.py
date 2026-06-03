"""SKILL-100..115 Technical indicator engine.

Pure, dependency-light indicator functions (numpy/pandas only) so they are
unit-testable in isolation (lesson borrowed from investdaytip's testable scoring
and myhhub's broad indicator coverage). `technical_signal` aggregates them into
one 0..100 SignalComponent plus a price/volume/momentum component.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..schemas import SignalComponent


# --------------------------------------------------------------------------- #
# Indicator primitives
# --------------------------------------------------------------------------- #
def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line, macd_line - signal_line


def bollinger(series: pd.Series, window: int = 20, n_std: float = 2.0):
    mid = sma(series, window)
    sd = series.rolling(window).std()
    return mid + n_std * sd, mid, mid - n_std * sd


def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift()
    ranges = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()],
        axis=1,
    )
    return ranges.max(axis=1)


def atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    return true_range(df).rolling(window).mean()


def adx(df: pd.DataFrame, window: int = 14) -> pd.Series:
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(df)
    atr_ = tr.rolling(window).mean().replace(0, np.nan)
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(window).mean() / atr_
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(window).mean() / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.rolling(window).mean().fillna(0)


def obv(df: pd.DataFrame) -> pd.Series:
    direction = np.sign(df["close"].diff().fillna(0))
    return (direction * df["volume"]).cumsum()


def relative_volume(df: pd.DataFrame, window: int = 20) -> float:
    avg = df["volume"].rolling(window).mean().iloc[-1]
    if not avg or np.isnan(avg):
        return 1.0
    return float(df["volume"].iloc[-1] / avg)


# --------------------------------------------------------------------------- #
# Aggregated signals
# --------------------------------------------------------------------------- #
def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def technical_signal(df: pd.DataFrame) -> SignalComponent:
    """Trend / structure score from MAs, MACD, RSI, ADX, Bollinger."""
    close = df["close"]
    score = 50.0
    notes: list[str] = []

    s20, s50, s200 = sma(close, 20).iloc[-1], sma(close, 50).iloc[-1], sma(close, 200).iloc[-1]
    price = close.iloc[-1]
    if not np.isnan(s50):
        if price > s50:
            score += 8; notes.append("Price above 50-day SMA (uptrend).")
        else:
            score -= 8; notes.append("Price below 50-day SMA (downtrend).")
    if not np.isnan(s200):
        if price > s200:
            score += 7; notes.append("Price above 200-day SMA (long-term up).")
        else:
            score -= 7; notes.append("Price below 200-day SMA (long-term down).")
    if not np.isnan(s20) and not np.isnan(s50):
        if s20 > s50:
            score += 5; notes.append("20>50 SMA (golden alignment).")
        else:
            score -= 5; notes.append("20<50 SMA (death alignment).")

    _, _, hist = macd(close)
    if hist.iloc[-1] > 0:
        score += 6; notes.append("MACD histogram positive.")
    else:
        score -= 6; notes.append("MACD histogram negative.")

    r = rsi(close).iloc[-1]
    if r > 70:
        score -= 6; notes.append(f"RSI {r:.0f} overbought.")
    elif r < 30:
        score += 6; notes.append(f"RSI {r:.0f} oversold (mean-reversion up).")
    else:
        notes.append(f"RSI {r:.0f} neutral.")

    adx_val = adx(df).iloc[-1]
    if adx_val > 25:
        notes.append(f"ADX {adx_val:.0f}: trending regime.")
        score += 3 if hist.iloc[-1] > 0 else -3

    upper, _, lower = bollinger(close)
    if price > upper.iloc[-1]:
        score -= 3; notes.append("Above upper Bollinger band (stretched).")
    elif price < lower.iloc[-1]:
        score += 3; notes.append("Below lower Bollinger band (stretched).")

    return SignalComponent(name="technical_structure", score=_clamp(score), weight=0.0, rationale=notes)


def price_volume_signal(df: pd.DataFrame) -> SignalComponent:
    """Momentum + relative volume + volatility expansion."""
    close = df["close"]
    score = 50.0
    notes: list[str] = []

    ret_5 = (close.iloc[-1] / close.iloc[-6] - 1) * 100 if len(close) > 6 else 0
    ret_20 = (close.iloc[-1] / close.iloc[-21] - 1) * 100 if len(close) > 21 else 0
    score += _clamp(ret_5 * 1.5, -15, 15)
    score += _clamp(ret_20 * 0.7, -12, 12)
    notes.append(f"5-day return {ret_5:+.1f}%, 20-day {ret_20:+.1f}%.")

    rvol = relative_volume(df)
    if rvol > 1.5:
        score += 6; notes.append(f"Relative volume {rvol:.1f}x (institutional interest).")
    elif rvol < 0.6:
        score -= 3; notes.append(f"Relative volume {rvol:.1f}x (apathy).")
    else:
        notes.append(f"Relative volume {rvol:.1f}x.")

    obv_series = obv(df)
    if len(obv_series) > 20 and obv_series.iloc[-1] > obv_series.iloc[-20]:
        score += 4; notes.append("OBV rising (accumulation).")
    else:
        score -= 4; notes.append("OBV flat/falling (distribution).")

    return SignalComponent(name="price_volume_momentum", score=_clamp(score), weight=0.0, rationale=notes)
